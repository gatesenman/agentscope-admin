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
import time
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator

import httpx
import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..agent_profile.models import AgentProfile
from ..observability.models import TraceSpan, UsageLog
from ..ontology.db import engine, get_session
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
    icon: str = "lucide:bot"
    opening_statement: str = ""
    suggested_questions: list[str] = Field(default_factory=list)
    allowed_origins: list[str] = Field(default_factory=lambda: ["*"])
    rate_limit_per_min: int = 60
    moderation_keywords: list[str] = Field(default_factory=list)
    moderation_reply: str = ""
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
    moderation_keywords: list[str] | None = None
    moderation_reply: str | None = None
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
        icon=body.icon or "lucide:bot",
        opening_statement=body.opening_statement,
        suggested_questions=body.suggested_questions,
        allowed_origins=body.allowed_origins or ["*"],
        rate_limit_per_min=body.rate_limit_per_min,
        moderation_keywords=body.moderation_keywords,
        moderation_reply=body.moderation_reply,
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
        model_name = ""
        if model_config is not None:
            model_name = model_config.get("model_name", "")
        tracer = _TraceCollector(app, session_id, model_name)
        try:
            async with client.stream(
                "POST",
                "/chat/",
                json=chat_body,
                headers=headers,
            ) as stream:
                async for line in stream.aiter_lines():
                    if line:
                        _capture_usage_frame(
                            line, app, session_id, model_name,
                        )
                        tracer.feed(line)
                        yield f"{line}\n"
                    else:
                        yield "\n"
        finally:
            tracer.flush()


class _TraceCollector:
    """Builds execution-chain spans from relayed SSE frames (server side).

    Mirrors the playground tracer so published-app traffic also shows up in
    the per-session trace timeline.
    """

    def __init__(self, app: PublishedApp, session_id: str, model_name: str):
        self._app = app
        self._session_id = session_id
        self._model_name = model_name
        self._run_id = f"app-{uuid.uuid4().hex[:12]}"
        self._spans: list[dict[str, Any]] = []
        self._tools: dict[str, dict[str, Any]] = {}
        self._reply = ""
        self._last = time.perf_counter()

    @staticmethod
    def _tool_kind(name: str) -> str:
        low = (name or "").lower()
        if "ontolog" in low:
            return "ontology"
        if any(k in low for k in ("knowledge", "retriev", "rag")):
            return "knowledge"
        return "tool"

    def feed(self, line: str) -> None:
        if not line.startswith("data:"):
            return
        try:
            event = json.loads(line[5:].strip())
        except (ValueError, TypeError):
            return
        etype = event.get("type")
        now = time.perf_counter()
        if etype == "MODEL_CALL_END":
            self._spans.append(
                {
                    "kind": "model",
                    "name": self._model_name or "model",
                    "model_name": self._model_name,
                    "input_tokens": int(event.get("input_tokens", 0) or 0),
                    "output_tokens": int(event.get("output_tokens", 0) or 0),
                    "duration_ms": int((now - self._last) * 1000),
                },
            )
            self._last = now
        elif etype == "TOOL_CALL_START":
            tid = event.get("tool_call_id", "")
            name = event.get("tool_call_name", "tool")
            span = {
                "kind": self._tool_kind(name),
                "name": name,
                "input_text": "",
                "output_text": "",
                "start": now,
            }
            self._tools[tid] = span
            self._spans.append(span)
            self._last = now
        elif etype == "TOOL_CALL_DELTA":
            span = self._tools.get(event.get("tool_call_id", ""))
            if span is not None:
                span["input_text"] = span.get("input_text", "") + (
                    event.get("delta", "") or ""
                )
        elif etype == "TOOL_RESULT_TEXT_DELTA":
            span = self._tools.get(event.get("tool_call_id", ""))
            if span is not None:
                span["output_text"] = span.get("output_text", "") + (
                    event.get("delta", "") or ""
                )
                span["duration_ms"] = int((now - span.get("start", now)) * 1000)
        elif etype == "TEXT_BLOCK_DELTA":
            self._reply += event.get("delta", "") or ""

    def flush(self) -> None:
        if self._reply.strip():
            self._spans.append(
                {
                    "kind": "reply",
                    "name": "回复",
                    "output_text": self._reply,
                    "duration_ms": 0,
                },
            )
        if not self._spans:
            return
        with Session(engine) as db:
            for i, s in enumerate(self._spans):
                db.add(
                    TraceSpan(
                        owner_user_id=self._app.owner_user_id,
                        agent_id=self._app.agent_id,
                        session_id=self._session_id,
                        run_id=self._run_id,
                        source="app",
                        seq=i,
                        kind=s.get("kind", "tool"),
                        name=s.get("name", ""),
                        status="ok",
                        model_name=s.get("model_name", ""),
                        input_text=str(s.get("input_text", ""))[:8000],
                        output_text=str(s.get("output_text", ""))[:8000],
                        input_tokens=int(s.get("input_tokens", 0)),
                        output_tokens=int(s.get("output_tokens", 0)),
                        duration_ms=int(s.get("duration_ms", 0)),
                    ),
                )
            db.commit()


