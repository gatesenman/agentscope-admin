"""REST endpoints for agent publishing.

Two surfaces:

* ``/admin/published-apps`` — authenticated console CRUD for published apps
  and their API keys (mirrors the rest of the admin API; identity via the
  ``X-User-ID`` header).
* ``/public/apps/{token}`` and ``/v1/apps/{token}`` — the public surface
  consumed by the hosted Web App, embeds, and third-party API callers. Chat
  traffic is proxied to the server's own AgentScope endpoints using the app
  owner's identity, reusing all existing execution + ontology wiring.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..agent_profile.models import AgentProfile
from ..ontology.db import get_session
from ..settings import get_settings
from .models import AppApiKey, PublishedApp

router = APIRouter(tags=["publish"])

_settings = get_settings()


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #
class PublishIn(BaseModel):
    """Create-publish body."""

    agent_id: str
    name: str = ""
    description: str = ""
    icon: str = "🤖"
    opening_statement: str = ""
    suggested_questions: list[str] = Field(default_factory=list)
    allowed_origins: list[str] = Field(default_factory=lambda: ["*"])
    rate_limit_per_min: int = 60
    # Optional explicit model override; when omitted we snapshot the agent
    # profile defaults.
    chat_model_type: str | None = None
    chat_model_credential_id: str | None = None
    chat_model_name: str | None = None
    parameters: dict[str, Any] | None = None
    permission_mode: str | None = None


class PublishUpdate(BaseModel):
    """Patch body for an existing app."""

    name: str | None = None
    description: str | None = None
    icon: str | None = None
    opening_statement: str | None = None
    suggested_questions: list[str] | None = None
    allowed_origins: list[str] | None = None
    rate_limit_per_min: int | None = None
    enabled: bool | None = None
    permission_mode: str | None = None
    # Re-snapshot the model binding when provided.
    chat_model_type: str | None = None
    chat_model_credential_id: str | None = None
    chat_model_name: str | None = None
    parameters: dict[str, Any] | None = None


class ApiKeyIn(BaseModel):
    name: str = "default"


class PublicChatIn(BaseModel):
    """Public chat body (Web App + API)."""

    query: str
    conversation_id: str | None = None
    response_mode: str = "streaming"  # streaming | blocking


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _public_view(app: PublishedApp) -> dict:
    """Metadata safe to expose on the public Web App surface."""
    return {
        "token": app.token,
        "name": app.name,
        "description": app.description,
        "icon": app.icon,
        "opening_statement": app.opening_statement,
        "suggested_questions": app.suggested_questions,
        "enabled": app.enabled,
    }


def _model_config(app: PublishedApp) -> dict | None:
    """Build the AgentScope ``chat_model_config`` from the app snapshot."""
    if not (app.chat_model_credential_id and app.chat_model_name):
        return None
    return {
        "type": app.chat_model_type or "",
        "credential_id": app.chat_model_credential_id,
        "model": app.chat_model_name,
        "parameters": app.parameters or {},
    }


def _get_app_or_404(session: Session, app_id: str, owner: str) -> PublishedApp:
    app = session.get(PublishedApp, app_id)
    if app is None or app.owner_user_id != owner:
        raise HTTPException(status_code=404, detail="Published app not found.")
    return app


# --------------------------------------------------------------------------- #
# Admin CRUD
# --------------------------------------------------------------------------- #
admin = APIRouter(prefix="/admin/published-apps")


def _owner(x_user_id: str = Header(default="admin")) -> str:
    return x_user_id


@admin.get("/")
def list_apps(
    session: Session = Depends(get_session),
    owner: str = Depends(_owner),
) -> dict:
    """List published apps for the caller, with API-key counts."""
    rows = list(
        session.exec(
            select(PublishedApp).where(PublishedApp.owner_user_id == owner),
        ),
    )
    items = []
    for app in rows:
        keys = list(
            session.exec(select(AppApiKey).where(AppApiKey.app_id == app.id)),
        )
        active = sum(1 for k in keys if not k.revoked)
        items.append({"app": app, "key_count": active})
    return {"items": items, "total": len(items)}


@admin.post("/", status_code=status.HTTP_201_CREATED)
def publish_app(
    body: PublishIn,
    session: Session = Depends(get_session),
    owner: str = Depends(_owner),
) -> PublishedApp:
    """Publish an agent as a public app.

    Snapshots the agent profile's default model / parameters / permission mode
    unless explicit overrides are supplied.
    """
    profile = session.get(AgentProfile, body.agent_id)
    app = PublishedApp(
        owner_user_id=owner,
        agent_id=body.agent_id,
        name=body.name or body.agent_id,
        description=body.description,
        icon=body.icon or "🤖",
        opening_statement=body.opening_statement,
        suggested_questions=body.suggested_questions,
        allowed_origins=body.allowed_origins or ["*"],
        rate_limit_per_min=body.rate_limit_per_min,
        chat_model_type=body.chat_model_type
        or (profile.default_provider if profile else None),
        chat_model_credential_id=body.chat_model_credential_id
        or (profile.default_credential_id if profile else None),
        chat_model_name=body.chat_model_name
        or (profile.default_model if profile else None),
        parameters=body.parameters
        if body.parameters is not None
        else (profile.parameters if profile else {}),
        permission_mode=body.permission_mode
        or (profile.permission_mode if profile else "default"),
    )
    session.add(app)
    session.commit()
    session.refresh(app)
    return app


@admin.get("/{app_id}")
def get_app(
    app_id: str,
    session: Session = Depends(get_session),
    owner: str = Depends(_owner),
) -> PublishedApp:
    return _get_app_or_404(session, app_id, owner)


@admin.patch("/{app_id}")
def update_app(
    app_id: str,
    body: PublishUpdate,
    session: Session = Depends(get_session),
    owner: str = Depends(_owner),
) -> PublishedApp:
    app = _get_app_or_404(session, app_id, owner)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(app, key, value)
    app.updated_at = datetime.utcnow()
    session.add(app)
    session.commit()
    session.refresh(app)
    return app


@admin.delete("/{app_id}")
def delete_app(
    app_id: str,
    session: Session = Depends(get_session),
    owner: str = Depends(_owner),
) -> dict:
    app = _get_app_or_404(session, app_id, owner)
    for key in session.exec(select(AppApiKey).where(AppApiKey.app_id == app.id)):
        session.delete(key)
    session.delete(app)
    session.commit()
    return {"ok": True}


@admin.get("/{app_id}/keys")
def list_keys(
    app_id: str,
    session: Session = Depends(get_session),
    owner: str = Depends(_owner),
) -> dict:
    _get_app_or_404(session, app_id, owner)
    rows = list(
        session.exec(select(AppApiKey).where(AppApiKey.app_id == app_id)),
    )
    return {"items": rows, "total": len(rows)}


@admin.post("/{app_id}/keys", status_code=status.HTTP_201_CREATED)
def create_key(
    app_id: str,
    body: ApiKeyIn,
    session: Session = Depends(get_session),
    owner: str = Depends(_owner),
) -> dict:
    """Create an API key. The plaintext key is returned only once."""
    _get_app_or_404(session, app_id, owner)
    raw = f"app-sk-{secrets.token_hex(24)}"
    key = AppApiKey(
        app_id=app_id,
        name=body.name or "default",
        key_prefix=raw[:14],
        key_hash=_hash_key(raw),
    )
    session.add(key)
    session.commit()
    session.refresh(key)
    return {"key": raw, "record": key}


@admin.post("/{app_id}/keys/{key_id}/revoke")
def revoke_key(
    app_id: str,
    key_id: str,
    session: Session = Depends(get_session),
    owner: str = Depends(_owner),
) -> dict:
    _get_app_or_404(session, app_id, owner)
    key = session.get(AppApiKey, key_id)
    if key is None or key.app_id != app_id:
        raise HTTPException(status_code=404, detail="API key not found.")
    key.revoked = True
    session.add(key)
    session.commit()
    return {"ok": True}


router.include_router(admin)


# --------------------------------------------------------------------------- #
# Public surface (Web App + embed + API)
# --------------------------------------------------------------------------- #
def _app_by_token(session: Session, token: str) -> PublishedApp:
    app = session.exec(
        select(PublishedApp).where(PublishedApp.token == token),
    ).first()
    if app is None or not app.enabled:
        raise HTTPException(
            status_code=404,
            detail="Application not found or offline.",
        )
    return app


def _authenticate_key(session: Session, app: PublishedApp, authorization: str) -> None:
    """Validate a ``Bearer <api_key>`` against the app's active keys."""
    token = ""
    if authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing API key.")
    digest = _hash_key(token)
    key = session.exec(
        select(AppApiKey).where(
            AppApiKey.app_id == app.id,
            AppApiKey.key_hash == digest,
            AppApiKey.revoked == False,  # noqa: E712
        ),
    ).first()
    if key is None:
        raise HTTPException(status_code=401, detail="Invalid API key.")
    key.last_used_at = datetime.utcnow()
    session.add(key)
    session.commit()


