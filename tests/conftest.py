import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.db import Base, get_db
from app.main import app
from app.services.queue import get_enqueue
from app.services.storage import LocalStorage, get_storage
from app.worker import process_scan


@pytest.fixture()
def client(tmp_path):
    """A client with a fresh in-memory database, a fresh storage folder and a fake job queue.

    Uploads put scan ids on `client.queued`. `client.run_jobs()` plays the worker.
    """
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    storage = LocalStorage(str(tmp_path / "storage"))

    def override_db():
        with Session() as session:
            yield session

    test_client = TestClient(app)
    test_client.queued = []

    def run_jobs():
        while test_client.queued:
            process_scan(test_client.queued.pop(0), session_factory=Session, storage=storage)

    test_client.run_jobs = run_jobs

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_enqueue] = lambda: test_client.queued.append
    yield test_client
    app.dependency_overrides.clear()


def register(client, email, password="password123"):
    """Register a user and return an Authorization header for them."""
    body = {"email": email, "password": password}
    token = client.post("/api/v1/auth/register", json=body).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def make_user(client):
    return lambda email: register(client, email)
