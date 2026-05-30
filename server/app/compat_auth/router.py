"""Compatibility auth router (vben demo flow).

Returns the ``{ "code": 0, "data": ... }`` envelope that the demo
``requestClient`` interceptor expects.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["auth-compat"])

# Static placeholder token. The AgentScope routers authenticate via the
# ``X-User-ID`` header, so this token only needs to satisfy the vben shell.
ADMIN_TOKEN = "agentscope-admin-token"  # noqa: S105 - not a real secret


def _ok(data: Any) -> dict:
    return {"code": 0, "data": data}


class LoginBody(BaseModel):
    username: str | None = None
    password: str | None = None


@router.post("/auth/login")
async def login(_body: LoginBody) -> dict:
    """Accept any credentials and return a static access token."""
    return _ok({"accessToken": ADMIN_TOKEN})


@router.post("/auth/refresh")
async def refresh() -> dict:
    return _ok(ADMIN_TOKEN)


@router.post("/auth/logout")
async def logout() -> dict:
    return _ok("")


@router.get("/auth/codes")
async def codes() -> dict:
    """Return permission codes (full access for the single admin user)."""
    return _ok(["AC_100100", "AC_100110", "AC_100120", "AC_100010"])


@router.get("/user/info")
async def user_info() -> dict:
    return _ok(
        {
            "userId": "admin",
            "username": "admin",
            "realName": "Administrator",
            "avatar": "",
            "desc": "AgentScope Admin",
            "homePath": "/agentscope/dashboard",
            "roles": ["super"],
            "token": ADMIN_TOKEN,
        },
    )


@router.get("/menu/all")
async def menu_all() -> dict:
    """Frontend access mode builds menus from routes, so return an empty list."""
    return _ok([])
