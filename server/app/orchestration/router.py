"""REST endpoints for multi-agent orchestration CRUD and execution."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..ontology.db import get_session
from .engine import OrchestrationEngine
from .models import Orchestration

router = APIRouter(prefix="/admin/orchestrations", tags=["orchestration"])

PATTERNS = [
    {"value": "sequential", "label": "顺序流水线"},
    {"value": "parallel", "label": "并行执行"},
    {"value": "aggregation", "label": "并行聚合"},
    {"value": "router", "label": "路由分发"},
    {"value": "supervisor", "label": "主管-工人"},
    {"value": "handoff", "label": "交接 (Swarm)"},
]


class OrchestrationIn(BaseModel):
    name: str = ""
    description: str = ""
    icon: str = "lucide:network"
    pattern: str = "sequential"
    config: dict[str, Any] | None = None
    enabled: bool = True


class OrchestrationUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    icon: str | None = None
    pattern: str | None = None
    config: dict[str, Any] | None = None
    enabled: bool | None = None


class RunIn(BaseModel):
    query: str = Field(default="")


@router.get("/patterns")
def list_patterns() -> dict:
    return {"items": PATTERNS}


@router.get("/")
def list_orchestrations(session: Session = Depends(get_session)) -> dict:
    rows = list(session.exec(select(Orchestration)))
    return {"items": rows, "total": len(rows)}


@router.post("/")
def create_orchestration(
    body: OrchestrationIn,
    session: Session = Depends(get_session),
) -> Orchestration:
    orch = Orchestration(**body.model_dump(exclude_none=True))
    session.add(orch)
    session.commit()
    session.refresh(orch)
    return orch


@router.get("/{orchestration_id}")
def get_orchestration(
    orchestration_id: str,
    session: Session = Depends(get_session),
) -> Orchestration:
    orch = session.get(Orchestration, orchestration_id)
    if orch is None:
        raise HTTPException(status_code=404, detail="Orchestration not found.")
    return orch


@router.patch("/{orchestration_id}")
def update_orchestration(
    orchestration_id: str,
    body: OrchestrationUpdate,
    session: Session = Depends(get_session),
) -> Orchestration:
    orch = session.get(Orchestration, orchestration_id)
    if orch is None:
        raise HTTPException(status_code=404, detail="Orchestration not found.")
    for key, value in body.model_dump(exclude_none=True).items():
        setattr(orch, key, value)
    orch.updated_at = datetime.utcnow()
    session.add(orch)
    session.commit()
    session.refresh(orch)
    return orch


@router.delete("/{orchestration_id}")
def delete_orchestration(
    orchestration_id: str,
    session: Session = Depends(get_session),
) -> dict:
    orch = session.get(Orchestration, orchestration_id)
    if orch is not None:
        session.delete(orch)
        session.commit()
    return {"ok": True}


@router.post("/{orchestration_id}/run")
async def run_orchestration(
    orchestration_id: str,
    body: RunIn,
    session: Session = Depends(get_session),
    x_user_id: str = Header(default="admin"),
) -> StreamingResponse:
    """Execute an orchestration, streaming member events as SSE."""
    orch = session.get(Orchestration, orchestration_id)
    if orch is None:
        raise HTTPException(status_code=404, detail="Orchestration not found.")
    engine = OrchestrationEngine(orch.pattern, orch.config, user_id=x_user_id)
    return StreamingResponse(
        engine.run(body.query),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
