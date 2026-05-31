"""SQLModel table backing token-usage / cost observability."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.utcnow()


class UsageLog(SQLModel, table=True):
    """A single model call's token usage.

    One row per ``MODEL_CALL_END`` event. ``source`` records where the call
    originated so the dashboard can separate interactive debugging from
    published-app traffic.
    """

    __tablename__ = "usage_log"

    id: str = Field(default_factory=_uuid, primary_key=True)
    owner_user_id: str = Field(default="admin", index=True)
    agent_id: str = Field(default="", index=True)
    session_id: str = Field(default="")
    source: str = Field(default="playground")  # playground | app | schedule
    model_name: str = Field(default="")
    input_tokens: int = 0
    output_tokens: int = 0
    created_at: datetime = Field(default_factory=_now, index=True)


class TraceSpan(SQLModel, table=True):
    """One step in an agent run's execution chain.

    Spans are grouped by ``run_id`` (one user turn) and ordered by ``seq``.
    A run is a single request/response cycle that may contain several model
    calls, tool calls, ontology operations and human-confirmation pauses.
    ``kind`` drives how the timeline renders each step.
    """

    __tablename__ = "trace_span"

    id: str = Field(default_factory=_uuid, primary_key=True)
    owner_user_id: str = Field(default="admin", index=True)
    agent_id: str = Field(default="", index=True)
    session_id: str = Field(default="", index=True)
    run_id: str = Field(default="", index=True)
    seq: int = 0
    # model | tool | ontology | knowledge | confirm | reply | error | run
    kind: str = Field(default="model", index=True)
    name: str = Field(default="")
    status: str = Field(default="ok")  # ok | error | rejected | pending
    source: str = Field(default="playground")  # playground | app | schedule
    model_name: str = Field(default="")
    input_text: str = Field(default="")
    output_text: str = Field(default="")
    input_tokens: int = 0
    output_tokens: int = 0
    duration_ms: int = 0
    created_at: datetime = Field(default_factory=_now, index=True)
