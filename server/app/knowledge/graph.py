"""Semantic knowledge-graph index method (GraphRAG-style).

At ingest time an LLM extracts ``(subject, predicate, object)`` triples from
each chunk; the triples form a lightweight knowledge graph. At retrieval time
the query is matched against triple entities and the chunks that produced the
matching edges are returned, optionally falling back to keyword ranking.
"""

from __future__ import annotations

import json
import re
from typing import Any

from ..settings import get_settings
from . import pipeline

_settings = get_settings()

_EXTRACT_PROMPT = (
    "You are a knowledge-graph extractor. Read the TEXT and extract factual "
    "relationships as triples. Return ONLY a compact JSON array of objects "
    'with keys "subject", "predicate", "object". Use the language of the '
    "TEXT for entity names. Extract at most {max_triples} of the most "
    "salient triples. No prose, no markdown.\n\nTEXT:\n{text}"
)


def _parse_triples(raw: str, max_triples: int) -> list[dict[str, str]]:
    """Best-effort parse of the model's JSON triple array."""
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    out: list[dict[str, str]] = []
    for item in data if isinstance(data, list) else []:
        if not isinstance(item, dict):
            continue
        s = str(item.get("subject", "")).strip()
        p = str(item.get("predicate", "")).strip()
        o = str(item.get("object", "")).strip()
        if s and o:
            out.append({"subject": s, "predicate": p, "object": o})
        if len(out) >= max_triples:
            break
    return out


async def _extract_async(
    text: str,
    kg_type: str,
    credential_id: str,
    model_name: str,
    user_id: str,
    max_triples: int,
) -> list[dict[str, str]]:
    from agentscope.app.storage import ChatModelConfig, RedisStorage
    from agentscope.app._service._model import get_model
    from agentscope.message import Msg

    prompt = _EXTRACT_PROMPT.format(max_triples=max_triples, text=text[:4000])
    messages = [Msg(name="user", role="user", content=[{"type": "text", "text": prompt}])]
    cfg = ChatModelConfig(
        type=kg_type,
        credential_id=credential_id,
        model=model_name,
        parameters={"temperature": 0.0},
    )
    async with RedisStorage(
        host=_settings.redis_host,
        port=_settings.redis_port,
        db=_settings.redis_db,
        password=_settings.redis_password,
    ) as storage:
        model = await get_model(user_id, cfg, storage)
        model.stream = False
        resp = await model(messages=messages)
        out: list[str] = []
        for block in resp.content or []:
            if isinstance(block, dict) and block.get("type") == "text":
                out.append(block.get("text", ""))
            elif getattr(block, "type", None) == "text":
                out.append(getattr(block, "text", ""))
        return _parse_triples("".join(out), max_triples)


def extract_triples(
    text: str,
    kg_type: str,
    credential_id: str,
    model_name: str,
    user_id: str = "admin",
    max_triples: int = 8,
) -> list[dict[str, str]]:
    """Synchronous wrapper around the async LLM triple extraction.

    Returns ``[]`` if no extraction model is configured or extraction fails,
    so document ingestion never hard-fails on graph extraction.
    """
    import asyncio

    if not (kg_type and credential_id and model_name):
        return []
    try:
        return asyncio.run(
            _extract_async(text, kg_type, credential_id, model_name, user_id, max_triples),
        )
    except Exception:  # noqa: BLE001 - graph extraction is best-effort
        return []


def graph_rank(
    query: str,
    triples: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
    top_k: int = 4,
    score_threshold: float = 0.0,
) -> list[dict[str, Any]]:
    """Rank chunks by how many of their extracted triples match the query.

    A triple matches when its subject or object shares tokens with the query.
    Chunks are scored by matched-triple count, then blended with a small
    keyword signal so the result stays sensible when the graph is sparse.
    """
    q_tokens = set(pipeline.tokenize(query))
    if not q_tokens:
        return []
    by_chunk: dict[str, list[dict[str, str]]] = {}
    chunk_score: dict[str, float] = {}
    for tri in triples:
        cid = tri.get("chunk_id", "")
        entity_tokens = set(pipeline.tokenize(f"{tri.get('subject', '')} {tri.get('object', '')}"))
        overlap = len(q_tokens & entity_tokens)
        if overlap > 0:
            chunk_score[cid] = chunk_score.get(cid, 0.0) + overlap
            by_chunk.setdefault(cid, []).append(
                {
                    "subject": tri.get("subject", ""),
                    "predicate": tri.get("predicate", ""),
                    "object": tri.get("object", ""),
                },
            )

    kw = {c["id"]: c["score"] for c in pipeline.rank(query, chunks, top_k=len(chunks) or 1)}
    by_id = {c["id"]: c for c in chunks}
    max_graph = max(chunk_score.values()) if chunk_score else 1.0

    scored: list[dict[str, Any]] = []
    candidate_ids = set(chunk_score) | set(kw)
    for cid in candidate_ids:
        chunk = by_id.get(cid)
        if chunk is None:
            continue
        graph_component = (chunk_score.get(cid, 0.0) / max_graph) if max_graph else 0.0
        score = 0.7 * graph_component + 0.3 * kw.get(cid, 0.0)
        if score >= score_threshold and score > 0:
            scored.append(
                {**chunk, "score": round(score, 4), "triples": by_chunk.get(cid, [])},
            )
    scored.sort(key=lambda c: c["score"], reverse=True)
    return scored[:top_k]
