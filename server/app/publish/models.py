"""SQLModel tables backing agent publishing.

A :class:`PublishedApp` is an agent frozen into a publicly reachable
application (Dify-style): it carries a stable public ``token`` (used for the
hosted Web App URL and embed snippets) plus a snapshot of the runtime config
(model + parameters + permission mode) so the published service stays stable
even if the underlying agent profile changes. Access via the REST API is
authenticated with one or more :class:`AppApiKey` records.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import Column
from sqlalchemy import JSON as SAJSON
from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.utcnow()


def _uuid() -> str:
    return uuid4().hex


class PublishedApp(SQLModel, table=True):
    """A published, externally reachable instance of an agent."""

    __tablename__ = "published_app"

    id: str = Field(default_factory=_uuid, primary_key=True)
    # Public, URL-safe token used in the Web App URL and embed snippets.
    token: str = Field(default_factory=_uuid, index=True, unique=True)
    owner_user_id: str = Field(default="admin", index=True)
    agent_id: str = Field(index=True)

    # Branding shown on the hosted Web App.
    name: str = ""
    description: str = ""
    icon: str = "lucide:bot"
    opening_statement: str = ""
    suggested_questions: list[str] = Field(
        default_factory=list,
        sa_column=Column(SAJSON),
    )

    # Frozen runtime config snapshot (taken from the agent profile at publish
    # time). Keeps the live service stable and self-contained.
    chat_model_type: str | None = None
    chat_model_credential_id: str | None = None
    chat_model_name: str | None = None
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(SAJSON),
    )
    permission_mode: str = "default"

    # Access control.
    enabled: bool = True
    allowed_origins: list[str] = Field(
        default_factory=lambda: ["*"],
        sa_column=Column(SAJSON),
    )
    rate_limit_per_min: int = 60
    # Content moderation (input guardrail): if the user message contains any of
    # these case-insensitive keywords the app returns ``moderation_reply``
    # instead of invoking the model. Empty list disables the guardrail.
    moderation_keywords: list[str] = Field(
        default_factory=list,
        sa_column=Column(SAJSON),
    )
    moderation_reply: str = ""

    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class AppApiKey(SQLModel, table=True):
    """An API key granting REST access to a published app."""

    __tablename__ = "app_api_key"

    id: str = Field(default_factory=_uuid, primary_key=True)
    app_id: str = Field(index=True)
    name: str = "default"
    # First chars of the key, safe to display (e.g. ``app-sk-1a2b3c``).
    key_prefix: str = ""
    # SHA-256 of the full key; the plaintext is shown to the user only once.
    key_hash: str = ""
    revoked: bool = False
    last_used_at: datetime | None = None
    created_at: datetime = Field(default_factory=_now)
