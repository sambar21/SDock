import uuid

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ApiError, errors
from app.core.permissions import current_user, require_role, require_scan_role
from app.db import get_db
from app.models import Membership, Role, Scan, ScanStatus, User
from app.schemas import ScanOut
from app.services import validation
from app.services.queue import get_enqueue
from app.services.storage import FileTooLarge, Storage, get_storage
from app.worker import preview_key

router = APIRouter(tags=["scans"], responses=errors(401, 403, 404))


def _chunks(source, size: int = 1024 * 1024):
    with source:
        while chunk := source.read(size):
            yield chunk


@router.post(
    "/orgs/{org_id}/scans",
    response_model=ScanOut,
    status_code=202,
    summary="Upload a scan",
    responses=errors(400, 413, 503),
)
def upload_scan(
    org_id: str,
    file: UploadFile = File(...),
    name: str | None = Form(default=None, max_length=200),
    _: Membership = Depends(require_role(Role.editor)),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    storage: Storage = Depends(get_storage),
    enqueue=Depends(get_enqueue),
):
    filename = validation.check_filename(file.filename)
    validation.check_content(file.file)

    scan_id = str(uuid.uuid4())
    key = f"{org_id}/{scan_id}/original.ply"
    max_bytes = settings.max_upload_mb * 1024 * 1024
    try:
        size = storage.save(key, file.file, max_bytes)
    except FileTooLarge:
        raise ApiError(413, "file_too_large", f"Files can be at most {settings.max_upload_mb} MB.")

    scan = Scan(
        id=scan_id,
        organization_id=org_id,
        uploaded_by=user.id,
        name=(name or filename).strip() or filename,
        original_filename=filename[:255],
        original_size=size,
    )
    try:
        db.add(scan)
        db.commit()
    except Exception:
        storage.delete_prefix(f"{org_id}/{scan_id}")
        raise

    try:
        enqueue(scan_id)
    except Exception:
        # Without a queued job the scan would sit in "uploaded" forever, so undo the upload.
        db.delete(scan)
        db.commit()
        storage.delete_prefix(f"{org_id}/{scan_id}")
        raise ApiError(503, "queue_unavailable", "Processing is unavailable right now. Try again shortly.")
    db.refresh(scan)  # inline processing may already have finished it
    return scan


@router.get("/orgs/{org_id}/scans", response_model=list[ScanOut])
def list_scans(
    org_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _: Membership = Depends(require_role(Role.viewer)),
    db: Session = Depends(get_db),
):
    query = (
        select(Scan)
        .where(Scan.organization_id == org_id)
        .order_by(Scan.created_at.desc(), Scan.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return db.scalars(query).all()


@router.get("/scans/{scan_id}", response_model=ScanOut)
def get_scan(scan: Scan = Depends(require_scan_role(Role.viewer))):
    return scan


@router.get(
    "/scans/{scan_id}/preview",
    summary="Download the GLB preview",
    responses={200: {"content": {"model/gltf-binary": {}}, "description": "The preview, as a binary glTF."}, **errors(409)},
)
def get_preview(scan: Scan = Depends(require_scan_role(Role.viewer)), storage: Storage = Depends(get_storage)):
    if scan.status != ScanStatus.ready:
        raise ApiError(409, "not_ready", f"The preview is not available yet (status: {scan.status.value}).")
    try:
        preview = storage.open(preview_key(scan))
    except FileNotFoundError:
        raise ApiError(404, "not_found", "The preview file is missing.")
    return StreamingResponse(
        _chunks(preview),
        media_type="model/gltf-binary",
        headers={"Content-Length": str(scan.preview_size)},
    )


@router.delete("/scans/{scan_id}", status_code=204)
def delete_scan(
    scan: Scan = Depends(require_scan_role(Role.editor)),
    db: Session = Depends(get_db),
    storage: Storage = Depends(get_storage),
):
    storage.delete_prefix(f"{scan.organization_id}/{scan.id}")
    db.delete(scan)
    db.commit()
    return Response(status_code=204)
