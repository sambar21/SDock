"""Open demo mode: sign-in switched off, everyone shares one workspace."""
import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.core.config import DEV_SECRET, Settings
from app.core.demo import DEMO_EMAIL, DEMO_ORG_NAME, demo_user
from app.models import Organization, User
from tests.helpers import upload
from tools import scangen


@pytest.fixture()
def open_client(client, monkeypatch):
    monkeypatch.setattr("app.core.permissions.settings.auth_disabled", True)
    monkeypatch.setattr("app.api.v1.auth.settings.auth_disabled", True)
    monkeypatch.setattr("app.api.v1.config.settings.auth_disabled", True)
    return client


def only_org(client):
    orgs = client.get("/api/v1/orgs").json()
    assert len(orgs) == 1
    return orgs[0]


def test_config_tells_the_page_whether_sign_in_is_needed(client, open_client):
    assert open_client.get("/api/v1/config").json() == {"auth_required": False, "max_upload_mb": 200}


def test_config_says_sign_in_is_needed_by_default(client):
    assert client.get("/api/v1/config").json() == {"auth_required": True, "max_upload_mb": 200}


def test_default_mode_still_demands_sign_in(client):
    assert client.get("/api/v1/orgs").status_code == 401


def test_a_visitor_gets_the_shared_workspace_without_signing_in(open_client):
    org = only_org(open_client)
    assert (org["name"], org["your_role"]) == (DEMO_ORG_NAME, "owner")


def test_the_whole_flow_works_with_no_credentials_at_all(open_client):
    org = only_org(open_client)
    response = upload(open_client, {}, org["id"], scangen.point_cloud(10_000), name="Open scan")
    assert response.status_code == 202

    open_client.run_jobs()

    scan = open_client.get(f"/api/v1/scans/{response.json()['id']}").json()
    assert scan["status"] == "ready"
    preview = open_client.get(f"/api/v1/scans/{scan['id']}/preview")
    assert preview.status_code == 200 and preview.content[:4] == b"glTF"
    assert open_client.get(f"/api/v1/orgs/{org['id']}/scans").json()[0]["name"] == "Open scan"
    assert open_client.delete(f"/api/v1/scans/{scan['id']}").status_code == 204


def test_every_visitor_is_the_same_user_so_nothing_is_duplicated(open_client):
    first, second = only_org(open_client), only_org(open_client)
    assert first["id"] == second["id"]
    with open_client.Session() as db:
        assert db.scalar(select(func.count()).select_from(User)) == 1
        assert db.scalar(select(func.count()).select_from(Organization)) == 1


def test_register_and_login_are_switched_off(open_client):
    body = {"email": "a@example.com", "password": "password123"}
    for path in ("/api/v1/auth/register", "/api/v1/auth/login"):
        response = open_client.post(path, json=body)
        assert response.status_code == 404
        assert response.json()["error"] == "auth_disabled"


def test_the_shared_user_can_never_be_logged_into_or_registered(client):
    """If a deployment later turns sign-in back on, the shared user must not become a login."""
    with client.Session() as db:
        demo_user(db)
    body = {"email": DEMO_EMAIL, "password": "long-enough-1"}
    # The reserved ".local" address is refused by the email check before any password is looked at.
    assert client.post("/api/v1/auth/login", json=body).status_code in (401, 422)
    assert client.post("/api/v1/auth/register", json=body).status_code in (409, 422)


def test_a_stored_value_that_is_not_a_hash_never_matches_and_never_crashes():
    from app.core.security import verify_password

    for junk in ("!", "", "not-a-hash", "$argon2id$broken"):
        assert verify_password("long-enough-1", junk) is False


def test_two_simultaneous_first_visits_end_up_with_one_shared_user(client, monkeypatch):
    with client.Session() as db:
        first = demo_user(db)

    with client.Session() as db:
        real_scalar, calls = db.scalar, []

        def blind_first_time(*args, **kwargs):
            calls.append(1)
            return None if len(calls) == 1 else real_scalar(*args, **kwargs)

        monkeypatch.setattr(db, "scalar", blind_first_time)
        second = demo_user(db)  # looks for the user, finds nothing, collides on insert, recovers

    assert second.id == first.id
    with client.Session() as db:
        assert db.scalar(select(func.count()).select_from(User)) == 1


def test_no_secret_is_needed_when_sign_in_is_off():
    s = Settings(environment="production", secret_key=DEV_SECRET, auth_disabled=True)
    assert s.auth_disabled


def test_a_secret_is_still_needed_when_sign_in_is_on():
    with pytest.raises(ValidationError):
        Settings(environment="production", secret_key=DEV_SECRET, auth_disabled=False)