async def _proxy_chat_events(
    app: PublishedApp,
    query: str,
    conversation_id: str,
) -> AsyncGenerator[str, None]:
    """Create/resume a session for the app and relay AgentScope SSE frames.

    Uses the app owner's identity to call the server's own endpoints so all
    execution, ontology tools, and permission handling are reused.
    """
    base = _settings.internal_base_url
    headers = {"X-User-ID": app.owner_user_id}
    model_config = _model_config(app)
    async with httpx.AsyncClient(base_url=base, timeout=None) as client:
        # 1) Create / resume the session (upsert keyed by workspace_id).
        create_body: dict[str, Any] = {
            "agent_id": app.agent_id,
            "workspace_id": conversation_id,
        }
        if model_config is not None:
            create_body["chat_model_config"] = model_config
        resp = await client.post("/sessions/", json=create_body, headers=headers)
        if resp.status_code >= 400:
            raise HTTPException(status_code=502, detail=resp.text)
        session_id = resp.json()["session_id"]

        # 2) Apply the published permission mode.
        await client.patch(
            f"/sessions/{session_id}",
            params={"agent_id": app.agent_id},
            json={"permission_mode": app.permission_mode},
            headers=headers,
        )

        # 3) Stream the chat reply, relaying frames untouched.
        chat_body = {
            "agent_id": app.agent_id,
            "session_id": session_id,
            "input": {
                "name": "user",
                "role": "user",
                "content": [{"type": "text", "text": query}],
            },
        }
        async with client.stream(
            "POST",
            "/chat/",
            json=chat_body,
            headers=headers,
        ) as stream:
            async for line in stream.aiter_lines():
                if line:
                    yield f"{line}\n"
                else:
                    yield "\n"


