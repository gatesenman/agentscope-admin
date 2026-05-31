"""Knowledge-base retrieval tool injected into AgentScope agents.

Gives a bound agent a ``knowledge_search`` capability that runs TF-IDF
retrieval across the owner's knowledge bases, so agents can ground their
answers in indexed documents (RAG). Auto-allowed like the ontology tools.
"""

from __future__ import annotations

import json
from typing import Any

from agentscope.message import TextBlock, ToolResultState
from agentscope.tool import ToolBase, ToolChunk
from sqlmodel import Session, select

from ..ontology.db import engine
from ..ontology.tools import AllowedFunctionTool
from . import service
from .models import KnowledgeBase


def _text(payload: Any, *, error: bool = False) -> ToolChunk:
    return ToolChunk(
        content=[TextBlock(type="text", text=json.dumps(payload, default=str, ensure_ascii=False))],
        state=ToolResultState.ERROR if error else ToolResultState.SUCCESS,
    )


def build_knowledge_tools(owner_user_id: str) -> list[ToolBase]:
    """Build the knowledge retrieval tool set for one owner."""

    def knowledge_search(query: str, top_k: int = 4) -> ToolChunk:
        """Search the knowledge base(s) for passages relevant to a query.

        Use this to ground answers in indexed documents before responding.

        Args:
            query: Natural-language search query.
            top_k: Maximum number of passages to return.
        """
        with Session(engine) as session:
            kbs = list(
                session.exec(
                    select(KnowledgeBase).where(
                        KnowledgeBase.owner_user_id == owner_user_id,
                    ),
                ),
            )
            hits: list[dict[str, Any]] = []
            for kb in kbs:
                for hit in service.retrieve(session, kb.id, query, top_k=top_k):
                    hits.append(
                        {
                            "knowledge_base": kb.name,
                            "content": hit["content"],
                            "score": hit["score"],
                        },
                    )
        hits.sort(key=lambda h: h["score"], reverse=True)
        return _text({"results": hits[:top_k]})

    return [AllowedFunctionTool(knowledge_search, is_read_only=True)]


async def knowledge_tools_factory(
    user_id: str,
    agent_id: str,
    session_id: str,
) -> list[ToolBase]:
    """``extra_agent_tools`` factory: inject knowledge retrieval tools."""
    with Session(engine) as session:
        has_kb = session.exec(
            select(KnowledgeBase).where(KnowledgeBase.owner_user_id == user_id),
        ).first()
    if has_kb is None:
        return []
    return build_knowledge_tools(user_id)
