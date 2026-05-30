"""SQLModel table storing per-agent model defaults and metadata."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Column
from sqlalchemy import JSON as SAJSON
from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.utcnow()


class AgentProfile(SQLModel, table=True):
    """Admin-level configuration attached to an AgentScope agent.

    Keyed by ``agent_id`` (1:1 with an AgentScope agent). Holds the default
    model binding used when a session is created from the console, the
    generation parameters, an optional fallback model, and free-form business
    metadata (description / tags).
    """

    __tablename__ = "agent_profile"

    agent_id: str = Field(primary_key=True)

    # Default chat model used to seed new sessions.
    default_provider: str | None = None
    default_credential_id: str | None = None
    default_model: str | None = None

    # Generation parameters (temperature, top_p, max_tokens, ...).
    parameters: dict[str, Any] = Field(default_factory=dict, sa_column=Column(SAJSON))

    # Optional fallback model used when the primary one fails.
    fallback_provider: str | None = None
    fallback_credential_id: str | None = None
    fallback_model: str | None = None

    # Whether streaming responses are enabled in the console by default.
    stream: bool = True

    # Tool-execution permission mode applied to sessions started for this
    # agent. Mirrors AgentScope ``PermissionMode`` / Claude Agent SDK
    # ``permission_mode``: default | accept_edits | explore | bypass | dont_ask.
    permission_mode: str = "default"

    # Business metadata.
    description: str = ""
    tags: list[str] = Field(default_factory=list, sa_column=Column(SAJSON))

    updated_at: datetime = Field(default_factory=_now)
