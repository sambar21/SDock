"""Housekeeping that keeps scans from getting stuck."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db import SessionLocal
from app.models import Scan, ScanStatus

log = logging.getLogger(__name__)

UNFINISHED = (ScanStatus.uploaded, ScanStatus.validating, ScanStatus.processing)
STUCK_MESSAGE = "Processing did not finish. Please upload the scan again."


def fail_stuck_scans(
    session_factory: sessionmaker | None = None,
    older_than: timedelta | None = None,
    now: datetime | None = None,
) -> int:
    """Fail scans that have sat unfinished too long, for example after a worker crash.

    Returns how many were failed. Safe to run from several processes at once.
    """
    older_than = older_than or timedelta(minutes=settings.stuck_after_minutes)
    cutoff = (now or datetime.now(timezone.utc)) - older_than
    with (session_factory or SessionLocal)() as db:
        stuck = db.scalars(select(Scan).where(Scan.status.in_(UNFINISHED), Scan.updated_at < cutoff)).all()
        for scan in stuck:
            scan.status = ScanStatus.failed
            scan.error_message = STUCK_MESSAGE
        db.commit()
        return len(stuck)


async def sweep_forever() -> None:
    while True:
        await asyncio.sleep(settings.sweep_every_seconds)
        try:
            count = await asyncio.to_thread(fail_stuck_scans)
            if count:
                log.warning("Failed %d stuck scan(s)", count)
        except Exception:
            log.exception("Stuck-scan sweep failed")
