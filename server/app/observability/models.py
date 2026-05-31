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
