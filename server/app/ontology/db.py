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
    from ..agent_profile import models as _ap_models  # noqa: F401
    from ..knowledge import models as _kb_models  # noqa: F401
    from ..mcp_registry import models as _mcp_models  # noqa: F401
    from ..observability import models as _obs_models  # noqa: F401
    from ..preferences import models as _pref_models  # noqa: F401
    from ..publish import models as _pub_models  # noqa: F401
    from ..workflow import models as _wf_models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a database session."""
    with Session(engine) as session:
        yield session
