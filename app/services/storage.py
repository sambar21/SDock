import io
import shutil
from pathlib import Path
from typing import BinaryIO, Protocol

from sqlalchemy import delete
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models import StoredFile

_CHUNK = 1024 * 1024


class FileTooLarge(Exception):
    pass


class Storage(Protocol):
    """What the rest of the app needs from a file store. S3 could implement this later."""

    def save(self, key: str, source: BinaryIO, max_bytes: int) -> int:
        """Store a stream and return its size. Raises FileTooLarge, keeping nothing, if it exceeds max_bytes."""

    def write(self, key: str, data: bytes) -> None: ...
    def open(self, key: str) -> BinaryIO:
        """Raises FileNotFoundError if the key does not exist."""

    def delete_prefix(self, prefix: str) -> None: ...


class LocalStorage:
    def __init__(self, root: str):
        self.root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        full = (self.root / key).resolve()
        if self.root not in full.parents:
            raise ValueError("Storage key escapes the storage folder.")
        return full

    def save(self, key: str, source: BinaryIO, max_bytes: int) -> int:
        target = self._path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        written = 0
        try:
            with open(target, "wb") as out:
                while chunk := source.read(_CHUNK):
                    written += len(chunk)
                    if written > max_bytes:
                        raise FileTooLarge
                    out.write(chunk)
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        return written

    def write(self, key: str, data: bytes) -> None:
        target = self._path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def open(self, key: str) -> BinaryIO:
        return open(self._path(key), "rb")

    def delete_prefix(self, prefix: str) -> None:
        shutil.rmtree(self._path(prefix), ignore_errors=True)


class DatabaseStorage:
    """Keeps files as rows in the database.

    For serverless hosts, where the disk is wiped between requests. Files are held in
    memory while they move, so it only suits small files (the upload limit keeps them small).
    """

    def __init__(self, session_factory: sessionmaker):
        self.session_factory = session_factory

    def save(self, key: str, source: BinaryIO, max_bytes: int) -> int:
        parts, written = [], 0
        while chunk := source.read(_CHUNK):
            written += len(chunk)
            if written > max_bytes:
                raise FileTooLarge
            parts.append(chunk)
        self.write(key, b"".join(parts))
        return written

    def write(self, key: str, data: bytes) -> None:
        with self.session_factory() as db:
            db.merge(StoredFile(key=key, data=data))
            db.commit()

    def open(self, key: str) -> BinaryIO:
        with self.session_factory() as db:
            row = db.get(StoredFile, key)
            if row is None:
                raise FileNotFoundError(key)
            return io.BytesIO(row.data)

    def delete_prefix(self, prefix: str) -> None:
        with self.session_factory() as db:
            db.execute(delete(StoredFile).where(StoredFile.key.startswith(prefix.rstrip("/") + "/", autoescape=True)))
            db.commit()


def get_storage() -> Storage:
    if settings.storage_backend == "database":
        from app.db import SessionLocal

        return DatabaseStorage(SessionLocal)
    return LocalStorage(settings.storage_dir)
