"""REST API for the ontology module."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from .db import get_session
from .models import (
    ActionType,
    AgentBinding,
    Connector,
    Datasource,
    LinkInstance,
    LinkType,
    ObjectInstance,
    ObjectType,
    Ontology,
    PropertyType,
)
from .schemas import (
    ActionExecuteRequest,
    ActionTypeCreate,
    ActionTypeUpdate,
    AgentBindingIn,
    ConnectorCreate,
    ConnectorUpdate,
    DatasourceCreate,
    DatasourceUpdate,
    LinkInstanceIn,
    LinkTypeCreate,
    LinkTypeUpdate,
    ObjectInstanceIn,
    ObjectQuery,
    ObjectTypeCreate,
    ObjectTypeUpdate,
    OntologyCreate,
    OntologyUpdate,
)
from .service import OntologyError, execute_action, list_properties, query_objects, traverse_link

router = APIRouter(prefix="/ontology", tags=["ontology"])


def _get_or_404(session: Session, model: type, ident: str, name: str) -> Any:
    obj = session.get(model, ident)
    if obj is None:
        raise HTTPException(status_code=404, detail=f"{name} not found: {ident}")
    return obj


# --------------------------------------------------------------------------- #
# Ontology namespaces
# --------------------------------------------------------------------------- #
@router.get("/")
def list_ontologies(session: Session = Depends(get_session)) -> dict:
    rows = list(session.exec(select(Ontology)))
    return {"items": rows, "total": len(rows)}


@router.post("/")
def create_ontology(body: OntologyCreate, session: Session = Depends(get_session)) -> Ontology:
    existing = session.exec(select(Ontology).where(Ontology.api_name == body.api_name)).first()
    if existing:
        raise HTTPException(status_code=409, detail="api_name already exists")
    ont = Ontology(**body.model_dump())
    session.add(ont)
    session.commit()
    session.refresh(ont)
    return ont


@router.get("/{ontology_id}")
def get_ontology(ontology_id: str, session: Session = Depends(get_session)) -> Ontology:
    return _get_or_404(session, Ontology, ontology_id, "Ontology")


@router.patch("/{ontology_id}")
def update_ontology(ontology_id: str, body: OntologyUpdate, session: Session = Depends(get_session)) -> Ontology:
    ont = _get_or_404(session, Ontology, ontology_id, "Ontology")
    for key, value in body.model_dump(exclude_none=True).items():
        setattr(ont, key, value)
    session.add(ont)
    session.commit()
    session.refresh(ont)
    return ont


@router.delete("/{ontology_id}")
def delete_ontology(ontology_id: str, session: Session = Depends(get_session)) -> dict:
    ont = _get_or_404(session, Ontology, ontology_id, "Ontology")
    session.delete(ont)
    session.commit()
    return {"deleted": ontology_id}


# --------------------------------------------------------------------------- #
# Object types & properties
# --------------------------------------------------------------------------- #
def _serialize_object_type(session: Session, ot: ObjectType) -> dict:
    return {
        **ot.model_dump(),
        "properties": [p.model_dump() for p in list_properties(session, ot.id)],
    }


@router.get("/{ontology_id}/object-types")
def list_object_types(ontology_id: str, session: Session = Depends(get_session)) -> dict:
    rows = list(session.exec(select(ObjectType).where(ObjectType.ontology_id == ontology_id)))
    return {"items": [_serialize_object_type(session, r) for r in rows], "total": len(rows)}


@router.post("/{ontology_id}/object-types")
def create_object_type(ontology_id: str, body: ObjectTypeCreate, session: Session = Depends(get_session)) -> dict:
    _get_or_404(session, Ontology, ontology_id, "Ontology")
    ot = ObjectType(
        ontology_id=ontology_id,
        **body.model_dump(exclude={"properties"}),
    )
    session.add(ot)
    session.commit()
    session.refresh(ot)
    for prop in body.properties:
        session.add(PropertyType(object_type_id=ot.id, **prop.model_dump()))
    session.commit()
    session.refresh(ot)
    return _serialize_object_type(session, ot)


@router.patch("/{ontology_id}/object-types/{object_type_id}")
def update_object_type(ontology_id: str, object_type_id: str, body: ObjectTypeUpdate, session: Session = Depends(get_session)) -> dict:
    ot = _get_or_404(session, ObjectType, object_type_id, "ObjectType")
    data = body.model_dump(exclude_none=True)
    props = data.pop("properties", None)
    for key, value in data.items():
        setattr(ot, key, value)
    session.add(ot)
    if props is not None:
        for old in list_properties(session, ot.id):
            session.delete(old)
        for prop in props:
            session.add(PropertyType(object_type_id=ot.id, **prop))
    session.commit()
    session.refresh(ot)
    return _serialize_object_type(session, ot)


@router.delete("/{ontology_id}/object-types/{object_type_id}")
def delete_object_type(ontology_id: str, object_type_id: str, session: Session = Depends(get_session)) -> dict:
    ot = _get_or_404(session, ObjectType, object_type_id, "ObjectType")
    for p in list_properties(session, ot.id):
        session.delete(p)
    session.delete(ot)
    session.commit()
    return {"deleted": object_type_id}


# --------------------------------------------------------------------------- #
# Datasources (backing data sources for object types)
# --------------------------------------------------------------------------- #
@router.get("/{ontology_id}/datasources")
def list_datasources(ontology_id: str, session: Session = Depends(get_session)) -> dict:
    rows = list(session.exec(select(Datasource).where(Datasource.ontology_id == ontology_id)))
    return {"items": rows, "total": len(rows)}


@router.post("/{ontology_id}/datasources")
def create_datasource(ontology_id: str, body: DatasourceCreate, session: Session = Depends(get_session)) -> Datasource:
    _get_or_404(session, Ontology, ontology_id, "Ontology")
    ds = Datasource(ontology_id=ontology_id, **body.model_dump())
    session.add(ds)
    session.commit()
    session.refresh(ds)
    return ds


@router.patch("/{ontology_id}/datasources/{datasource_id}")
def update_datasource(datasource_id: str, body: DatasourceUpdate, session: Session = Depends(get_session)) -> Datasource:
    ds = _get_or_404(session, Datasource, datasource_id, "Datasource")
    for key, value in body.model_dump(exclude_none=True).items():
        setattr(ds, key, value)
    session.add(ds)
    session.commit()
    session.refresh(ds)
    return ds


@router.delete("/{ontology_id}/datasources/{datasource_id}")
def delete_datasource(datasource_id: str, session: Session = Depends(get_session)) -> dict:
    ds = _get_or_404(session, Datasource, datasource_id, "Datasource")
    session.delete(ds)
    session.commit()
    return {"deleted": datasource_id}


# --------------------------------------------------------------------------- #
# Connectors (external systems action types write back to)
# --------------------------------------------------------------------------- #
@router.get("/{ontology_id}/connectors")
def list_connectors(ontology_id: str, session: Session = Depends(get_session)) -> dict:
    rows = list(session.exec(select(Connector).where(Connector.ontology_id == ontology_id)))
    return {"items": rows, "total": len(rows)}


@router.post("/{ontology_id}/connectors")
def create_connector(ontology_id: str, body: ConnectorCreate, session: Session = Depends(get_session)) -> Connector:
    _get_or_404(session, Ontology, ontology_id, "Ontology")
    conn = Connector(ontology_id=ontology_id, **body.model_dump())
    session.add(conn)
    session.commit()
    session.refresh(conn)
    return conn


@router.patch("/{ontology_id}/connectors/{connector_id}")
def update_connector(connector_id: str, body: ConnectorUpdate, session: Session = Depends(get_session)) -> Connector:
    conn = _get_or_404(session, Connector, connector_id, "Connector")
    for key, value in body.model_dump(exclude_none=True).items():
        setattr(conn, key, value)
    session.add(conn)
    session.commit()
    session.refresh(conn)
    return conn


@router.delete("/{ontology_id}/connectors/{connector_id}")
def delete_connector(connector_id: str, session: Session = Depends(get_session)) -> dict:
    conn = _get_or_404(session, Connector, connector_id, "Connector")
    session.delete(conn)
    session.commit()
    return {"deleted": connector_id}


# --------------------------------------------------------------------------- #
# Link types
# --------------------------------------------------------------------------- #
@router.get("/{ontology_id}/link-types")
def list_link_types(ontology_id: str, session: Session = Depends(get_session)) -> dict:
    rows = list(session.exec(select(LinkType).where(LinkType.ontology_id == ontology_id)))
    return {"items": rows, "total": len(rows)}


@router.post("/{ontology_id}/link-types")
def create_link_type(ontology_id: str, body: LinkTypeCreate, session: Session = Depends(get_session)) -> LinkType:
    _get_or_404(session, Ontology, ontology_id, "Ontology")
    lt = LinkType(ontology_id=ontology_id, **body.model_dump())
    session.add(lt)
    session.commit()
    session.refresh(lt)
    return lt


@router.patch("/{ontology_id}/link-types/{link_type_id}")
def update_link_type(ontology_id: str, link_type_id: str, body: LinkTypeUpdate, session: Session = Depends(get_session)) -> LinkType:
    lt = _get_or_404(session, LinkType, link_type_id, "LinkType")
    for key, value in body.model_dump(exclude_none=True).items():
        setattr(lt, key, value)
    session.add(lt)
    session.commit()
    session.refresh(lt)
    return lt


@router.delete("/{ontology_id}/link-types/{link_type_id}")
def delete_link_type(ontology_id: str, link_type_id: str, session: Session = Depends(get_session)) -> dict:
    lt = _get_or_404(session, LinkType, link_type_id, "LinkType")
    session.delete(lt)
    session.commit()
    return {"deleted": link_type_id}


# --------------------------------------------------------------------------- #
# Action types
# --------------------------------------------------------------------------- #
@router.get("/{ontology_id}/action-types")
def list_action_types(ontology_id: str, session: Session = Depends(get_session)) -> dict:
    rows = list(session.exec(select(ActionType).where(ActionType.ontology_id == ontology_id)))
    return {"items": rows, "total": len(rows)}


@router.post("/{ontology_id}/action-types")
def create_action_type(ontology_id: str, body: ActionTypeCreate, session: Session = Depends(get_session)) -> ActionType:
    _get_or_404(session, Ontology, ontology_id, "Ontology")
    at = ActionType(ontology_id=ontology_id, **body.model_dump())
    session.add(at)
    session.commit()
    session.refresh(at)
    return at


@router.patch("/{ontology_id}/action-types/{action_type_id}")
def update_action_type(ontology_id: str, action_type_id: str, body: ActionTypeUpdate, session: Session = Depends(get_session)) -> ActionType:
    at = _get_or_404(session, ActionType, action_type_id, "ActionType")
    for key, value in body.model_dump(exclude_none=True).items():
        setattr(at, key, value)
    session.add(at)
    session.commit()
    session.refresh(at)
    return at


@router.delete("/{ontology_id}/action-types/{action_type_id}")
def delete_action_type(ontology_id: str, action_type_id: str, session: Session = Depends(get_session)) -> dict:
    at = _get_or_404(session, ActionType, action_type_id, "ActionType")
    session.delete(at)
    session.commit()
    return {"deleted": action_type_id}


# --------------------------------------------------------------------------- #
# Object instances
# --------------------------------------------------------------------------- #
@router.get("/{ontology_id}/object-types/{object_type_id}/objects")
def list_objects(object_type_id: str, session: Session = Depends(get_session)) -> dict:
    rows = list(session.exec(select(ObjectInstance).where(ObjectInstance.object_type_id == object_type_id)))
    return {"items": rows, "total": len(rows)}


@router.post("/{ontology_id}/object-types/{object_type_id}/objects")
def create_object(object_type_id: str, body: ObjectInstanceIn, session: Session = Depends(get_session)) -> ObjectInstance:
    _get_or_404(session, ObjectType, object_type_id, "ObjectType")
    inst = ObjectInstance(object_type_id=object_type_id, properties=body.properties)
    session.add(inst)
    session.commit()
    session.refresh(inst)
    return inst


@router.patch("/{ontology_id}/object-types/{object_type_id}/objects/{object_id}")
def update_object(object_id: str, body: ObjectInstanceIn, session: Session = Depends(get_session)) -> ObjectInstance:
    inst = _get_or_404(session, ObjectInstance, object_id, "Object")
    inst.properties = {**(inst.properties or {}), **body.properties}
    session.add(inst)
    session.commit()
    session.refresh(inst)
    return inst


@router.delete("/{ontology_id}/object-types/{object_type_id}/objects/{object_id}")
def delete_object(object_id: str, session: Session = Depends(get_session)) -> dict:
    inst = _get_or_404(session, ObjectInstance, object_id, "Object")
    session.delete(inst)
    session.commit()
    return {"deleted": object_id}


# --------------------------------------------------------------------------- #
# Link instances
# --------------------------------------------------------------------------- #
@router.post("/{ontology_id}/links")
def create_link(ontology_id: str, body: LinkInstanceIn, session: Session = Depends(get_session)) -> LinkInstance:
    link = LinkInstance(**body.model_dump())
    session.add(link)
    session.commit()
    session.refresh(link)
    return link


# --------------------------------------------------------------------------- #
# Semantic query, traversal & action execution
# --------------------------------------------------------------------------- #
@router.post("/{ontology_id}/query")
def run_query(ontology_id: str, body: ObjectQuery, session: Session = Depends(get_session)) -> dict:
    try:
        return query_objects(
            session, ontology_id, body.object_type, body.filters, body.search, body.limit, body.offset
        )
    except OntologyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{ontology_id}/traverse")
def run_traverse(ontology_id: str, link_type: str, source_object_id: str, session: Session = Depends(get_session)) -> dict:
    try:
        return traverse_link(session, ontology_id, link_type, source_object_id)
    except OntologyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{ontology_id}/actions/execute")
def run_action(ontology_id: str, body: ActionExecuteRequest, session: Session = Depends(get_session)) -> dict:
    try:
        return execute_action(session, ontology_id, body.action, body.parameters, body.object_id)
    except OntologyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# --------------------------------------------------------------------------- #
# Graph (for visualization)
# --------------------------------------------------------------------------- #
@router.get("/{ontology_id}/graph")
def get_graph(ontology_id: str, session: Session = Depends(get_session)) -> dict:
    object_types = list(session.exec(select(ObjectType).where(ObjectType.ontology_id == ontology_id)))
    link_types = list(session.exec(select(LinkType).where(LinkType.ontology_id == ontology_id)))
    nodes = [
        {"id": ot.id, "api_name": ot.api_name, "label": ot.display_name, "icon": ot.icon, "color": ot.color}
        for ot in object_types
    ]
    edges = [
        {
            "id": lt.id,
            "label": lt.display_name,
            "source": lt.source_object_type_id,
            "target": lt.target_object_type_id,
            "cardinality": lt.cardinality,
        }
        for lt in link_types
    ]
    return {"nodes": nodes, "edges": edges}


# --------------------------------------------------------------------------- #
# Agent <-> ontology bindings
# --------------------------------------------------------------------------- #
@router.get("/bindings/all")
def list_bindings(session: Session = Depends(get_session)) -> dict:
    rows = list(session.exec(select(AgentBinding)))
    return {"items": rows, "total": len(rows)}


@router.get("/bindings/{agent_id}")
def get_binding(agent_id: str, session: Session = Depends(get_session)) -> AgentBinding | None:
    return session.get(AgentBinding, agent_id)


@router.put("/bindings/{agent_id}")
def upsert_binding(agent_id: str, body: AgentBindingIn, session: Session = Depends(get_session)) -> AgentBinding:
    binding = session.get(AgentBinding, agent_id)
    if binding is None:
        binding = AgentBinding(agent_id=agent_id, **body.model_dump())
    else:
        for key, value in body.model_dump().items():
            setattr(binding, key, value)
    session.add(binding)
    session.commit()
    session.refresh(binding)
    return binding


@router.delete("/bindings/{agent_id}")
def delete_binding(agent_id: str, session: Session = Depends(get_session)) -> dict:
    binding = session.get(AgentBinding, agent_id)
    if binding is not None:
        session.delete(binding)
        session.commit()
    return {"deleted": agent_id}