def _capture_usage_frame(
    line: str,
    app: PublishedApp,
    session_id: str,
    model_name: str,
) -> None:
    """Record token usage from a relayed ``MODEL_CALL_END`` SSE frame."""
    if not line.startswith("data:"):
        return
    try:
        event = json.loads(line[5:].strip())
    except (ValueError, TypeError):
        return
    if event.get("type") != "MODEL_CALL_END":
        return
    with Session(engine) as db:
        db.add(
            UsageLog(
                owner_user_id=app.owner_user_id,
                agent_id=app.agent_id,
                session_id=session_id,
                source="app",
                model_name=model_name or event.get("model_name", ""),
                input_tokens=int(event.get("input_tokens", 0) or 0),
                output_tokens=int(event.get("output_tokens", 0) or 0),
            ),
        )
        db.commit()


def _origin_allowed(app: PublishedApp, origin: str | None) -> bool:
    if not app.allowed_origins or "*" in app.allowed_origins:
        return True
    if origin is None:
        return True
    return origin in app.allowed_origins


_redis_client: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.Redis(
            host=_settings.redis_host,
            port=_settings.redis_port,
            db=_settings.redis_db,
            password=_settings.redis_password,
            decode_responses=True,
        )
    return _redis_client


async def _enforce_rate_limit(app: PublishedApp) -> None:
    """Per-minute fixed-window rate limit for a published app.

    Counts all chat requests (hosted Web App, embed, and API key surface) for
    the app within the current minute and rejects with HTTP 429 once
    ``rate_limit_per_min`` is exceeded. ``rate_limit_per_min <= 0`` disables the
    limit. The counter lives in Redis so it is shared across workers; if Redis
    is unreachable we fail open rather than block legitimate traffic on a
    limiter-infrastructure problem.
    """
    limit = app.rate_limit_per_min or 0
    if limit <= 0:
        return
    window = int(time.time()) // 60
    key = f"ratelimit:{app.id}:{window}"
    try:
        client = _get_redis()
        count = await client.incr(key)
        if count == 1:
            await client.expire(key, 60)
    except Exception:
        return
    if count > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please retry shortly.",
        )


_DEFAULT_MODERATION_REPLY = "抱歉，您的输入包含不被允许的内容，我无法回答。"


def _moderation_reply(app: PublishedApp, query: str) -> str | None:
    """Input guardrail: return a canned reply if ``query`` hits a blocked word.

    Performs a case-insensitive substring match against ``moderation_keywords``.
    Returns ``None`` when the guardrail is disabled (no keywords) or the message
    is clean, so the caller proceeds to the model as usual.
    """
    keywords = app.moderation_keywords or []
    if not keywords:
        return None
    haystack = (query or "").lower()
    for word in keywords:
        needle = (word or "").strip().lower()
        if needle and needle in haystack:
            return app.moderation_reply or _DEFAULT_MODERATION_REPLY
    return None


async def _blocked_reply_events(reply: str) -> AsyncGenerator[str, None]:
    """Emit a single SSE text frame for a guardrail-blocked message.

    Uses the same ``TEXT_BLOCK_DELTA`` frame the WebApp/embed client renders and
    ``_collect_answer`` accumulates, so a blocked turn behaves like a normal
    (instant) reply without ever invoking the model.
    """
    frame = {
        "type": "TEXT_BLOCK_DELTA",
        "block_id": "moderation",
        "delta": reply,
    }
    yield f"data: {json.dumps(frame, ensure_ascii=False)}\n\n"


