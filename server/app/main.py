"""Application entrypoint.

Builds a FastAPI app directly on top of AgentScope's own app layer and
augments it with the ontology and dashboard routers.
"""

from __future__ import annotations

from agentscope.app import create_app
from agentscope.app._manager import LocalWorkspaceManager
from agentscope.app.storage import RedisStorage
from fastapi.middleware.cors import CORSMiddleware

from .agent_profile.router import router as agent_profile_router
from .compat_auth.router import router as auth_router
from .dashboard.router import router as dashboard_router
from .ontology.db import init_db
from .ontology.router import router as ontology_router
from .ontology.tools import ontology_tools_factory
from .preferences.router import router as preferences_router
from .publish.router import router as publish_router
from .settings import get_settings


def build_app():
    """Create and configure the FastAPI application."""
    settings = get_settings()

    storage = RedisStorage(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        password=settings.redis_password,
    )
    workspace_manager = LocalWorkspaceManager(basedir=settings.workspace_dir)

    app = create_app(
        storage=storage,
        workspace_manager=workspace_manager,
        extra_agent_tools=ontology_tools_factory,
        title=settings.title,
        version=settings.version,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Initialise ontology storage and mount our routers.
    init_db()
    app.include_router(ontology_router)
    app.include_router(dashboard_router)
    app.include_router(auth_router)
    app.include_router(preferences_router)
    app.include_router(agent_profile_router)
    app.include_router(publish_router)

    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        return {"status": "ok", "service": settings.title, "version": settings.version}

    return app


app = build_app()
