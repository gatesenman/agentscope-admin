"""SQLModel table backing the persistent MCP server registry."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Column
from sqlalchemy import JSON as SAJSON
from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.utcnow()


class McpServer(SQLModel, table=True):
    """A reusable MCP server definition.

    Maps onto AgentScope's ``MCPClient`` (``StdioMCPConfig`` /
    ``HttpMCPConfig``). ``transport`` selects which set of fields is relevant:
    ``stdio`` uses ``command`` / ``args`` / ``env``; ``http`` uses ``url`` /
    ``headers`` / ``timeout``.
    """

    __tablename__ = "mcp_server"

    id: str = Field(default_factory=_uuid, primary_key=True)
    owner_user_id: str = Field(default="admin", index=True)
    name: str = ""
    description: str = ""

    # "stdio" | "http"
    transport: str = "stdio"

    # stdio transport
    command: str = ""
    args: list[str] = Field(default_factory=list, sa_column=Column(SAJSON))
    env: dict[str, str] = Field(default_factory=dict, sa_column=Column(SAJSON))

    # http transport
    url: str = ""
    headers: dict[str, str] = Field(
        default_factory=dict,
        sa_column=Column(SAJSON),
    )
    timeout: float | None = None

    # Whether the connection is stateful. STDIO must be stateful; HTTP may be
    # either. Mirrors ``MCPClient.is_stateful``.
    is_stateful: bool = True

    # Optional tool allow/deny lists and per-call timeout.
    enable_tools: list[str] = Field(
        default_factory=list,
        sa_column=Column(SAJSON),
    )
    disable_tools: list[str] = Field(
        default_factory=list,
        sa_column=Column(SAJSON),
    )
    execution_timeout: float | None = None

    # When enabled, the server is auto-attached to sessions started from the
    # console for any agent.
    enabled: bool = True

    # Last health-check result (populated by the test endpoint).
    last_status: str = "unknown"  # unknown | healthy | unhealthy
    last_checked_at: datetime | None = None
    last_error: str = ""

    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    def to_mcp_client_payload(self) -> dict[str, Any]:
        """Render this row into AgentScope's ``MCPClient`` request body."""
        if self.transport == "http":
            mcp_config: dict[str, Any] = {"type": "http_mcp", "url": self.url}
            if self.headers:
                mcp_config["headers"] = self.headers
            if self.timeout is not None:
                mcp_config["timeout"] = self.timeout
        else:
            mcp_config = {"type": "stdio_mcp", "command": self.command}
            if self.args:
                mcp_config["args"] = self.args
            if self.env:
                mcp_config["env"] = self.env

        payload: dict[str, Any] = {
            "name": self.name,
            "is_stateful": self.is_stateful,
            "mcp_config": mcp_config,
        }
        if self.enable_tools:
            payload["enable_tools"] = self.enable_tools
        if self.disable_tools:
            payload["disable_tools"] = self.disable_tools
        if self.execution_timeout is not None:
            payload["execution_timeout"] = self.execution_timeout
        return payload
