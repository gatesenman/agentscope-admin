"""Ontology database engine and session helpers."""

from __future__ import annotations

from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from ..settings import get_settings

_settings = get_settings()

engine = create_engine(
    _settings.ontology_db_url,
    connect_args={"check_same_thread": False},
)


def init_db() -> None:
    """Create all ontology tables."""
    # Import models so they register with SQLModel metadata.
    from . import models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a database session."""
    with Session(engine) as session:
        yield session
