"""SQLModel table + role catalog for the RBAC skeleton."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.utcnow()


# Fixed role catalog. Permission codes mirror the frontend access codes so the
# vben shell can gate routes/actions by role. Kept small and explicit on
# purpose — this is a skeleton, not a full policy engine.
ROLE_CATALOG: dict[str, dict] = {
    "admin": {
        "label": "Administrator",
        "permissions": [
            "agent:manage",
            "ontology:manage",
            "credential:manage",
            "publish:manage",
            "user:manage",
            "observability:view",
        ],
    },
    "editor": {
        "label": "Editor",
        "permissions": [
            "agent:manage",
            "ontology:manage",
            "publish:manage",
            "observability:view",
        ],
    },
    "viewer": {
        "label": "Viewer",
        "permissions": ["observability:view"],
    },
}

DEFAULT_ROLE = "viewer"


class User(SQLModel, table=True):
    """A console member.

    ``username`` doubles as the ``owner_user_id`` used to scope domain data, so
    it must be unique. Identity is still asserted via the ``X-User-ID`` header
    (no password auth in this skeleton).
    """

    __tablename__ = "rbac_user"

    id: str = Field(default_factory=_uuid, primary_key=True)
    username: str = Field(index=True, unique=True)
    display_name: str = ""
    role: str = DEFAULT_ROLE  # admin | editor | viewer
    enabled: bool = True
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
