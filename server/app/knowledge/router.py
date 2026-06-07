"""REST endpoints for knowledge bases, documents and retrieval."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, delete, func, select

from ..ontology.db import get_session
from . import service
from .models import (
    Chunk,
    Document,
    KnowledgeBase,
    KnowledgeTriple,
    build_pipeline,
)

router = APIRouter(prefix="/admin/knowledge-bases", tags=["knowledge"])


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #
class KnowledgeBaseIn(BaseModel):
    name: str = ""
    description: str = ""
    icon: str = "lucide:book-open"
    chunk_strategy: str = "general"
    index_method: str = "keyword"
    kg_type: str = ""
    kg_credential_id: str = ""
    kg_model: str = ""
    qa_type: str = ""
    qa_credential_id: str = ""
    qa_model: str = ""
    pipeline: list[dict[str, Any]] | None = None
    top_k: int = 4
    score_threshold: float = 0.0


class KnowledgeBaseUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    icon: str | None = None
    chunk_strategy: str | None = None
    index_method: str | None = None
    kg_type: str | None = None
    kg_credential_id: str | None = None
    kg_model: str | None = None
    qa_type: str | None = None
    qa_credential_id: str | None = None
    qa_model: str | None = None
    pipeline: list[dict[str, Any]] | None = None
    top_k: int | None = None
    score_threshold: float | None = None


class DocumentIn(BaseModel):
    name: str = ""
    content: str = ""


class RetrieveIn(BaseModel):
    query: str
    top_k: int | None = None
    score_threshold: float | None = None
    method: str | None = None


# --------------------------------------------------------------------------- #
# Knowledge bases
# --------------------------------------------------------------------------- #
@router.get("/")
def list_kbs(session: Session = Depends(get_session)) -> dict:
    rows = list(session.exec(select(KnowledgeBase)))
    items = []
    for kb in rows:
        doc_count = session.exec(
            select(func.count()).select_from(Document).where(Document.kb_id == kb.id),
        ).one()
        chunk_count = session.exec(
            select(func.count()).select_from(Chunk).where(Chunk.kb_id == kb.id),
        ).one()
        items.append({"kb": kb, "doc_count": doc_count, "chunk_count": chunk_count})
    return {"items": items, "total": len(items)}


@router.post("/")
def create_kb(body: KnowledgeBaseIn, session: Session = Depends(get_session)) -> KnowledgeBase:
    data = body.model_dump(exclude_none=True)
    # Derive the pipeline from the chosen strategy + method unless one was
    # supplied explicitly (so the orchestration UI always reflects the method).
    if data.get("pipeline") is None:
        data["pipeline"] = build_pipeline(
            data.get("chunk_strategy", "general"),
            data.get("index_method", "keyword"),
        )
    kb = KnowledgeBase(**data)
    session.add(kb)
    session.commit()
    session.refresh(kb)
    return kb


@router.get("/{kb_id}")
def get_kb(kb_id: str, session: Session = Depends(get_session)) -> KnowledgeBase:
    kb = session.get(KnowledgeBase, kb_id)
    if kb is None:
        raise HTTPException(status_code=404, detail="Knowledge base not found.")
    return kb


@router.patch("/{kb_id}")
def update_kb(
    kb_id: str,
    body: KnowledgeBaseUpdate,
    session: Session = Depends(get_session),
) -> KnowledgeBase:
    kb = session.get(KnowledgeBase, kb_id)
    if kb is None:
        raise HTTPException(status_code=404, detail="Knowledge base not found.")
    updates = body.model_dump(exclude_none=True)
    for key, value in updates.items():
        setattr(kb, key, value)
    # If the strategy or method changed and no explicit pipeline was provided,
    # regenerate the pipeline so it stays consistent with the method.
    if ("chunk_strategy" in updates or "index_method" in updates) and "pipeline" not in updates:
        kb.pipeline = build_pipeline(kb.chunk_strategy, kb.index_method)
    kb.updated_at = datetime.utcnow()
    session.add(kb)
    session.commit()
    session.refresh(kb)
    return kb


@router.delete("/{kb_id}")
def delete_kb(kb_id: str, session: Session = Depends(get_session)) -> dict:
    kb = session.get(KnowledgeBase, kb_id)
    if kb is not None:
        session.exec(delete(Chunk).where(Chunk.kb_id == kb_id))
        session.exec(delete(KnowledgeTriple).where(KnowledgeTriple.kb_id == kb_id))
        session.exec(delete(Document).where(Document.kb_id == kb_id))
        session.delete(kb)
        session.commit()
    return {"ok": True}


@router.post("/{kb_id}/reindex")
def reindex_all(kb_id: str, session: Session = Depends(get_session)) -> dict:
    """Re-run the (possibly changed) pipeline over every document in the KB."""
    kb = session.get(KnowledgeBase, kb_id)
    if kb is None:
        raise HTTPException(status_code=404, detail="Knowledge base not found.")
    docs = list(session.exec(select(Document).where(Document.kb_id == kb_id)))
    for doc in docs:
        service.ingest_document(session, doc, kb)
    return {"ok": True, "reindexed": len(docs)}


# --------------------------------------------------------------------------- #
# Documents
# --------------------------------------------------------------------------- #
@router.get("/{kb_id}/documents")
def list_documents(kb_id: str, session: Session = Depends(get_session)) -> dict:
    rows = list(
        session.exec(
            select(Document).where(Document.kb_id == kb_id).order_by(Document.created_at),
        ),
    )
    return {"items": rows, "total": len(rows)}


@router.post("/{kb_id}/documents")
def add_document(
    kb_id: str,
    body: DocumentIn,
    session: Session = Depends(get_session),
) -> Document:
    kb = session.get(KnowledgeBase, kb_id)
    if kb is None:
        raise HTTPException(status_code=404, detail="Knowledge base not found.")
    doc = Document(kb_id=kb_id, name=body.name or "untitled", content=body.content)
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return service.ingest_document(session, doc, kb)


@router.post("/{kb_id}/documents/{doc_id}/reindex")
def reindex_document(
    kb_id: str,
    doc_id: str,
    session: Session = Depends(get_session),
) -> Document:
    kb = session.get(KnowledgeBase, kb_id)
    doc = session.get(Document, doc_id)
    if kb is None or doc is None:
        raise HTTPException(status_code=404, detail="Not found.")
    return service.ingest_document(session, doc, kb)


@router.delete("/{kb_id}/documents/{doc_id}")
def delete_document(kb_id: str, doc_id: str, session: Session = Depends(get_session)) -> dict:
    doc = session.get(Document, doc_id)
    if doc is not None:
        session.exec(delete(Chunk).where(Chunk.document_id == doc_id))
        session.delete(doc)
        session.commit()
    return {"ok": True}


@router.get("/{kb_id}/chunks")
def list_chunks(
    kb_id: str,
    document_id: str | None = None,
    session: Session = Depends(get_session),
) -> dict:
    stmt = select(Chunk).where(Chunk.kb_id == kb_id)
    if document_id:
        stmt = stmt.where(Chunk.document_id == document_id)
    rows = list(session.exec(stmt.order_by(Chunk.document_id, Chunk.seq)))
    return {
        "items": [
            {
                "id": c.id,
                "document_id": c.document_id,
                "seq": c.seq,
                "content": c.content,
                "answer": c.answer,
                "is_parent": c.is_parent,
            }
            for c in rows
        ],
        "total": len(rows),
    }


# --------------------------------------------------------------------------- #
# Retrieval
# --------------------------------------------------------------------------- #
@router.post("/{kb_id}/retrieve")
def retrieve(
    kb_id: str,
    body: RetrieveIn,
    session: Session = Depends(get_session),
) -> dict:
    hits = service.retrieve(
        session,
        kb_id,
        body.query,
        top_k=body.top_k,
        score_threshold=body.score_threshold,
        method=body.method,
    )
    return {
        "items": [
            {
                "id": h["id"],
                "document_id": h["document_id"],
                "seq": h["seq"],
                "content": h["content"],
                "answer": h.get("answer", ""),
                "score": h["score"],
                "context": h.get("context", ""),
                "triples": h.get("triples", []),
            }
            for h in hits
        ],
        "total": len(hits),
    }


@router.get("/{kb_id}/triples")
def list_triples(
    kb_id: str,
    document_id: str | None = None,
    session: Session = Depends(get_session),
) -> dict:
    """List the knowledge-graph triples extracted for a KB (graph index)."""
    stmt = select(KnowledgeTriple).where(KnowledgeTriple.kb_id == kb_id)
    if document_id:
        stmt = stmt.where(KnowledgeTriple.document_id == document_id)
    rows = list(session.exec(stmt))
    return {
        "items": [
            {
                "id": t.id,
                "subject": t.subject,
                "predicate": t.predicate,
                "object": t.object,
                "document_id": t.document_id,
                "chunk_id": t.chunk_id,
            }
            for t in rows
        ],
        "total": len(rows),
    }
