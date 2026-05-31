"""Ontology business logic shared by the REST API and the agent tools."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlmodel import Session, select

from .models import (
    ActionEffect,
    ActionType,
    Connector,
    ConnectorKind,
    LinkInstance,
    LinkType,
    ObjectInstance,
    ObjectType,
    PropertyType,
)


class OntologyError(Exception):
    """Raised on invalid ontology operations."""


def _invoke_connector(
    session: Session,
    action: ActionType,
    parameters: dict[str, Any],
    object_id: str | None,
) -> dict[str, Any] | None:
    """Invoke the connector operation bound to an action, if any.

    Action parameters are mapped onto the operation's fields via
    ``action.parameter_bindings`` (action_param -> operation_field). For REST/
    webhook connectors with a ``base_url`` the call is attempted over HTTP
    (best-effort, short timeout); otherwise the call is *simulated* and the
    resolved payload is returned so the result is deterministic for demos and
    offline environments. A connector failure never aborts the ontology
    mutation — the error is captured in the returned record.
    """
    if not action.connector_id or not action.connector_operation:
        return None
    connector = session.get(Connector, action.connector_id)
    if connector is None:
        return {"status": "error", "error": "connector not found"}

    operation = next(
        (
            op
            for op in (connector.operations or [])
            if op.get("api_name") == action.connector_operation
        ),
        None,
    )
    if operation is None:
        return {
            "status": "error",
            "connector": connector.api_name,
            "operation": action.connector_operation,
            "error": "operation not found on connector",
        }

    # Map action parameters onto operation fields.
    bindings = action.parameter_bindings or {}
    payload: dict[str, Any] = {}
    for action_param, value in parameters.items():
        field = bindings.get(action_param, action_param)
        payload[field] = value
    if object_id:
        payload.setdefault("object_id", object_id)

    record: dict[str, Any] = {
        "connector": connector.api_name,
        "kind": connector.kind,
        "operation": operation.get("api_name"),
        "method": operation.get("method", "POST"),
        "path": operation.get("path", ""),
        "payload": payload,
    }

    config = connector.config or {}
    base_url = config.get("base_url")
    simulate = bool(config.get("simulate"))
    if (
        not simulate
        and connector.kind in (ConnectorKind.REST, ConnectorKind.WEBHOOK)
        and base_url
    ):
        url = f"{str(base_url).rstrip('/')}/{operation.get('path', '').lstrip('/')}"
        try:
            import httpx

            resp = httpx.request(
                operation.get("method", "POST"),
                url,
                json=payload,
                headers=config.get("headers") or {},
                timeout=5.0,
            )
            record["status"] = "sent"
            record["http_status"] = resp.status_code
        except Exception as exc:  # noqa: BLE001 — connector errors must not abort the action
            record["status"] = "error"
            record["error"] = str(exc)
    else:
        # Simulate mode (or no reachable endpoint): resolve the call
        # deterministically so demos/offline runs still show the write-back.
        record["status"] = "simulated"
    return record


def get_object_type_by_name(
    session: Session, ontology_id: str, api_name: str
) -> ObjectType | None:
    return session.exec(
        select(ObjectType).where(
            ObjectType.ontology_id == ontology_id,
            ObjectType.api_name == api_name,
        )
    ).first()


def list_properties(session: Session, object_type_id: str) -> list[PropertyType]:
    return list(
        session.exec(
            select(PropertyType)
            .where(PropertyType.object_type_id == object_type_id)
            .order_by(PropertyType.sort_order)
        )
    )


def query_objects(
    session: Session,
    ontology_id: str,
    object_type_name: str,
    filters: dict[str, Any] | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Run a semantic query against an object type, returning matching rows.

    Filtering is performed on the JSON ``properties`` payload. ``filters``
    are exact equality matches keyed by property api_name; ``search`` is a
    case-insensitive substring match across all string-valued properties.
    """
    obj_type = get_object_type_by_name(session, ontology_id, object_type_name)
    if obj_type is None:
        raise OntologyError(f"Unknown object type: {object_type_name!r}")

    rows = session.exec(
        select(ObjectInstance).where(ObjectInstance.object_type_id == obj_type.id)
    ).all()

    filters = filters or {}

    def _match(row: ObjectInstance) -> bool:
        props = row.properties or {}
        for key, value in filters.items():
            if props.get(key) != value:
                return False
        if search:
            needle = search.lower()
            haystack = " ".join(
                str(v) for v in props.values() if isinstance(v, str)
            ).lower()
            if needle not in haystack:
                return False
        return True

    matched = [r for r in rows if _match(r)]
    total = len(matched)
    page = matched[offset : offset + limit]
    return {
        "object_type": object_type_name,
        "total": total,
        "items": [
            {"id": r.id, "properties": r.properties, "updated_at": r.updated_at}
            for r in page
        ],
    }


