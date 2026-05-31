"""Request/response schemas for the ontology API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .models import (
    ActionEffect,
    ConnectorKind,
    DatasourceKind,
    LinkCardinality,
    PropertyDataType,
)


class OntologyCreate(BaseModel):
    api_name: str
    display_name: str
    description: str = ""


class OntologyUpdate(BaseModel):
    display_name: str | None = None
    description: str | None = None


class PropertyTypeIn(BaseModel):
    api_name: str
    display_name: str
    data_type: PropertyDataType = PropertyDataType.STRING
    required: bool = False
    is_primary_key: bool = False
    is_title: bool = False
    description: str = ""
    sort_order: int = 0
    column_mapping: str = ""


class ObjectTypeCreate(BaseModel):
    api_name: str
    display_name: str
    description: str = ""
    icon: str = "Box"
    color: str = "#3b82f6"
    primary_key_property: str = "id"
    title_property: str | None = None
    datasource_id: str | None = None
    backing_table: str = ""
    properties: list[PropertyTypeIn] = Field(default_factory=list)


class ObjectTypeUpdate(BaseModel):
    display_name: str | None = None
    description: str | None = None
    icon: str | None = None
    color: str | None = None
    primary_key_property: str | None = None
    title_property: str | None = None
    datasource_id: str | None = None
    backing_table: str | None = None
    properties: list[PropertyTypeIn] | None = None


class DatasourceCreate(BaseModel):
    api_name: str
    display_name: str
    description: str = ""
    kind: DatasourceKind = DatasourceKind.DATASET
    connection: dict[str, Any] = Field(default_factory=dict)
    columns: list[dict[str, Any]] = Field(default_factory=list)


class DatasourceUpdate(BaseModel):
    display_name: str | None = None
    description: str | None = None
    kind: DatasourceKind | None = None
    connection: dict[str, Any] | None = None
    columns: list[dict[str, Any]] | None = None


class ConnectorCreate(BaseModel):
    api_name: str
    display_name: str
    description: str = ""
    kind: ConnectorKind = ConnectorKind.REST
    config: dict[str, Any] = Field(default_factory=dict)
    operations: list[dict[str, Any]] = Field(default_factory=list)


class ConnectorUpdate(BaseModel):
    display_name: str | None = None
    description: str | None = None
    kind: ConnectorKind | None = None
    config: dict[str, Any] | None = None
    operations: list[dict[str, Any]] | None = None


class LinkTypeCreate(BaseModel):
    api_name: str
    display_name: str
    description: str = ""
    source_object_type_id: str
    target_object_type_id: str
    cardinality: LinkCardinality = LinkCardinality.ONE_TO_MANY


class LinkTypeUpdate(BaseModel):
    display_name: str | None = None
    description: str | None = None
    cardinality: LinkCardinality | None = None


class ActionTypeCreate(BaseModel):
    api_name: str
    display_name: str
    description: str = ""
    object_type_id: str | None = None
    effect: ActionEffect = ActionEffect.MODIFY
    parameters: dict[str, Any] = Field(default_factory=dict)
    connector_id: str | None = None
    connector_operation: str = ""
    parameter_bindings: dict[str, Any] = Field(default_factory=dict)


class ActionTypeUpdate(BaseModel):
    display_name: str | None = None
    description: str | None = None
    object_type_id: str | None = None
    effect: ActionEffect | None = None
    parameters: dict[str, Any] | None = None
    connector_id: str | None = None
    connector_operation: str | None = None
    parameter_bindings: dict[str, Any] | None = None


class ObjectInstanceIn(BaseModel):
    properties: dict[str, Any] = Field(default_factory=dict)


class LinkInstanceIn(BaseModel):
    link_type_id: str
    source_object_id: str
    target_object_id: str


class ObjectQuery(BaseModel):
    """A semantic query against an object type."""

    object_type: str = Field(description="Object type api_name.")
    filters: dict[str, Any] = Field(
        default_factory=dict,
        description="Equality filters keyed by property api_name.",
    )
    search: str | None = Field(
        default=None, description="Free-text search across string properties."
    )
    limit: int = 50
    offset: int = 0


class ActionExecuteRequest(BaseModel):
    action: str = Field(description="Action type api_name.")
    parameters: dict[str, Any] = Field(default_factory=dict)
    object_id: str | None = Field(
        default=None, description="Target object id for modify/delete actions."
    )


class AgentBindingIn(BaseModel):
    ontology_id: str
    enabled: bool = True
    allowed_object_types: list[str] = Field(default_factory=list)
    allowed_actions: list[str] = Field(default_factory=list)