def _origin_allowed(app: PublishedApp, origin: str | None) -> bool:
    if not app.allowed_origins or "*" in app.allowed_origins:
        return True
    if origin is None:
        return True
    return origin in app.allowed_origins


_EMBED_JS = """\
/* AgentScope Admin embeddable chat bubble. */
(function () {
  var cfg = window.AGENTSCOPE_APP || {};
  if (!cfg.url) {
    console.error("AGENTSCOPE_APP.url is required");
    return;
  }
  var open = false;
  var btn = document.createElement("div");
  btn.innerHTML = "\\uD83D\\uDCAC";
  Object.assign(btn.style, {
    position: "fixed", right: "24px", bottom: "24px", width: "56px",
    height: "56px", borderRadius: "50%", background: cfg.color || "#2563eb",
    color: "#fff", fontSize: "26px", display: "flex",
    alignItems: "center", justifyContent: "center", cursor: "pointer",
    boxShadow: "0 6px 20px rgba(0,0,0,.25)", zIndex: 2147483646
  });
  var frame = document.createElement("iframe");
  frame.src = cfg.url;
  frame.allow = "microphone";
  Object.assign(frame.style, {
    position: "fixed", right: "24px", bottom: "92px",
    width: cfg.width || "400px", height: cfg.height || "640px",
    maxWidth: "calc(100vw - 48px)", maxHeight: "calc(100vh - 120px)",
    border: "0", borderRadius: "14px", display: "none",
    boxShadow: "0 12px 40px rgba(0,0,0,.3)", zIndex: 2147483646,
    background: "#fff"
  });
  function toggle() {
    open = !open;
    frame.style.display = open ? "block" : "none";
    btn.innerHTML = open ? "\\u2715" : "\\uD83D\\uDCAC";
  }
  btn.addEventListener("click", toggle);
  document.body.appendChild(frame);
  document.body.appendChild(btn);
})();
"""


