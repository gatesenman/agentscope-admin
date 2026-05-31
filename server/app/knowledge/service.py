"""Reusable knowledge-base operations shared by the router, the workflow
engine and the agent tool."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlmodel import Session, delete, select

from . import pipeline
from .models import Chunk, Document, KnowledgeBase


def ingest_document(session: Session, doc: Document, kb: KnowledgeBase) -> Document:
    """Run the KB pipeline over a document and (re)build its chunks."""
    # Drop any previously indexed chunks for this document.
    session.exec(delete(Chunk).where(Chunk.document_id == doc.id))
    try:
        texts = pipeline.run_pipeline(doc.content, kb.pipeline)
        for seq, text in enumerate(texts):
            session.add(
                Chunk(
                    kb_id=kb.id,
                    document_id=doc.id,
                    seq=seq,
                    content=text,
                    term_freq=pipeline.term_freq(text),
                ),
            )
        doc.chunk_count = len(texts)
        doc.status = "indexed"
        doc.error = ""
    except Exception as exc:  # noqa: BLE001 - surface failure on the document
        doc.status = "failed"
        doc.error = str(exc)
        doc.chunk_count = 0
    doc.updated_at = datetime.utcnow()
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return doc


def retrieve(
    session: Session,
    kb_id: str,
    query: str,
    top_k: int | None = None,
    score_threshold: float | None = None,
) -> list[dict[str, Any]]:
    """Return the top matching chunks for ``query`` within a knowledge base."""
    kb = session.get(KnowledgeBase, kb_id)
    if kb is None:
        return []
    rows = list(session.exec(select(Chunk).where(Chunk.kb_id == kb_id)))
    chunks = [
        {
            "id": c.id,
            "document_id": c.document_id,
            "seq": c.seq,
            "content": c.content,
            "term_freq": c.term_freq,
        }
        for c in rows
    ]
    return pipeline.rank(
        query,
        chunks,
        top_k=top_k if top_k is not None else kb.top_k,
        score_threshold=(
            score_threshold if score_threshold is not None else kb.score_threshold
        ),
    )
