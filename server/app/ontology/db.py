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
    from ..orchestration import models as _orch_models  # noqa: F401
    from ..preferences import models as _pref_models  # noqa: F401
    from ..publish import models as _pub_models  # noqa: F401
    from ..rbac import models as _rbac_models  # noqa: F401
    from ..workflow import models as _wf_models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    _migrate()


# Columns added to existing tables after their first release. SQLModel's
# ``create_all`` never alters existing tables, so we add missing columns
# in-place (SQLite ``ADD COLUMN``) to avoid losing the user's data.
_ADDED_COLUMNS: dict[str, dict[str, str]] = {
    "knowledge_base": {
        "chunk_strategy": "VARCHAR DEFAULT 'general'",
        "index_method": "VARCHAR DEFAULT 'keyword'",
        "kg_type": "VARCHAR DEFAULT ''",
        "kg_credential_id": "VARCHAR DEFAULT ''",
        "kg_model": "VARCHAR DEFAULT ''",
    },
    "knowledge_document": {
        "triple_count": "INTEGER DEFAULT 0",
    },
    "knowledge_chunk": {
        "parent_id": "VARCHAR DEFAULT ''",
        "is_parent": "BOOLEAN DEFAULT 0",
        "embedding": "JSON",
    },
}


def _migrate() -> None:
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, columns in _ADDED_COLUMNS.items():
            if table not in existing_tables:
                continue
            present = {col["name"] for col in inspector.get_columns(table)}
            for name, ddl in columns.items():
                if name not in present:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a database session."""
    with Session(engine) as session:
        yield session
