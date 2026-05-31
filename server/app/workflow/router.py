"""REST endpoints for workflow CRUD and execution."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..ontology.db import get_session
from .engine import WorkflowEngine
from .models import Workflow

router = APIRouter(prefix="/admin/workflows", tags=["workflow"])


class WorkflowIn(BaseModel):
    name: str = ""
    description: str = ""
    icon: str = "lucide:workflow"
    graph: dict[str, Any] | None = None
    enabled: bool = True


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    icon: str | None = None
    graph: dict[str, Any] | None = None
    enabled: bool | None = None


class RunIn(BaseModel):
    inputs: dict[str, Any] = Field(default_factory=dict)


@router.get("/")
def list_workflows(session: Session = Depends(get_session)) -> dict:
    rows = list(session.exec(select(Workflow)))
    return {"items": rows, "total": len(rows)}


@router.post("/")
def create_workflow(body: WorkflowIn, session: Session = Depends(get_session)) -> Workflow:
    wf = Workflow(**body.model_dump(exclude_none=True))
    session.add(wf)
    session.commit()
    session.refresh(wf)
    return wf


@router.get("/{workflow_id}")
def get_workflow(workflow_id: str, session: Session = Depends(get_session)) -> Workflow:
    wf = session.get(Workflow, workflow_id)
    if wf is None:
        raise HTTPException(status_code=404, detail="Workflow not found.")
    return wf


@router.patch("/{workflow_id}")
def update_workflow(
    workflow_id: str,
    body: WorkflowUpdate,
    session: Session = Depends(get_session),
) -> Workflow:
    wf = session.get(Workflow, workflow_id)
    if wf is None:
        raise HTTPException(status_code=404, detail="Workflow not found.")
    for key, value in body.model_dump(exclude_none=True).items():
        setattr(wf, key, value)
    wf.updated_at = datetime.utcnow()
    session.add(wf)
    session.commit()
    session.refresh(wf)
    return wf


@router.delete("/{workflow_id}")
def delete_workflow(workflow_id: str, session: Session = Depends(get_session)) -> dict:
    wf = session.get(Workflow, workflow_id)
    if wf is not None:
        session.delete(wf)
        session.commit()
    return {"ok": True}


@router.post("/{workflow_id}/run")
async def run_workflow(
    workflow_id: str,
    body: RunIn,
    session: Session = Depends(get_session),
    x_user_id: str = Header(default="admin"),
) -> StreamingResponse:
    """Execute a workflow, streaming node/text/finish events as SSE."""
    wf = session.get(Workflow, workflow_id)
    if wf is None:
        raise HTTPException(status_code=404, detail="Workflow not found.")
    engine = WorkflowEngine(wf.graph, session, user_id=x_user_id)
    return StreamingResponse(
        engine.run(body.inputs),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