@router.get("/static/embed.js")
def embed_script() -> Response:
    """Serve the floating chat-bubble loader used by the embed snippet."""
    return Response(content=_EMBED_JS, media_type="application/javascript")


@router.get("/public/apps/{token}")
def public_app_meta(
    token: str,
    session: Session = Depends(get_session),
) -> dict:
    """Public metadata for the hosted Web App (no auth)."""
    return _public_view(_app_by_token(session, token))


@router.post("/public/apps/{token}/chat")
async def public_app_chat(
    token: str,
    body: PublicChatIn,
    request: Request,
    session: Session = Depends(get_session),
) -> StreamingResponse:
    """Streaming chat for the hosted Web App / embed (no API key)."""
    app = _app_by_token(session, token)
    if not _origin_allowed(app, request.headers.get("origin")):
        raise HTTPException(status_code=403, detail="Origin not allowed.")
    conversation_id = body.conversation_id or uuid.uuid4().hex
    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "X-Conversation-Id": conversation_id,
    }
    return StreamingResponse(
        _proxy_chat_events(app, body.query, conversation_id),
        media_type="text/event-stream",
        headers=headers,
    )


@router.post("/v1/apps/{token}/chat-messages")
async def api_chat_messages(
    token: str,
    body: PublicChatIn,
    session: Session = Depends(get_session),
    authorization: str = Header(default=""),
) -> Any:
    """Authenticated REST chat endpoint (Bearer API key).

    ``response_mode=streaming`` returns SSE; ``blocking`` accumulates the
    final answer and returns JSON.
    """
    app = _app_by_token(session, token)
    _authenticate_key(session, app, authorization)
    conversation_id = body.conversation_id or uuid.uuid4().hex

    if body.response_mode == "blocking":
        answer = await _collect_answer(app, body.query, conversation_id)
        return JSONResponse(
            {"answer": answer, "conversation_id": conversation_id},
        )

    return StreamingResponse(
        _proxy_chat_events(app, body.query, conversation_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Conversation-Id": conversation_id,
        },
    )


async def _collect_answer(
    app: PublishedApp,
    query: str,
    conversation_id: str,
) -> str:
    """Drain the SSE stream and return the assistant's text reply.

    Accumulates ``TEXT_BLOCK_DELTA`` deltas grouped by ``block_id`` (the agent
    may emit several text blocks across tool calls) and concatenates them in
    arrival order.
    """
    blocks: dict[str, str] = {}
    order: list[str] = []
    async for frame in _proxy_chat_events(app, query, conversation_id):
        frame = frame.strip()
        if not frame.startswith("data:"):
            continue
        try:
            event = json.loads(frame[5:].strip())
        except json.JSONDecodeError:
            continue
        if event.get("type") == "TEXT_BLOCK_DELTA":
            block_id = event.get("block_id", "")
            if block_id not in blocks:
                blocks[block_id] = ""
                order.append(block_id)
            blocks[block_id] += event.get("delta", "")
    return "".join(blocks[b] for b in order)
