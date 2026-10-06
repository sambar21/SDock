import shutil
from pathlib import Path
from typing import BinaryIO, Protocol

from app.core.config import settings

_CHUNK = 1024 * 1024


class FileTooLarge(Exception):
    pass


class Storage(Protocol):
    """What the rest of the app needs from a file store. S3 could implement this later."""

    def save(self, key: str, source: BinaryIO, max_bytes: int) -> int: ...
    def open(self, key: str) -> BinaryIO: ...
    def path(self, key: str) -> Path: ...
    def delete_prefix(self, prefix: str) -> None: ...


class LocalStorage:
    def __init__(self, root: str):
        self.root = Path(root).resolve()

    def path(self, key: str) -> Path:
        full = (self.root / key).resolve()
        if self.root not in full.parents:
            raise ValueError("Storage key escapes the storage folder.")
        return full

    def save(self, key: str, source: BinaryIO, max_bytes: int) -> int:
        """Copy source to disk and return its size. Removes the partial file if it is too big."""
        target = self.path(key)
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

    def open(self, key: str) -> BinaryIO:
        return open(self.path(key), "rb")

    def delete_prefix(self, prefix: str) -> None:
        shutil.rmtree(self.path(prefix), ignore_errors=True)


def get_storage() -> Storage:
    return LocalStorage(settings.storage_dir)
