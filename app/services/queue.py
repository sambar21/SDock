from redis import Redis
from rq import Queue

from app.core.config import settings

QUEUE_NAME = "scans"


def enqueue_processing(scan_id: str) -> None:
    """Ask the worker to process a scan. Raises a redis error if the queue is down."""
    connection = Redis.from_url(settings.redis_url, socket_connect_timeout=2)
    Queue(QUEUE_NAME, connection=connection).enqueue("app.worker.process_scan", scan_id, job_timeout=600)


def get_enqueue():
    """Dependency, so tests can swap in a fake queue."""
    return enqueue_processing
