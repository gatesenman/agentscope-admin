"""Persistent MCP server registry.

AgentScope's own ``/workspace/mcp`` endpoints attach MCP clients to a single
running *session* (runtime scope). A professional admin platform additionally
needs a *persistent registry* of MCP servers that operators configure once and
then reuse across agents and sessions. This module provides that registry
(SQLite-backed CRUD), a live health/tool-discovery test that builds a real
AgentScope ``MCPClient``, and a helper to materialise a registry row into the
payload AgentScope's session-scoped endpoint expects.
"""
