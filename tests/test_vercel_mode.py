"""Vercel mode: files in the database, processing inside the upload request, a cron sweeper."""
import io
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import worker
from app.core.config import Settings
from app.db import Base, get_db
from app.main import app
from app.models import Scan, ScanStatus
from app.services import queue
from app.services.storage import DatabaseStorage, FileTooLarge, LocalStorage, get_storage
from tests.helpers import make_org, upload
from tools import scangen

ROOT = Path(__file__).resolve().parent.parent
STRONG = "k" * 40
POSTGRES = "postgresql://user:pass@host/db"


# ---- The two storage backends must behave the same ----

@pytest.fixture(params=["local", "database"])
def store(request, tmp_path):
    if request.param == "local":
        return LocalStorage(str(tmp_path / "files"))
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return DatabaseStorage(sessionmaker(bind=engine))


def test_saved_stream_can_be_read_back(store):
    assert store.save("org/scan/original.ply", io.BytesIO(b"hello"), max_bytes=100) == 5
    with store.open("org/scan/original.ply") as f:
        assert f.read() == b"hello"


def test_write_replaces_what_was_there(store):
    store.write("org/scan/preview.glb", b"one")
    store.write("org/scan/preview.glb", b"two")
    with store.open("org/scan/preview.glb") as f:
        assert f.read() == b"two"


def test_too_large_is_refused_and_nothing_is_kept(store):
    with pytest.raises(FileTooLarge):
        store.save("org/scan/original.ply", io.BytesIO(b"x" * 50), max_bytes=10)
    with pytest.raises(FileNotFoundError):
        store.open("org/scan/original.ply")


def test_missing_key_raises_file_not_found(store):
    with pytest.raises(FileNotFoundError):
        store.open("org/nothing/here.ply")


def test_delete_prefix_removes_that_scan_only(store):
    store.write("org/a/original.ply", b"1")
    store.write("org/a/preview.glb", b"2")
    store.write("org/ab/original.ply", b"3")  # shares the text "org/a" but is another scan
    store.delete_prefix("org/a")
    for gone in ("org/a/original.ply", "org/a/preview.glb"):
        with pytest.raises(FileNotFoundError):
            store.open(gone)
    with store.open("org/ab/original.ply") as f:
        assert f.read() == b"3"


# ---- Settings ----

