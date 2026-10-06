import os
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings

_options: dict = {}
if settings.database_url.startswith("sqlite"):
    _options["connect_args"] = {"check_same_thread": False}
if os.getenv("VERCEL"):
    # Each serverless instance would otherwise hold its own pool, and many instances
    # exhaust the database's connections. Use the host's pooled URL and keep none here.
    _options["poolclass"] = NullPool

engine = create_engine(settings.database_url, **_options)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
