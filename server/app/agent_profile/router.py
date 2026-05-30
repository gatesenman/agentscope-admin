"""REST endpoints for per-agent model defaults and metadata."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..ontology.db import get_session
from .models import AgentProfile

router = APIRouter(prefix="/admin/agent-profiles", tags=["agent-profile"])


class AgentProfileIn(BaseModel):
    """Upsert body for an agent profile."""

    default_provider: str | None = None
    default_credential_id: str | None = None
    default_model: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    fallback_provider: str | None = None
    fallback_credential_id: str | None = None
    fallback_model: str | None = None
    stream: bool = True
    permission_mode: str = "default"
    description: str = ""
    tags: list[str] = Field(default_factory=list)


@router.get("/")
def list_profiles(session: Session = Depends(get_session)) -> dict:
    """Return every stored agent profile."""
    rows = list(session.exec(select(AgentProfile)))
    return {"items": rows, "total": len(rows)}


@router.get("/{agent_id}")
def get_profile(
    agent_id: str,
    session: Session = Depends(get_session),
) -> AgentProfile | None:
    """Return the profile for one agent (``null`` if not configured)."""
    return session.get(AgentProfile, agent_id)


@router.put("/{agent_id}")
def upsert_profile(
    agent_id: str,
    body: AgentProfileIn,
    session: Session = Depends(get_session),
) -> AgentProfile:
    """Create or update the profile for one agent."""
    profile = session.get(AgentProfile, agent_id)
    if profile is None:
        profile = AgentProfile(agent_id=agent_id, **body.model_dump())
    else:
        for key, value in body.model_dump().items():
            setattr(profile, key, value)
        profile.updated_at = datetime.utcnow()
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


@router.delete("/{agent_id}")
def delete_profile(
    agent_id: str,
    session: Session = Depends(get_session),
) -> dict:
    """Delete the profile for one agent (no-op if missing)."""
    profile = session.get(AgentProfile, agent_id)
    if profile is not None:
        session.delete(profile)
        session.commit()
    return {"ok": True}
