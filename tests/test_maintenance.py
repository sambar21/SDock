from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.maintenance import STUCK_MESSAGE, fail_stuck_scans
from app.models import Organization, Scan, ScanStatus, User


@pytest.fixture()
def Session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def add_scan(Session, status, age_minutes):
    with Session() as db:
        user, org = User(email=f"{status.value}{age_minutes}@x.co", password_hash="x"), Organization(name="o")
        db.add_all([user, org])
        db.flush()
        scan = Scan(organization_id=org.id, uploaded_by=user.id, name="s", original_filename="s.ply",
                    original_size=10, status=status,
                    updated_at=datetime.now(timezone.utc) - timedelta(minutes=age_minutes))
        db.add(scan)
        db.commit()
        return scan.id


def status_of(Session, scan_id):
    with Session() as db:
        scan = db.get(Scan, scan_id)
        return scan.status, scan.error_message


@pytest.mark.parametrize("status", [ScanStatus.uploaded, ScanStatus.validating, ScanStatus.processing])
def test_old_unfinished_scans_are_failed_with_a_message(Session, status):
    scan_id = add_scan(Session, status, age_minutes=30)
    assert fail_stuck_scans(Session, older_than=timedelta(minutes=15)) == 1
    assert status_of(Session, scan_id) == (ScanStatus.failed, STUCK_MESSAGE)


def test_recent_scans_are_left_alone(Session):
    scan_id = add_scan(Session, ScanStatus.processing, age_minutes=2)
    assert fail_stuck_scans(Session, older_than=timedelta(minutes=15)) == 0
    assert status_of(Session, scan_id)[0] == ScanStatus.processing


@pytest.mark.parametrize("status", [ScanStatus.ready, ScanStatus.failed])
def test_finished_scans_are_never_touched_however_old(Session, status):
    scan_id = add_scan(Session, status, age_minutes=10_000)
    assert fail_stuck_scans(Session, older_than=timedelta(minutes=15)) == 0
    assert status_of(Session, scan_id) == (status, None)


def test_running_it_twice_changes_nothing_the_second_time(Session):
    add_scan(Session, ScanStatus.processing, age_minutes=60)
    assert fail_stuck_scans(Session, older_than=timedelta(minutes=15)) == 1
    assert fail_stuck_scans(Session, older_than=timedelta(minutes=15)) == 0


def test_a_late_job_does_not_revive_a_rescued_scan(client, make_user):
    """If the sweeper failed a scan, a worker picking up its old job later must do nothing."""
    from tests.helpers import make_org, upload
    from tools import scangen

    owner = make_user("owner@example.com")
    org = make_org(client, owner)
    scan = upload(client, owner, org, scangen.point_cloud(1_000)).json()
    # The sweeper would have failed it; mimic that, then let the stale job run.
    from app.main import app
    from app.db import get_db
    db = next(app.dependency_overrides[get_db]())
    row = db.get(Scan, scan["id"])
    row.status, row.error_message = ScanStatus.failed, STUCK_MESSAGE
    db.commit()

    client.run_jobs()

    after = client.get(f"/api/v1/scans/{scan['id']}", headers=owner).json()
    assert after["status"] == "failed"
    assert after["error_message"] == STUCK_MESSAGE
