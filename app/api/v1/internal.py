import secrets

from fastapi import APIRouter, Depends, Header

from app.core.config import settings
from app.core.errors import ApiError
from app.maintenance import fail_stuck_scans

router = APIRouter(prefix="/internal", include_in_schema=False)


def _scheduler_only(authorization: str | None = Header(default=None)) -> None:
    """Vercel Cron sends `Authorization: Bearer <CRON_SECRET>`. With no secret set, the route is off."""
    expected = f"Bearer {settings.cron_secret}"
    if not settings.cron_secret or not secrets.compare_digest(authorization or "", expected):
        raise ApiError(404, "not_found", "Not found.")


@router.get("/sweep", dependencies=[Depends(_scheduler_only)])
def sweep() -> dict:
    """Fail scans stuck for too long. Serverless hosts cannot run the background sweeper, so a cron calls this."""
    return {"failed": fail_stuck_scans()}
