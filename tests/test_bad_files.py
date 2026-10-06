import pytest

from app.core.config import settings
from tests.helpers import make_org, upload
from tools import scangen


@pytest.fixture()
def org(client, make_user):
    owner = make_user("owner@example.com")
    return owner, make_org(client, owner)


def test_wrong_extension_is_rejected(client, org):
    owner, org_id = org
    response = upload(client, owner, org_id, scangen.point_cloud(100), filename="scan.obj")
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_file_type"


def test_text_pretending_to_be_ply_is_rejected(client, org):
    owner, org_id = org
    response = upload(client, owner, org_id, scangen.not_a_ply(), filename="scan.ply")
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_file_type"


def test_empty_file_is_rejected(client, org):
    owner, org_id = org
    response = upload(client, owner, org_id, b"")
    assert response.status_code == 400
    assert response.json()["error"] == "empty_file"


def test_oversized_file_is_rejected_and_nothing_is_kept(client, org, monkeypatch, tmp_path):
    owner, org_id = org
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    response = upload(client, owner, org_id, scangen.point_cloud(200_000))  # about 3 MB
    assert response.status_code == 413
    assert response.json()["error"] == "file_too_large"
    assert list((tmp_path / "storage").rglob("*.ply")) == []
    assert client.get(f"/api/v1/orgs/{org_id}/scans", headers=owner).json() == []


def test_file_just_over_the_limit_is_caught_while_saving(client, org, monkeypatch, tmp_path):
    """Small enough to pass the declared-size check, so the streaming check has to catch it."""
    owner, org_id = org
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    response = upload(client, owner, org_id, scangen.point_cloud(100_000))  # about 1.5 MB
    assert response.status_code == 413
    assert list((tmp_path / "storage").rglob("*.ply")) == []


def test_a_rejected_upload_leaves_no_scan_behind(client, org):
    owner, org_id = org
    upload(client, owner, org_id, b"")
    upload(client, owner, org_id, scangen.not_a_ply())
    assert client.get(f"/api/v1/orgs/{org_id}/scans", headers=owner).json() == []
