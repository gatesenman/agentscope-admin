"""Ontology tools injected into AgentScope agents.

These tools let an agent run precise semantic queries and execute actions
against the ontology bound to it (Palantir-style). They are wired into the
AgentScope app through the ``extra_agent_tools`` factory in ``main.py``.
"""

from __future__ import annotations

import json
from typing import Any

from agentscope.message import TextBlock
from agentscope.permission import PermissionBehavior, PermissionDecision
from agentscope.tool import FunctionTool, ToolBase, ToolResponse
from sqlmodel import Session, select

from .db import engine
from .models import AgentBinding, ObjectType
from .service import OntologyError, execute_action, list_properties, query_objects, traverse_link


class AllowedFunctionTool(FunctionTool):
    """A FunctionTool that is auto-allowed (no human confirmation).

    The default :class:`FunctionTool` returns ``ASK`` so custom tools require
    explicit approval. Ontology tools are first-class capabilities of the
    platform, so we allow them to run automatically within the agent loop.
    """

    async def check_permissions(self, *args: Any, **kwargs: Any) -> PermissionDecision:  # noqa: D401
        return PermissionDecision(
            behavior=PermissionBehavior.ALLOW,
            message="Ontology tool allowed.",
        )


def _text(payload: Any) -> ToolResponse:
    return ToolResponse(
        content=[TextBlock(type="text", text=json.dumps(payload, default=str, ensure_ascii=False))]
    )


def build_ontology_tools(ontology_id: str) -> list[ToolBase]:
    """Build the ontology tool set scoped to a single ontology."""

    def ontology_list_object_types() -> ToolResponse:
        """List all object types available in the bound ontology, including
        their properties. Use this first to discover what data exists."""
        with Session(engine) as session:
            rows = list(
                session.exec(select(ObjectType).where(ObjectType.ontology_id == ontology_id))
            )
            out = []
            for ot in rows:
                out.append(
                    {
                        "api_name": ot.api_name,
                        "display_name": ot.display_name,
                        "description": ot.description,
                        "primary_key": ot.primary_key_property,
                        "properties": [
                            {"api_name": p.api_name, "data_type": p.data_type, "required": p.required}
                            for p in list_properties(session, ot.id)
                        ],
                    }
                )
            return _text({"object_types": out})

    def ontology_query_objects(
        object_type: str,
        filters: dict | None = None,
        search: str | None = None,
        limit: int = 25,
    ) -> ToolResponse:
        """Query objects of a given object type from the ontology.

        Args:
            object_type: The object type api_name to query.
            filters: Optional exact-match filters keyed by property api_name.
            search: Optional free-text search across string properties.
            limit: Maximum number of rows to return.
        """
        with Session(engine) as session:
            try:
                result = query_objects(session, ontology_id, object_type, filters, search, limit)
            except OntologyError as exc:
                return _text({"error": str(exc)})
            return _text(result)

    def ontology_traverse_link(link_type: str, source_object_id: str) -> ToolResponse:
        """Traverse a relationship (link) from a source object to its linked
        objects.

        Args:
            link_type: The link type api_name to traverse.
            source_object_id: The id of the source object instance.
        """
        with Session(engine) as session:
            try:
                result = traverse_link(session, ontology_id, link_type, source_object_id)
            except OntologyError as exc:
                return _text({"error": str(exc)})
            return _text(result)

    def ontology_execute_action(
        action: str,
        parameters: dict | None = None,
        object_id: str | None = None,
    ) -> ToolResponse:
        """Execute an ontology action to create, modify or delete objects.

        Args:
            action: The action type api_name to execute.
            parameters: Action parameters (object properties for create/modify).
            object_id: Target object id for modify/delete actions.
        """
        with Session(engine) as session:
            try:
                result = execute_action(session, ontology_id, action, parameters, object_id)
            except OntologyError as exc:
                return _text({"error": str(exc)})
            return _text(result)

    return [
        AllowedFunctionTool(ontology_list_object_types, is_read_only=True),
        AllowedFunctionTool(ontology_query_objects, is_read_only=True),
        AllowedFunctionTool(ontology_traverse_link, is_read_only=True),
        AllowedFunctionTool(ontology_execute_action, is_read_only=False),
    ]


async def ontology_tools_factory(user_id: str, agent_id: str, session_id: str) -> list[ToolBase]:
    """``extra_agent_tools`` factory: inject ontology tools for a bound agent."""
    with Session(engine) as session:
        binding = session.get(AgentBinding, agent_id)
    if binding is None or not binding.enabled:
        return []
    return build_ontology_tools(binding.ontology_id)
