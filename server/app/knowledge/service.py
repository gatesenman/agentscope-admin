"""Reusable knowledge-base operations shared by the router, the workflow
engine and the agent tool. Ingestion and retrieval branch on the knowledge
base's ``chunk_strategy`` and ``index_method``."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlmodel import Session, delete, select

from . import graph, pipeline
from .models import (
    CHUNK_PARENT_CHILD,
    INDEX_GRAPH,
    INDEX_HYBRID,
    INDEX_VECTOR,
    Chunk,
    Document,
    KnowledgeBase,
    KnowledgeTriple,
)


def _embed_dim(kb: KnowledgeBase) -> int:
    for stage in kb.pipeline:
        if stage.get("type") == "embed":
            return int(stage.get("config", {}).get("dim", 256))
    return 256


def _max_triples(kb: KnowledgeBase) -> int:
    for stage in kb.pipeline:
        if stage.get("type") == "build_graph":
            return int(stage.get("config", {}).get("max_triples_per_chunk", 8))
    return 8


def ingest_document(session: Session, doc: Document, kb: KnowledgeBase) -> Document:
    """Run the KB pipeline over a document and (re)build its chunks, embeddings
    and (for the knowledge-graph method) triples."""
    # Drop any previously indexed artefacts for this document.
    session.exec(delete(Chunk).where(Chunk.document_id == doc.id))
    session.exec(delete(KnowledgeTriple).where(KnowledgeTriple.document_id == doc.id))
    try:
        want_embed = kb.index_method in (INDEX_VECTOR, INDEX_HYBRID)
        dim = _embed_dim(kb)
        chunk_rows: list[Chunk] = []

        if kb.chunk_strategy == CHUNK_PARENT_CHILD:
            parents = pipeline.run_pipeline_parent_child(doc.content, kb.pipeline)
            seq = 0
            for parent in parents:
                parent_chunk = Chunk(
                    kb_id=kb.id,
                    document_id=doc.id,
                    seq=seq,
                    content=parent["content"],
                    is_parent=True,
                    term_freq=pipeline.term_freq(parent["content"]),
                )
                session.add(parent_chunk)
                session.flush()
                seq += 1
                for child_text in parent["children"]:
                    child = Chunk(
                        kb_id=kb.id,
                        document_id=doc.id,
                        seq=seq,
                        content=child_text,
                        parent_id=parent_chunk.id,
                        term_freq=pipeline.term_freq(child_text),
                        embedding=pipeline.embed(child_text, dim) if want_embed else [],
                    )
                    session.add(child)
                    chunk_rows.append(child)
                    seq += 1
            indexed = len(chunk_rows)
        else:
            texts = pipeline.run_pipeline(doc.content, kb.pipeline)
            for seq, text in enumerate(texts):
                row = Chunk(
                    kb_id=kb.id,
                    document_id=doc.id,
                    seq=seq,
                    content=text,
                    term_freq=pipeline.term_freq(text),
                    embedding=pipeline.embed(text, dim) if want_embed else [],
                )
                session.add(row)
                chunk_rows.append(row)
            indexed = len(chunk_rows)

        triple_count = 0
        if kb.index_method == INDEX_GRAPH:
            session.flush()
            for row in chunk_rows:
                triples = graph.extract_triples(
                    row.content,
                    kb.kg_type,
                    kb.kg_credential_id,
                    kb.kg_model,
                    user_id=kb.owner_user_id,
                    max_triples=_max_triples(kb),
                )
                for tri in triples:
                    session.add(
                        KnowledgeTriple(
                            kb_id=kb.id,
                            document_id=doc.id,
                            chunk_id=row.id,
                            subject=tri["subject"],
                            predicate=tri["predicate"],
                            object=tri["object"],
                        ),
                    )
                    triple_count += 1

        doc.chunk_count = indexed
        doc.triple_count = triple_count
        doc.status = "indexed"
        doc.error = ""
    except Exception as exc:  # noqa: BLE001 - surface failure on the document
        doc.status = "failed"
        doc.error = str(exc)
        doc.chunk_count = 0
        doc.triple_count = 0
    doc.updated_at = datetime.utcnow()
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return doc


def _retrievable_chunks(session: Session, kb_id: str) -> list[dict[str, Any]]:
    """Return chunks eligible for matching. For parent-child indexes only the
    child chunks are matched (parents are context holders)."""
    rows = list(session.exec(select(Chunk).where(Chunk.kb_id == kb_id)))
    has_children = any(c.parent_id for c in rows)
    out = []
    for c in rows:
        if has_children and c.is_parent:
            continue
        out.append(
            {
                "id": c.id,
                "document_id": c.document_id,
                "seq": c.seq,
                "content": c.content,
                "parent_id": c.parent_id,
                "term_freq": c.term_freq,
                "embedding": c.embedding,
            },
        )
    return out


def _expand_parents(session: Session, kb_id: str, hits: list[dict[str, Any]]) -> None:
    """Attach the parent chunk's full text as ``context`` for child hits."""
    parent_ids = {h.get("parent_id") for h in hits if h.get("parent_id")}
    if not parent_ids:
        return
    parents = {
        p.id: p.content
        for p in session.exec(select(Chunk).where(Chunk.id.in_(parent_ids)))  # type: ignore[attr-defined]
    }
    for h in hits:
        pid = h.get("parent_id")
        if pid and pid in parents:
            h["context"] = parents[pid]


def retrieve(
    session: Session,
    kb_id: str,
    query: str,
    top_k: int | None = None,
    score_threshold: float | None = None,
    method: str | None = None,
) -> list[dict[str, Any]]:
    """Return the top matching chunks for ``query`` within a knowledge base,
    dispatching on the configured (or overridden) index method."""
    kb = session.get(KnowledgeBase, kb_id)
    if kb is None:
        return []
    chunks = _retrievable_chunks(session, kb_id)
    k = top_k if top_k is not None else kb.top_k
    threshold = score_threshold if score_threshold is not None else kb.score_threshold
    use_method = method or kb.index_method
    dim = _embed_dim(kb)

    if use_method == INDEX_VECTOR:
        hits = pipeline.vector_rank(query, chunks, top_k=k, score_threshold=threshold, dim=dim)
    elif use_method == INDEX_HYBRID:
        hits = pipeline.hybrid_rank(query, chunks, top_k=k, score_threshold=threshold, dim=dim)
    elif use_method == INDEX_GRAPH:
        rows = session.exec(select(KnowledgeTriple).where(KnowledgeTriple.kb_id == kb_id))
        triples = [
            {"chunk_id": t.chunk_id, "subject": t.subject, "predicate": t.predicate, "object": t.object}
            for t in rows
        ]
        hits = graph.graph_rank(query, triples, chunks, top_k=k, score_threshold=threshold)
    else:
        hits = pipeline.rank(query, chunks, top_k=k, score_threshold=threshold)

    _expand_parents(session, kb_id, hits)
    return hits
