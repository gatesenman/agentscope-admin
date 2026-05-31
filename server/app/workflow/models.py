"""SQLModel table backing visual workflows."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Column
from sqlalchemy import JSON as SAJSON
from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.utcnow()


def _default_graph() -> dict[str, Any]:
    """A minimal start -> answer graph used for new workflows."""
    return {
        "nodes": [
            {
                "id": "start",
                "type": "start",
                "position": {"x": 80, "y": 160},
                "data": {
                    "title": "开始",
                    "variables": [
                        {"name": "query", "label": "用户输入", "type": "string"},
                    ],
                },
            },
            {
                "id": "answer",
                "type": "answer",
                "position": {"x": 520, "y": 160},
                "data": {"title": "回复", "answer": "{{start.query}}"},
            },
        ],
        "edges": [{"id": "e1", "source": "start", "target": "answer"}],
    }


class Workflow(SQLModel, table=True):
    """A persisted node/edge orchestration graph."""

    __tablename__ = "workflow"

    id: str = Field(default_factory=_uuid, primary_key=True)
    owner_user_id: str = Field(default="admin", index=True)
    name: str = ""
    description: str = ""
    icon: str = "🧩"

    graph: dict[str, Any] = Field(default_factory=_default_graph, sa_column=Column(SAJSON))
    enabled: bool = True

    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
