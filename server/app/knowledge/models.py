"""SQLModel tables backing knowledge bases, documents, chunks and the
knowledge-graph triples produced by the semantic-graph index method."""

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


# Chunking strategies (how a document is segmented).
CHUNK_GENERAL = "general"
CHUNK_PARENT_CHILD = "parent_child"
# Q&A segmentation (Dify "Q&A 模式"): an LLM turns each base chunk into
# question/answer pairs; the question is indexed for retrieval and the answer
# is returned as the grounded context.
CHUNK_QA = "qa"

# Index / retrieval methods (how chunks are indexed and searched).
INDEX_KEYWORD = "keyword"
INDEX_VECTOR = "vector"
INDEX_GRAPH = "knowledge_graph"
INDEX_HYBRID = "hybrid"


def build_pipeline(
    chunk_strategy: str,
    index_method: str,
) -> list[dict[str, Any]]:
    """Derive the ordered ingestion-pipeline stages for the chosen strategy
    and index method. The frontend renders this list as a visual orchestration
    chain, so the stages mirror exactly what ``service.ingest_document`` runs.
    """
    stages: list[dict[str, Any]] = [
        {"type": "extract", "name": "提取文本", "config": {}},
        {
            "type": "clean",
            "name": "清洗",
            "config": {"strip": True, "collapse_whitespace": True},
        },
    ]
    if chunk_strategy == CHUNK_PARENT_CHILD:
        stages.append(
            {
                "type": "split_parent_child",
                "name": "父子分块",
                "config": {
                    "parent_size": 1200,
                    "chunk_size": 400,
                    "chunk_overlap": 40,
                    "separator": "\n\n",
                },
            },
        )
    else:
        stages.append(
            {
                "type": "split",
                "name": "通用分块",
                "config": {
                    "chunk_size": 500,
                    "chunk_overlap": 50,
                    "separator": "\n\n",
                },
            },
        )

    if chunk_strategy == CHUNK_QA:
        stages.append(
            {
                "type": "qa",
                "name": "QA 分块",
                "config": {"max_pairs_per_chunk": 5},
            },
        )

    if index_method in (INDEX_VECTOR, INDEX_HYBRID):
        stages.append(
            {"type": "embed", "name": "向量嵌入", "config": {"dim": 256}},
        )
    if index_method == INDEX_GRAPH:
        stages.append(
            {
                "type": "build_graph",
                "name": "语义知识图谱",
                "config": {"max_triples_per_chunk": 8},
            },
        )
    stages.append({"type": "index", "name": "建立索引", "config": {}})
    return stages


# Backwards-compatible default (general chunking + keyword index).
DEFAULT_PIPELINE: list[dict[str, Any]] = build_pipeline(CHUNK_GENERAL, INDEX_KEYWORD)


class KnowledgeBase(SQLModel, table=True):
    """A collection of documents sharing one ingestion pipeline."""

    __tablename__ = "knowledge_base"

    id: str = Field(default_factory=_uuid, primary_key=True)
    owner_user_id: str = Field(default="admin", index=True)
    name: str = ""
    description: str = ""
    icon: str = "lucide:book-open"

    # How documents are segmented and indexed.
    chunk_strategy: str = CHUNK_GENERAL
    index_method: str = INDEX_KEYWORD

    # Credential + model used by the knowledge-graph extractor (LLM). Only
    # required when ``index_method == knowledge_graph``.
    kg_type: str = ""
    kg_credential_id: str = ""
    kg_model: str = ""

    # Credential + model used by the Q&A extractor (LLM). Only required when
    # ``chunk_strategy == qa``.
    qa_type: str = ""
    qa_credential_id: str = ""
    qa_model: str = ""

    # Ordered ingestion pipeline stages, derived from the strategy + method
    # but persisted so the orchestration UI can display (and tweak) them.
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
    triple_count: int = 0
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
    # Parent-child chunking: child chunks point at their parent chunk; the
    # parent's full text is returned as retrieval context. Empty for general.
    parent_id: str = Field(default="", index=True)
    is_parent: bool = False
    # Q&A segmentation: ``content`` holds the generated question (what is
    # matched at retrieval time) and ``answer`` the grounded answer returned
    # on a hit. Empty for the other chunk strategies.
    answer: str = Field(default="")
    # Sparse term-frequency vector ``{term: count}`` cached at index time so
    # retrieval avoids re-tokenising every chunk on each query.
    term_freq: dict[str, int] = Field(
        default_factory=dict,
        sa_column=Column(SAJSON),
    )
    # Dense local embedding (only populated for vector / hybrid indexes).
    embedding: list[float] = Field(
        default_factory=list,
        sa_column=Column(SAJSON),
    )
    created_at: datetime = Field(default_factory=_now)


class KnowledgeTriple(SQLModel, table=True):
    """A (subject, predicate, object) edge extracted from a chunk by the
    knowledge-graph index method."""

    __tablename__ = "knowledge_triple"

    id: str = Field(default_factory=_uuid, primary_key=True)
    kb_id: str = Field(index=True)
    document_id: str = Field(index=True)
    chunk_id: str = Field(default="", index=True)
    subject: str = ""
    predicate: str = ""
    object: str = ""
    created_at: datetime = Field(default_factory=_now)
