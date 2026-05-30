"""Dashboard statistics, aggregated across AgentScope storage and ontology."""

from __future__ import annotations

from agentscope.app._deps import get_current_user_id, get_storage
from agentscope.app.storage import StorageBase
from fastapi import APIRouter, Depends
from sqlmodel import Session, func, select

from ..ontology.db import engine
from ..ontology.models import (
    ActionType,
    LinkType,
    ObjectInstance,
    ObjectType,
    Ontology,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats")
async def get_stats(
    user_id: str = Depends(get_current_user_id),
    storage: StorageBase = Depends(get_storage),
) -> dict:
    """Return aggregate counts for the dashboard overview cards."""
    agents = await storage.list_agents(user_id)
    credentials = await storage.list_credentials(user_id)
    schedules = await storage.list_schedules(user_id)

    session_count = 0
    for agent in agents:
        try:
            sessions = await storage.list_sessions(user_id, agent.id)
            session_count += len(sessions)
        except Exception:  # noqa: BLE001 - agent may have no sessions yet
            continue

    with Session(engine) as db:
        ontology_count = db.exec(select(func.count()).select_from(Ontology)).one()
        object_type_count = db.exec(select(func.count()).select_from(ObjectType)).one()
        link_type_count = db.exec(select(func.count()).select_from(LinkType)).one()
        action_type_count = db.exec(select(func.count()).select_from(ActionType)).one()
        object_count = db.exec(select(func.count()).select_from(ObjectInstance)).one()

    return {
        "agents": len(agents),
        "credentials": len(credentials),
        "schedules": len(schedules),
        "sessions": session_count,
        "ontologies": ontology_count,
        "object_types": object_type_count,
        "link_types": link_type_count,
        "action_types": action_type_count,
        "objects": object_count,
    }
