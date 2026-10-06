from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/config", summary="What this deployment needs and allows")
def public_config() -> dict:
    """Lets the page decide whether to show a sign-in screen, and how big an upload may be."""
    return {"auth_required": not settings.auth_disabled, "max_upload_mb": settings.max_upload_mb}
