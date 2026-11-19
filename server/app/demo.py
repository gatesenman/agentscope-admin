"""Demo/mock API mode: admin pages can render without Redis or a live AgentScope."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def demo_payloads() -> dict:
    return {
        "connection": {
            "mode": "demo",
            "backend": "mock",
            "redis": False,
            "agentscope": False,
            "banner": "Demo mode: the real AgentScope/Redis backend is not connected.",
            "banner_zh": "演示模式：未连接真实的 AgentScope / Redis 后端。",
        },
        "agents": {
            "items": [
                {
                    "agent_id": "demo-researcher",
                    "default_model": "demo-model",
                    "description": "Offline sample agent for the admin console.",
                }
            ],
            "total": 1,
        },
        "observability": {
            "usage": {"recorded": False, "model_name": "demo-model", "calls": 0},
            "recent": [],
        },
        "orchestration": {
            "workflows": [{"id": "demo-flow", "name": "Sample orchestration", "status": "idle"}],
            "total": 1,
        },
    }


def build_demo_app() -> FastAPI:
    payloads = demo_payloads()
    app = FastAPI(title="AgentScope Admin (demo)", version="demo")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/admin/status")
    def status():
        return payloads["connection"]

    @app.get("/admin/agent-profiles/")
    def agents():
        return payloads["agents"]

    @app.get("/admin/usage/summary")
    def usage_summary():
        return payloads["observability"]["usage"]

    @app.get("/admin/orchestration/workflows")
    def workflows():
        return payloads["orchestration"]

    return app


app = build_demo_app()
