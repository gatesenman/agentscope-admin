"""REST API for the RBAC skeleton: users, roles, and current-user lookup."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from ..ontology.db import get_session
from .models import DEFAULT_ROLE, ROLE_CATALOG, User

router = APIRouter(prefix="/admin/rbac", tags=["rbac"])


def _caller(x_user_id: str = Header(default="admin")) -> str:
    return x_user_id


def _validate_role(role: str) -> None:
    if role not in ROLE_CATALOG:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown role '{role}'. Valid: {list(ROLE_CATALOG)}",
        )


def _serialize(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "enabled": user.enabled,
        "permissions": ROLE_CATALOG.get(user.role, {}).get("permissions", []),
        "created_at": user.created_at.isoformat(),
        "updated_at": user.updated_at.isoformat(),
    }


class UserCreate(BaseModel):
    username: str
    display_name: str = ""
    role: str = DEFAULT_ROLE
    enabled: bool = True


class UserUpdate(BaseModel):
    display_name: str | None = None
    role: str | None = None
    enabled: bool | None = None


@router.get("/roles", summary="List the role catalog")
def list_roles() -> dict:
    return {
        "items": [
            {"name": name, "label": meta["label"], "permissions": meta["permissions"]}
            for name, meta in ROLE_CATALOG.items()
        ],
    }


@router.get("/me", summary="Resolve the current caller's identity and role")
def whoami(
    session: Session = Depends(get_session),
    caller: str = Depends(_caller),
) -> dict:
    user = session.exec(
        select(User).where(User.username == caller),
    ).first()
    if user is None:
        # Unknown header identity: report a default viewer profile.
        return {
            "username": caller,
            "display_name": caller,
            "role": DEFAULT_ROLE,
            "enabled": True,
            "permissions": ROLE_CATALOG[DEFAULT_ROLE]["permissions"],
            "registered": False,
        }
    return {**_serialize(user), "registered": True}


@router.get("/users", summary="List console members")
def list_users(session: Session = Depends(get_session)) -> dict:
    users = session.exec(select(User).order_by(User.created_at)).all()
    return {"items": [_serialize(u) for u in users]}


@router.post("/users", summary="Create a console member")
def create_user(
    body: UserCreate,
    session: Session = Depends(get_session),
) -> dict:
    _validate_role(body.role)
    exists = session.exec(
        select(User).where(User.username == body.username),
    ).first()
    if exists is not None:
        raise HTTPException(status_code=409, detail="Username already exists")
    user = User(**body.model_dump())
    session.add(user)
    session.commit()
    session.refresh(user)
    return _serialize(user)


@router.put("/users/{user_id}", summary="Update a console member")
def update_user(
    user_id: str,
    body: UserUpdate,
    session: Session = Depends(get_session),
) -> dict:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    data = body.model_dump(exclude_unset=True)
    if "role" in data and data["role"] is not None:
        _validate_role(data["role"])
    for key, value in data.items():
        if value is not None:
            setattr(user, key, value)
    user.updated_at = datetime.utcnow()
    session.add(user)
    session.commit()
    session.refresh(user)
    return _serialize(user)


@router.delete("/users/{user_id}", summary="Delete a console member")
def delete_user(
    user_id: str,
    session: Session = Depends(get_session),
) -> dict:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.username == "admin":
        raise HTTPException(
            status_code=400,
            detail="The default admin user cannot be deleted",
        )
    session.delete(user)
    session.commit()
    return {"deleted": True}


def seed_default_admin() -> None:
    """Ensure a default ``admin`` user exists (idempotent)."""
    from ..ontology.db import engine

    with Session(engine) as session:
        exists = session.exec(
            select(User).where(User.username == "admin"),
        ).first()
        if exists is None:
            session.add(
                User(
                    username="admin",
                    display_name="Administrator",
                    role="admin",
                ),
            )
            session.commit()
