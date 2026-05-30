"""Storage model for per-user frontend preferences."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON as SAJSON
from sqlalchemy import Column
from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now()


class UserPreferences(SQLModel, table=True):
    """A user's persisted vben preference state (full preferences object)."""

    __tablename__ = "user_preferences"

    user_id: str = Field(primary_key=True)
    data: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(SAJSON),
    )
    updated_at: datetime = Field(default_factory=_now)
