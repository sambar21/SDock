"""Cheap checks that run during upload. Parsing checks live in the worker."""
from typing import BinaryIO

from app.core.errors import ApiError

ALLOWED_EXTENSIONS = (".ply",)
_PLY_MAGIC = b"ply"


def check_filename(filename: str | None) -> str:
    name = (filename or "").strip()
    if not name.lower().endswith(ALLOWED_EXTENSIONS):
        raise ApiError(400, "invalid_file_type", "Only .ply files are supported.")
    return name


def check_content(source: BinaryIO) -> None:
    """Look at the first bytes without consuming them."""
    head = source.read(16)
    source.seek(0)
    if not head:
        raise ApiError(400, "empty_file", "The file is empty.")
    if not head.startswith(_PLY_MAGIC) or head[3:4] not in (b"\n", b"\r"):
        raise ApiError(400, "invalid_file_type", "The file does not look like a PLY scan.")
