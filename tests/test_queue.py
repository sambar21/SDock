import fakeredis
from rq import Queue, SimpleWorker
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app import worker
from app.db import Base
from app.services import queue


def test_enqueue_puts_a_job_on_the_scans_queue(monkeypatch):
    connection = fakeredis.FakeStrictRedis()
    monkeypatch.setattr(queue.Redis, "from_url", lambda *a, **k: connection)

    queue.enqueue_processing("abc-123")

    jobs = Queue(queue.QUEUE_NAME, connection=connection).jobs
    assert [(j.func_name, j.args) for j in jobs] == [("app.worker.process_scan", ("abc-123",))]


def test_a_real_worker_can_run_the_queued_job(monkeypatch):
    """The job's function path must resolve, and a missing scan must be a quiet no-op."""
    connection = fakeredis.FakeStrictRedis()
    monkeypatch.setattr(queue.Redis, "from_url", lambda *a, **k: connection)
    q = Queue(queue.QUEUE_NAME, connection=connection)

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(worker, "SessionLocal", sessionmaker(bind=engine))

    queue.enqueue_processing("no-such-scan")
    SimpleWorker([q], connection=connection).work(burst=True)

    assert q.finished_job_registry.count == 1
    assert q.failed_job_registry.count == 0
