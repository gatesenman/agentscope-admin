"""Application settings."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    """Backend configuration, overridable via environment variables."""

    model_config = SettingsConfigDict(env_prefix="AGENTSCOPE_ADMIN_", extra="ignore")

    title: str = "AgentScope Admin API"
    version: str = "0.1.0"

    # Redis (AgentScope storage backend)
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str | None = None

    # Ontology persistence (SQLite)
    ontology_db_url: str = f"sqlite:///{DATA_DIR / 'ontology.db'}"

    # Per-agent local workspaces
    workspace_dir: str = str(DATA_DIR / "workspaces")

    # CORS
    cors_origins: list[str] = ["*"]


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    os.makedirs(get_settings_workspace_dir(), exist_ok=True)
    return Settings()


def get_settings_workspace_dir() -> str:
    """Resolve the workspace dir without instantiating settings twice."""
    return os.environ.get(
        "AGENTSCOPE_ADMIN_WORKSPACE_DIR",
        str(DATA_DIR / "workspaces"),
    )
