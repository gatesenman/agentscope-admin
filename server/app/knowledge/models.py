"""SQLModel tables backing knowledge bases, documents and chunks."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Column
from sqlalchemy import JSON as SAJSON
from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.utcnow()


# Default ingestion pipeline: an ordered list of stages applied to each
# document's raw text. Mirrors Dify's knowledge pipeline (extract -> clean ->
# split -> index) and is editable per knowledge base.
DEFAULT_PIPELINE: list[dict[str, Any]] = [
    {"type": "extract", "name": "提取文本", "config": {}},
    {
        "type": "clean",
        "name": "清洗",
        "config": {"strip": True, "collapse_whitespace": True},
    },
    {
        "type": "split",
        "name": "分块",
        "config": {"chunk_size": 500, "chunk_overlap": 50, "separator": "\n\n"},
    },
    {"type": "index", "name": "索引", "config": {}},
]


class KnowledgeBase(SQLModel, table=True):
    """A collection of documents sharing one ingestion pipeline."""

    __tablename__ = "knowledge_base"

    id: str = Field(default_factory=_uuid, primary_key=True)
    owner_user_id: str = Field(default="admin", index=True)
    name: str = ""
    description: str = ""
    icon: str = "📚"

    # Ordered ingestion pipeline stages (extract / clean / split / index).
    pipeline: list[dict[str, Any]] = Field(
        default_factory=lambda: [dict(s) for s in DEFAULT_PIPELINE],
        sa_column=Column(SAJSON),
    )
    # Default retrieval settings.
    top_k: int = 4
    score_threshold: float = 0.0

    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class Document(SQLModel, table=True):
    """A raw source document belonging to a knowledge base."""

    __tablename__ = "knowledge_document"

    id: str = Field(default_factory=_uuid, primary_key=True)
    kb_id: str = Field(index=True)
    name: str = ""
    # Raw text content as uploaded / pasted.
    content: str = ""
    # ``pending`` -> ``indexed`` -> ``failed``.
    status: str = "pending"
    chunk_count: int = 0
    error: str = ""
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class Chunk(SQLModel, table=True):
    """An indexed text chunk produced by the ingestion pipeline."""

    __tablename__ = "knowledge_chunk"

    id: str = Field(default_factory=_uuid, primary_key=True)
    kb_id: str = Field(index=True)
    document_id: str = Field(index=True)
    seq: int = 0
    content: str = ""
    # Sparse term-frequency vector ``{term: count}`` cached at index time so
    # retrieval avoids re-tokenising every chunk on each query.
    term_freq: dict[str, int] = Field(
        default_factory=dict,
        sa_column=Column(SAJSON),
    )
    created_at: datetime = Field(default_factory=_now)
