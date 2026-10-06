from fastapi import Depends
from redis import Redis
from rq import Queue

from app.core.config import settings
from app.services.storage import Storage, get_storage

QUEUE_NAME = "scans"


def enqueue_processing(scan_id: str) -> None:
    """Ask the worker to process a scan. Raises a redis error if the queue is down."""
    connection = Redis.from_url(settings.redis_url, socket_connect_timeout=2)
    Queue(QUEUE_NAME, connection=connection).enqueue("app.worker.process_scan", scan_id, job_timeout=600)


def get_enqueue(storage: Storage = Depends(get_storage)):
    """Dependency, so tests can swap in a fake queue.

    "inline" mode does the work right away, inside the upload request. Serverless hosts
    have no worker to hand it to. It is quick, because uploads are capped to small files.
    """
    if settings.queue_backend == "inline":
        from app import worker

        return lambda scan_id: worker.process_scan(scan_id, storage=storage)
    return enqueue_processing