_EMBED_JS = """\
/* AgentScope Admin embeddable chat bubble (cross-platform, no external deps). */
(function () {
  var cfg = window.AGENTSCOPE_APP || {};
  if (!cfg.url) {
    console.error("AGENTSCOPE_APP.url is required");
    return;
  }
  var ICON_CHAT =
    '<svg viewBox="0 0 24 24" width="26" height="26" fill="none" ' +
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" ' +
    'stroke-linejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 ' +
    '8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 ' +
    '8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 ' +
    '8.48 0 0 1 8 8v.5z"></path></svg>';
  var ICON_CLOSE =
    '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" ' +
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" ' +
    'stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line>' +
    '<line x1="6" y1="6" x2="18" y2="18"></line></svg>';
  var open = false;
  var mobile = window.matchMedia("(max-width: 640px)");
  var btn = document.createElement("div");
  btn.innerHTML = ICON_CHAT;
  Object.assign(btn.style, {
    position: "fixed",
    right: "max(16px, env(safe-area-inset-right))",
    bottom: "max(16px, env(safe-area-inset-bottom))",
    width: "56px", height: "56px", borderRadius: "50%",
    background: cfg.color || "#2563eb", color: "#fff", display: "flex",
    alignItems: "center", justifyContent: "center", cursor: "pointer",
    boxShadow: "0 6px 20px rgba(0,0,0,.25)", zIndex: 2147483646
  });
  var frame = document.createElement("iframe");
  frame.src = cfg.url;
  frame.allow = "microphone";
  frame.title = cfg.title || "Chat";
  document.body.appendChild(frame);
  document.body.appendChild(btn);

  /* Layout differs by viewport: floating panel on desktop, near-fullscreen
   * sheet on phones so the app is usable on every device. */
  function layout() {
    var base = {
      position: "fixed", border: "0", zIndex: 2147483646,
      background: "#fff", boxShadow: "0 12px 40px rgba(0,0,0,.3)",
      display: open ? "block" : "none"
    };
    if (mobile.matches) {
      Object.assign(base, {
        left: "0", right: "0", top: "0", bottom: "0",
        width: "100%", height: "100%", borderRadius: "0"
      });
    } else {
      Object.assign(base, {
        left: "auto", top: "auto", right: "24px", bottom: "92px",
        width: cfg.width || "400px", height: cfg.height || "640px",
        maxWidth: "calc(100vw - 48px)", maxHeight: "calc(100vh - 120px)",
        borderRadius: "14px"
      });
    }
    Object.assign(frame.style, base);
    /* The button is appended after the iframe, so it always paints above it
     * (same z-index) and stays tappable. On a phone the panel is fullscreen,
     * so move the close button to the top-right to avoid the composer. */
    if (open && mobile.matches) {
      btn.style.top = "max(12px, env(safe-area-inset-top))";
      btn.style.bottom = "auto";
    } else {
      btn.style.top = "auto";
      btn.style.bottom = "max(16px, env(safe-area-inset-bottom))";
    }
  }
  function toggle() {
    open = !open;
    btn.innerHTML = open ? ICON_CLOSE : ICON_CHAT;
    layout();
  }
  btn.addEventListener("click", toggle);
  (mobile.addEventListener
    ? mobile.addEventListener.bind(mobile, "change")
    : mobile.addListener.bind(mobile))(layout);
  layout();
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
    await _enforce_rate_limit(app)
    conversation_id = body.conversation_id or uuid.uuid4().hex
    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "X-Conversation-Id": conversation_id,
    }
    blocked = _moderation_reply(app, body.query)
    events = (
        _blocked_reply_events(blocked)
        if blocked is not None
        else _proxy_chat_events(app, body.query, conversation_id)
    )
    return StreamingResponse(
        events,
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
    await _enforce_rate_limit(app)
    conversation_id = body.conversation_id or uuid.uuid4().hex

    blocked = _moderation_reply(app, body.query)

    if body.response_mode == "blocking":
        answer = (
            blocked
            if blocked is not None
            else await _collect_answer(app, body.query, conversation_id)
        )
        return JSONResponse(
            {"answer": answer, "conversation_id": conversation_id},
        )

    events = (
        _blocked_reply_events(blocked)
        if blocked is not None
        else _proxy_chat_events(app, body.query, conversation_id)
    )
    return StreamingResponse(
        events,
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
