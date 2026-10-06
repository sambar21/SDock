import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1 import api_router
from app.core.config import settings
from app.core.errors import install_error_handlers
from app.maintenance import sweep_forever


@asynccontextmanager
async def lifespan(app: FastAPI):
    sweeper = asyncio.create_task(sweep_forever()) if settings.sweep_enabled else None
    yield
    if sweeper:
        sweeper.cancel()


DESCRIPTION = """
Upload 3D scans (PLY), let a background worker turn each one into a much smaller GLB preview,
and open the preview in the browser viewer at `/viewer/`.

**Signing in.** Call `POST /api/v1/auth/register` or `/login`, then send the token as
`Authorization: Bearer <token>`. In this page, use the Authorize button.

**Roles.** Every organization has owners, editors and viewers. Viewers can look, editors can also
upload and delete scans, owners can also manage members. Someone outside an organization gets
`404`, never `403`, so organization ids are not revealed.

**Errors.** Every error is `{"error": "<code>", "message": "<text>"}`.

**Scan status.** `uploaded`, `validating`, `processing`, then `ready` or `failed`.
Poll `GET /api/v1/scans/{id}` until it is `ready`.
"""

TAGS = [
    {"name": "auth", "description": "Create an account and get a token."},
    {"name": "orgs", "description": "Organizations and who belongs to them."},
    {"name": "scans", "description": "Upload scans, follow their status, fetch previews."},
    {"name": "health", "description": "Is the service up?"},
]

app = FastAPI(title="Scan Service", version="1.0.0", description=DESCRIPTION, openapi_tags=TAGS, lifespan=lifespan)
install_error_handlers(app)
app.include_router(api_router)

VIEWER_DIR = Path(__file__).resolve().parent.parent / "viewer"
app.mount("/viewer", StaticFiles(directory=VIEWER_DIR, html=True), name="viewer")


@app.get("/", include_in_schema=False)
def home():
    return RedirectResponse("/viewer/")

# Multipart overhead (boundaries, form fields) on top of the file itself.
_BODY_SLACK = 1024 * 1024


@app.middleware("http")
async def reject_oversized_bodies(request: Request, call_next):
    """Turn away big uploads by their declared size, before the body is read."""
    declared = request.headers.get("content-length")
    limit = settings.max_upload_mb * 1024 * 1024 + _BODY_SLACK
    if declared and declared.isdigit() and int(declared) > limit:
        body = {"error": "file_too_large", "message": f"Files can be at most {settings.max_upload_mb} MB."}
        return JSONResponse(body, status_code=413)
    return await call_next(request)
