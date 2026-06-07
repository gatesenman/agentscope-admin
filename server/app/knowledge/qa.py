"""Q&A segmentation index helper (Dify "Q&A 模式").

At ingest time an LLM turns each base chunk into question/answer pairs. The
question becomes the chunk's indexed/searchable content and the answer is kept
as the grounded context returned on a hit. This boosts retrieval precision for
FAQ-style content where users phrase queries as questions.
"""

from __future__ import annotations

import json
import re
from typing import Any

from ..settings import get_settings

_settings = get_settings()

_QA_PROMPT = (
    "You generate Q&A pairs for a retrieval knowledge base. Read the TEXT and "
    "write the most useful question/answer pairs a user might ask, answered "
    "strictly from the TEXT. Return ONLY a compact JSON array of objects with "
    'keys "question" and "answer". Use the language of the TEXT. Produce at '
    "most {max_pairs} pairs. No prose, no markdown.\n\nTEXT:\n{text}"
)


def _parse_pairs(raw: str, max_pairs: int) -> list[dict[str, str]]:
    """Best-effort parse of the model's JSON Q&A array."""
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
        q = str(item.get("question", "")).strip()
        a = str(item.get("answer", "")).strip()
        if q and a:
            out.append({"question": q, "answer": a})
        if len(out) >= max_pairs:
            break
    return out


async def _extract_async(
    text: str,
    qa_type: str,
    credential_id: str,
    model_name: str,
    user_id: str,
    max_pairs: int,
) -> list[dict[str, str]]:
    from agentscope.app.storage import ChatModelConfig, RedisStorage
    from agentscope.app._service._model import get_model
    from agentscope.message import Msg

    prompt = _QA_PROMPT.format(max_pairs=max_pairs, text=text[:4000])
    messages = [Msg(name="user", role="user", content=[{"type": "text", "text": prompt}])]
    cfg = ChatModelConfig(
        type=qa_type,
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
        return _parse_pairs("".join(out), max_pairs)


def extract_qa_pairs(
    text: str,
    qa_type: str,
    credential_id: str,
    model_name: str,
    user_id: str = "admin",
    max_pairs: int = 5,
) -> list[dict[str, str]]:
    """Synchronous wrapper around the async LLM Q&A extraction.

    Returns ``[]`` if no extraction model is configured or extraction fails,
    so document ingestion never hard-fails on Q&A generation.
    """
    import asyncio

    if not (qa_type and credential_id and model_name):
        return []
    try:
        return asyncio.run(
            _extract_async(text, qa_type, credential_id, model_name, user_id, max_pairs),
        )
    except Exception:  # noqa: BLE001 - Q&A extraction is best-effort
        return []
