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
from .knowledge.router import router as knowledge_router
from .knowledge.tools import knowledge_tools_factory
from .mcp_registry.router import router as mcp_registry_router
from .observability.router import router as observability_router
from .ontology.db import init_db
from .ontology.router import router as ontology_router
from .ontology.tools import ontology_tools_factory
from .preferences.router import router as preferences_router
from .publish.router import router as publish_router
from .rbac.router import router as rbac_router
from .rbac.router import seed_default_admin
from .settings import get_settings
from .workflow.router import router as workflow_router


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

    async def extra_agent_tools(user_id: str, agent_id: str, session_id: str):
        """Combine ontology + knowledge tools for the running agent."""
        tools = await ontology_tools_factory(user_id, agent_id, session_id)
        tools += await knowledge_tools_factory(user_id, agent_id, session_id)
        return tools

    app = create_app(
        storage=storage,
        workspace_manager=workspace_manager,
        extra_agent_tools=extra_agent_tools,
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
    app.include_router(knowledge_router)
    app.include_router(workflow_router)
    app.include_router(mcp_registry_router)
    app.include_router(observability_router)
    app.include_router(rbac_router)
    seed_default_admin()

    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        return {"status": "ok", "service": settings.title, "version": settings.version}

    return app


app = build_app()
