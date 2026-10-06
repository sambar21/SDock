"""The background job. Run it with:  rq worker scans --url $REDIS_URL"""
import logging

from sqlalchemy.orm import Session, sessionmaker

from app.db import SessionLocal
from app.models import Scan, ScanStatus
from app.services import processing
from app.services.storage import Storage, get_storage

log = logging.getLogger(__name__)


def preview_key(scan: Scan) -> str:
    return f"{scan.organization_id}/{scan.id}/preview.glb"


def original_key(scan: Scan) -> str:
    return f"{scan.organization_id}/{scan.id}/original.ply"


def _move(db: Session, scan: Scan, status: ScanStatus, error: str | None = None) -> None:
    scan.status = status
    scan.error_message = error
    db.commit()


def process_scan(scan_id: str, session_factory: sessionmaker | None = None, storage: Storage | None = None) -> None:
    storage = storage or get_storage()
    with (session_factory or SessionLocal)() as db:
        scan = db.get(Scan, scan_id)
        # Only fresh scans are processed, so a duplicate or late job does nothing.
        if scan is None or scan.status != ScanStatus.uploaded:
            return

        _move(db, scan, ScanStatus.validating)
        try:
            source = storage.path(original_key(scan))
            geometry = processing.load_scan(source)
            processing.check_geometry(geometry)

            _move(db, scan, ScanStatus.processing)
            destination = storage.path(preview_key(scan))
            destination.parent.mkdir(parents=True, exist_ok=True)
            processing.shrink(geometry).export(str(destination), file_type="glb")

            scan.preview_size = destination.stat().st_size
            scan.reduction_pct = round((1 - scan.preview_size / scan.original_size) * 100, 1)
            _move(db, scan, ScanStatus.ready)
        except processing.ScanRejected as exc:
            _move(db, scan, ScanStatus.failed, str(exc))
        except Exception:
            log.exception("Processing scan %s failed", scan_id)
            _move(db, scan, ScanStatus.failed, "Processing failed unexpectedly.")