def traverse_link(
    session: Session,
    ontology_id: str,
    link_type_name: str,
    source_object_id: str,
) -> dict[str, Any]:
    """Return the objects linked to ``source_object_id`` via a link type."""
    link_type = session.exec(
        select(LinkType).where(
            LinkType.ontology_id == ontology_id,
            LinkType.api_name == link_type_name,
        )
    ).first()
    if link_type is None:
        raise OntologyError(f"Unknown link type: {link_type_name!r}")

    links = session.exec(
        select(LinkInstance).where(
            LinkInstance.link_type_id == link_type.id,
            LinkInstance.source_object_id == source_object_id,
        )
    ).all()
    targets: list[dict[str, Any]] = []
    for link in links:
        target = session.get(ObjectInstance, link.target_object_id)
        if target is not None:
            targets.append({"id": target.id, "properties": target.properties})
    return {"link_type": link_type_name, "source_object_id": source_object_id, "targets": targets}


def execute_action(
    session: Session,
    ontology_id: str,
    action_name: str,
    parameters: dict[str, Any] | None = None,
    object_id: str | None = None,
) -> dict[str, Any]:
    """Execute an action type, mutating the ontology accordingly.

    - ``CREATE``: creates a new object instance of the action's object type
      using ``parameters`` as its properties.
    - ``MODIFY``: merges ``parameters`` into the target object's properties.
    - ``DELETE``: deletes the target object.
    - ``CUSTOM``: records the invocation and returns the parameters (no-op
      mutation; intended for side-effects wired up by integrators).
    """
    action = session.exec(
        select(ActionType).where(
            ActionType.ontology_id == ontology_id,
            ActionType.api_name == action_name,
        )
    ).first()
    if action is None:
        raise OntologyError(f"Unknown action: {action_name!r}")

    parameters = parameters or {}
    connector_result = _invoke_connector(session, action, parameters, object_id)

    def _with_connector(result: dict[str, Any]) -> dict[str, Any]:
        if connector_result is not None:
            result["connector_result"] = connector_result
        return result

    if action.effect == ActionEffect.CREATE:
        if not action.object_type_id:
            raise OntologyError("Create action has no target object type")
        instance = ObjectInstance(
            object_type_id=action.object_type_id, properties=parameters
        )
        session.add(instance)
        session.commit()
        session.refresh(instance)
        return _with_connector({"action": action_name, "effect": "create", "object": {"id": instance.id, "properties": instance.properties}})

    if action.effect == ActionEffect.MODIFY:
        if not object_id:
            raise OntologyError("Modify action requires object_id")
        instance = session.get(ObjectInstance, object_id)
        if instance is None:
            raise OntologyError(f"Object not found: {object_id!r}")
        merged = {**(instance.properties or {}), **parameters}
        instance.properties = merged
        instance.updated_at = datetime.utcnow()
        session.add(instance)
        session.commit()
        session.refresh(instance)
        return _with_connector({"action": action_name, "effect": "modify", "object": {"id": instance.id, "properties": instance.properties}})

    if action.effect == ActionEffect.DELETE:
        if not object_id:
            raise OntologyError("Delete action requires object_id")
        instance = session.get(ObjectInstance, object_id)
        if instance is None:
            raise OntologyError(f"Object not found: {object_id!r}")
        session.delete(instance)
        session.commit()
        return _with_connector({"action": action_name, "effect": "delete", "object_id": object_id})

    return _with_connector({"action": action_name, "effect": "custom", "parameters": parameters})
