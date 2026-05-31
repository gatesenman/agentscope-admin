"""SQLModel table backing multi-agent orchestrations.

An orchestration ties together several *members* (agent personas, each backed
by a model config and an instruction) under a *pattern* that decides how they
collaborate. Supported patterns mirror the industry consensus:

- ``sequential``   — a pipeline; each member refines the previous output.
- ``parallel``     — fan-out the same task to every member concurrently.
- ``aggregation``  — parallel fan-out, then an aggregator LLM synthesises one
  answer from all member outputs.
- ``router``       — a router LLM picks the single best member for the task.
- ``supervisor``   — a supervisor LLM iteratively delegates to worker members
  (supervisor-worker / orchestrator-worker) until it produces a final answer.
- ``handoff``      — members hand control to one another (swarm style) until a
  member signals completion or ``max_rounds`` is reached.
"""

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


def _default_config() -> dict[str, Any]:
    """A minimal two-member sequential pipeline used for new orchestrations."""
    return {
        "members": [
            {
                "id": "m1",
                "name": "研究员",
                "role": "researcher",
                "instruction": "针对用户问题进行分析，给出关键事实与要点。",
                "credential_id": "",
                "type": "",
                "model": "",
                "parameters": {},
            },
            {
                "id": "m2",
                "name": "撰写者",
                "role": "writer",
                "instruction": "基于上一步的要点，撰写一段清晰、专业的最终回答。",
                "credential_id": "",
                "type": "",
                "model": "",
                "parameters": {},
            },
        ],
        # router / supervisor / aggregation use this LLM as the coordinator.
        "coordinator": {
            "credential_id": "",
            "type": "",
            "model": "",
            "parameters": {},
            "instruction": "",
        },
        "max_rounds": 4,
    }


class Orchestration(SQLModel, table=True):
    """A persisted multi-agent collaboration definition."""

    __tablename__ = "orchestration"

    id: str = Field(default_factory=_uuid, primary_key=True)
    owner_user_id: str = Field(default="admin", index=True)
    name: str = ""
    description: str = ""
    icon: str = "lucide:network"
    pattern: str = "sequential"

    config: dict[str, Any] = Field(
        default_factory=_default_config,
        sa_column=Column(SAJSON),
    )
    enabled: bool = True

    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
