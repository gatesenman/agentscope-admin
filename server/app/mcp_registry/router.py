"""REST endpoints for the persistent MCP server registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from agentscope.mcp import HttpMCPConfig, StdioMCPConfig
from agentscope.mcp._mcp_client import MCPClient
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..ontology.db import get_session
from .models import McpServer

router = APIRouter(prefix="/admin/mcp-servers", tags=["mcp-registry"])


def _owner(x_user_id: str = Header(default="admin")) -> str:
    return x_user_id


class McpServerIn(BaseModel):
    """Create / update body for an MCP server."""

    name: str
    description: str = ""
    transport: str = "stdio"
    command: str = ""
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    url: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    timeout: float | None = None
    is_stateful: bool = True
    enable_tools: list[str] = Field(default_factory=list)
    disable_tools: list[str] = Field(default_factory=list)
    execution_timeout: float | None = None
    enabled: bool = True


def _get_or_404(session: Session, server_id: str, owner: str) -> McpServer:
    row = session.get(McpServer, server_id)
    if row is None or row.owner_user_id != owner:
        raise HTTPException(status_code=404, detail="MCP server not found.")
    return row


@router.get("/")
def list_servers(
    session: Session = Depends(get_session),
    owner: str = Depends(_owner),
) -> dict:
    """List MCP servers owned by the caller."""
    rows = list(
        session.exec(
            select(McpServer).where(McpServer.owner_user_id == owner),
        ),
    )
    return {"items": rows, "total": len(rows)}


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_server(
    body: McpServerIn,
    session: Session = Depends(get_session),
    owner: str = Depends(_owner),
) -> McpServer:
    """Register a new MCP server."""
    row = McpServer(owner_user_id=owner, **body.model_dump())
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@router.get("/{server_id}")
def get_server(
    server_id: str,
    session: Session = Depends(get_session),
    owner: str = Depends(_owner),
) -> McpServer:
    """Return one MCP server."""
    return _get_or_404(session, server_id, owner)


@router.put("/{server_id}")
def update_server(
    server_id: str,
    body: McpServerIn,
    session: Session = Depends(get_session),
    owner: str = Depends(_owner),
) -> McpServer:
    """Update an MCP server."""
    row = _get_or_404(session, server_id, owner)
    for key, value in body.model_dump().items():
        setattr(row, key, value)
    row.updated_at = datetime.utcnow()
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_server(
    server_id: str,
    session: Session = Depends(get_session),
    owner: str = Depends(_owner),
) -> None:
    """Delete an MCP server."""
    row = _get_or_404(session, server_id, owner)
    session.delete(row)
    session.commit()


def _build_client(row: McpServer) -> MCPClient:
    """Construct an AgentScope ``MCPClient`` from a registry row."""
    if row.transport == "http":
        config: Any = HttpMCPConfig(
            url=row.url,
            headers=row.headers or None,
            timeout=row.timeout,
        )
    else:
        config = StdioMCPConfig(
            command=row.command,
            args=row.args or None,
            env=row.env or None,
        )
    return MCPClient(
        name=row.name,
        is_stateful=row.is_stateful,
        mcp_config=config,
        enable_tools=row.enable_tools or None,
        disable_tools=row.disable_tools or None,
        execution_timeout=row.execution_timeout,
    )


@router.post("/{server_id}/test")
async def test_server(
    server_id: str,
    session: Session = Depends(get_session),
    owner: str = Depends(_owner),
) -> dict:
    """Connect to the MCP server and list its tools (health check).

    Builds a real AgentScope ``MCPClient``, connects (for stateful transports),
    enumerates tools, then records the result on the registry row.
    """
    row = _get_or_404(session, server_id, owner)
    client = _build_client(row)
    healthy = False
    error = ""
    tools: list[dict[str, str]] = []
    try:
        if row.is_stateful:
            await client.connect()
        mcp_tools = await client.list_tools()
        tools = [
            {"name": t.name, "description": getattr(t, "description", "") or ""}
            for t in mcp_tools
        ]
        healthy = True
    except Exception as exc:  # noqa: BLE001 - surface any connection failure
        error = str(exc)
    finally:
        try:
            if row.is_stateful:
                await client.close()
        except Exception:  # noqa: BLE001 - best-effort cleanup
            pass

    row.last_status = "healthy" if healthy else "unhealthy"
    row.last_checked_at = datetime.utcnow()
    row.last_error = error
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"healthy": healthy, "error": error, "tools": tools, "server": row}


@router.get("/enabled/payloads")
def enabled_payloads(
    session: Session = Depends(get_session),
    owner: str = Depends(_owner),
) -> dict:
    """Return ``MCPClient`` payloads for all enabled servers.

    The console uses this after creating a session to attach every enabled MCP
    server to that session's workspace via AgentScope's ``POST /workspace/mcp``.
    """
    rows = list(
        session.exec(
            select(McpServer).where(
                McpServer.owner_user_id == owner,
                McpServer.enabled == True,  # noqa: E712 - SQL boolean compare
            ),
        ),
    )
    return {"items": [r.to_mcp_client_payload() for r in rows]}