def test_vercel_switches_on_the_serverless_defaults(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    s = Settings(secret_key=STRONG, database_url=POSTGRES)
    assert (s.storage_backend, s.queue_backend, s.max_upload_mb) == ("database", "inline", 4)
    assert s.sweep_enabled is False
    assert s.environment == "production"


def test_explicit_settings_beat_the_vercel_defaults(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    s = Settings(secret_key=STRONG, database_url=POSTGRES, max_upload_mb=3, storage_backend="local")
    assert (s.max_upload_mb, s.storage_backend) == (3, "local")


def test_vercel_refuses_to_start_without_a_real_secret(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    with pytest.raises(ValidationError):
        Settings()


def test_nothing_changes_off_vercel(monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    s = Settings()
    assert (s.storage_backend, s.queue_backend, s.max_upload_mb, s.environment) == ("local", "redis", 200, "dev")


@pytest.mark.parametrize("given", ["postgres://u:p@host/db", "postgresql://u:p@host/db"])
def test_host_database_urls_are_given_the_driver_name(given):
    assert Settings(database_url=given).database_url == "postgresql+psycopg://u:p@host/db"


def test_a_url_that_already_names_the_driver_is_left_alone():
    url = "postgresql+psycopg://u:p@host/db?sslmode=require"
    assert Settings(database_url=url).database_url == url


@pytest.mark.parametrize("field", ["storage_backend", "queue_backend"])
def test_unknown_backends_are_rejected(field):
    with pytest.raises(ValidationError):
        Settings(**{field: "carrier-pigeon"})


# ---- The whole flow in Vercel mode, minus the platform ----

@pytest.fixture()
def vercel_client(monkeypatch):
    from fastapi.testclient import TestClient

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db():
        with Session() as session:
            yield session

    monkeypatch.setattr(queue.settings, "queue_backend", "inline")
    monkeypatch.setattr(worker, "SessionLocal", Session)
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_storage] = lambda: DatabaseStorage(Session)
    client = TestClient(app)
    client.Session = Session
    yield client
    app.dependency_overrides.clear()


def register(client, email):
    token = client.post("/api/v1/auth/register", json={"email": email, "password": "password123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_upload_is_processed_before_the_response_returns(vercel_client):
    owner = register(vercel_client, "owner@example.com")
    org = make_org(vercel_client, owner)

    response = upload(vercel_client, owner, org, scangen.point_cloud(30_000))

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "ready"
    assert body["preview_size"] and body["preview_size"] < body["original_size"]
    assert body["reduction_pct"] > 80

    preview = vercel_client.get(f"/api/v1/scans/{body['id']}/preview", headers=owner)
    assert preview.status_code == 200
    assert preview.content[:4] == b"glTF"
    assert len(preview.content) == body["preview_size"]
    assert preview.headers["content-length"] == str(body["preview_size"])


def test_a_broken_scan_comes_back_failed_with_its_reason(vercel_client):
    owner = register(vercel_client, "owner@example.com")
    org = make_org(vercel_client, owner)
    body = upload(vercel_client, owner, org, scangen.with_nan()).json()
    assert body["status"] == "failed"
    assert "invalid coordinates" in body["error_message"]


def test_deleting_a_scan_removes_its_files_from_the_database(vercel_client):
    from app.models import StoredFile

    owner = register(vercel_client, "owner@example.com")
    org = make_org(vercel_client, owner)
    scan = upload(vercel_client, owner, org, scangen.point_cloud(3_000)).json()
    with vercel_client.Session() as db:
        assert db.query(StoredFile).count() == 2  # the original and the preview
    assert vercel_client.delete(f"/api/v1/scans/{scan['id']}", headers=owner).status_code == 204
    with vercel_client.Session() as db:
        assert db.query(StoredFile).count() == 0


# ---- Cron sweeper ----

def test_sweep_endpoint_is_off_without_a_secret(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.internal.settings.cron_secret", "")
    assert client.get("/api/v1/internal/sweep", headers={"Authorization": "Bearer "}).status_code == 404
    assert client.get("/api/v1/internal/sweep").status_code == 404


def test_sweep_endpoint_needs_the_right_secret(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.internal.settings.cron_secret", STRONG)
    assert client.get("/api/v1/internal/sweep").status_code == 404
    assert client.get("/api/v1/internal/sweep", headers={"Authorization": "Bearer wrong"}).status_code == 404


def test_sweep_endpoint_fails_stuck_scans(client, make_user, monkeypatch):
    monkeypatch.setattr("app.api.v1.internal.settings.cron_secret", STRONG)
    monkeypatch.setattr("app.maintenance.SessionLocal", client.Session)
    owner = make_user("owner@example.com")
    org = make_org(client, owner)
    scan_id = upload(client, owner, org, scangen.point_cloud(1_000)).json()["id"]
    with client.Session() as db:  # make it look old
        scan = db.get(Scan, scan_id)
        scan.updated_at = datetime.now(timezone.utc) - timedelta(hours=2)
        db.commit()

    response = client.get("/api/v1/internal/sweep", headers={"Authorization": f"Bearer {STRONG}"})

    assert response.status_code == 200
    assert response.json() == {"failed": 1}
    assert client.get(f"/api/v1/scans/{scan_id}", headers=owner).json()["status"] == "failed"


def test_sweep_route_is_hidden_from_the_public_docs(client):
    assert "/api/v1/internal/sweep" not in client.get("/openapi.json").json()["paths"]


# ---- Deployment files ----

def test_vercel_json_points_at_things_that_exist(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.internal.settings.cron_secret", STRONG)
    monkeypatch.setattr("app.maintenance.SessionLocal", client.Session)
    config = json.loads((ROOT / "vercel.json").read_text())
    for entry in config["functions"]:
        assert (ROOT / entry).is_file()
    for cron in config["crons"]:
        # Vercel Cron sends the secret as a bearer token, so this is the call it will make.
        assert client.get(cron["path"], headers={"Authorization": f"Bearer {STRONG}"}).status_code == 200


def test_the_deployed_bundle_still_contains_what_runs():
    ignored = {line.strip().rstrip("/") for line in (ROOT / ".vercelignore").read_text().splitlines()
               if line.strip() and not line.startswith("#")}
    for needed in ("app", "viewer", "requirements.txt", "vercel.json"):
        assert needed not in ignored
        assert (ROOT / needed).exists()


def test_requirements_cover_what_the_app_imports():
    text = (ROOT / "requirements.txt").read_text().lower()
    for package in ("fastapi", "sqlalchemy", "psycopg", "numpy", "trimesh", "fast-simplification", "pwdlib", "pyjwt"):
        assert package in text


# ---- Wrong settings should explain themselves ----

def test_vercel_without_a_database_url_is_refused_with_a_clear_reason(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        Settings(secret_key=STRONG)


def test_a_demo_on_vercel_still_needs_a_database(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        Settings(auth_disabled=True)
    assert Settings(auth_disabled=True, database_url=POSTGRES).auth_disabled


def test_loading_bad_settings_reports_instead_of_crashing(monkeypatch):
    from app.core.config import load_settings

    monkeypatch.setenv("VERCEL", "1")
    for name in ("SECRET_KEY", "DATABASE_URL", "AUTH_DISABLED"):
        monkeypatch.delenv(name, raising=False)
    loaded, problem = load_settings()
    assert problem and "SECRET_KEY" in problem
    assert isinstance(loaded, Settings)  # a usable object, so the app can still import and explain


def test_loading_good_settings_reports_no_problem(monkeypatch):
    from app.core.config import load_settings

    monkeypatch.delenv("VERCEL", raising=False)
    assert load_settings()[1] is None


@pytest.fixture()
def broken_settings(client, monkeypatch):
    monkeypatch.setattr("app.main.CONFIG_ERROR", "Set SECRET_KEY to a random value.")
    return client


def test_a_broken_setup_answers_every_path_with_a_readable_page(broken_settings):
    for path in ("/", "/viewer/", "/api/v1/health", "/api/v1/orgs", "/docs"):
        response = broken_settings.get(path, follow_redirects=False)
        assert response.status_code == 503, path
        assert "text/html" in response.headers["content-type"]
        assert "Set SECRET_KEY to a random value." in response.text
        assert "Setup needed" in response.text


def test_the_setup_page_lists_names_and_status_but_never_values(broken_settings, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "super-secret-value-0123456789")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    page = broken_settings.get("/").text
    assert "SECRET_KEY" in page and "DATABASE_URL" in page
    assert "super-secret-value-0123456789" not in page
    row = next(r for r in page.split("<tr>") if "DATABASE_URL" in r)
    assert "not set" in row
    row = next(r for r in page.split("<tr>") if "SECRET_KEY" in r)
    assert "not set" not in row


def test_the_setup_page_escapes_the_message(broken_settings, monkeypatch):
    monkeypatch.setattr("app.main.CONFIG_ERROR", "<script>alert(1)</script>")
    page = broken_settings.get("/").text
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page


def test_a_good_setup_is_not_affected(client):
    assert client.get("/api/v1/health").status_code == 200
