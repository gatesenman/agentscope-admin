"""Router exposing GET/PUT endpoints for per-user frontend preferences."""

from __future__ import annotations

from typing import Any

from agentscope.app._deps import get_current_user_id
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlmodel import Session

from ..ontology.db import engine
from .models import UserPreferences

router = APIRouter(prefix="/preferences", tags=["preferences"])


class PreferencesBody(BaseModel):
    """Request body wrapping the full vben preferences object."""

    data: dict[str, Any] = Field(default_factory=dict)


@router.get("/")
def get_preferences(user_id: str = Depends(get_current_user_id)) -> dict:
    """Return the saved preferences for the current user (``{}`` if none)."""
    with Session(engine) as session:
        row = session.get(UserPreferences, user_id)
        return {"data": row.data if row else {}}


@router.put("/")
def put_preferences(
    body: PreferencesBody,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Persist (upsert) the full preferences object for the current user."""
    with Session(engine) as session:
        row = session.get(UserPreferences, user_id)
        if row is None:
            row = UserPreferences(user_id=user_id, data=body.data)
        else:
            row.data = body.data
        session.add(row)
        session.commit()
    return {"ok": True}
