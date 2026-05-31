"""SQLModel tables for the ontology.

The data model mirrors Palantir ontology concepts:

- ``Ontology``      — a namespace grouping a set of types.
- ``ObjectType``    — a class of objects (e.g. ``Employee``).
- ``PropertyType``  — a typed attribute on an object type.
- ``LinkType``      — a relationship between two object types.
- ``ActionType``    — a parameterised action that mutates objects.
- ``ObjectInstance``— a concrete object (row) of an object type.
- ``LinkInstance``  — a concrete link between two object instances.
- ``AgentBinding``  — binds an AgentScope agent to an ontology.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import Column
from sqlalchemy import JSON as SAJSON
from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.utcnow()


class PropertyDataType(str, Enum):
    """Supported property data types."""

    STRING = "string"
    INTEGER = "integer"
    DOUBLE = "double"
    BOOLEAN = "boolean"
    DATE = "date"
    TIMESTAMP = "timestamp"
    GEO_POINT = "geo_point"
    ARRAY = "array"


class LinkCardinality(str, Enum):
    """Cardinality of a link type."""

    ONE_TO_ONE = "one_to_one"
    ONE_TO_MANY = "one_to_many"
    MANY_TO_MANY = "many_to_many"


class ActionEffect(str, Enum):
    """The primary effect of an action type."""

    CREATE = "create"
    MODIFY = "modify"
    DELETE = "delete"
    CUSTOM = "custom"


class DatasourceKind(str, Enum):
    """Backing data source kind for an object type."""

    DATASET = "dataset"
    REST_API = "rest_api"
    SQL = "sql"
    INLINE = "inline"


class ConnectorKind(str, Enum):
    """External system kind an action can write back to."""

    REST = "rest"
    WEBHOOK = "webhook"
    SQL = "sql"
    INTERNAL = "internal"


class Ontology(SQLModel, table=True):
    """A namespace grouping ontology types."""

    __tablename__ = "ontology"

    id: str = Field(default_factory=_uuid, primary_key=True)
    api_name: str = Field(index=True, unique=True)
    display_name: str
    description: str = ""
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class Datasource(SQLModel, table=True):
    """A backing data source for object types (dataset / REST / SQL).

    Object types are *materialised* from a datasource; each property maps to
    one of the datasource's columns (see ``PropertyType.column_mapping``).
    This mirrors Palantir's "object type is backed by a datasource" model and
    gives every object provenance/lineage.
    """

    __tablename__ = "datasource"

    id: str = Field(default_factory=_uuid, primary_key=True)
    ontology_id: str = Field(index=True, foreign_key="ontology.id")
    api_name: str = Field(index=True)
    display_name: str
    description: str = ""
    kind: DatasourceKind = DatasourceKind.DATASET
    # Connection details, kind-specific:
    #   dataset  -> {"path": "/datasets/...", "format": "parquet"}
    #   rest_api -> {"base_url": "...", "path": "/accounts"}
    #   sql      -> {"dsn": "...", "table": "accounts"}
    connection: dict[str, Any] = Field(default_factory=dict, sa_column=Column(SAJSON))
    # Declared columns: [{"name": "ACCT_NO", "data_type": "string"}, ...]
    columns: list[dict[str, Any]] = Field(
        default_factory=list, sa_column=Column(SAJSON)
    )
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class Connector(SQLModel, table=True):
    """An external system an action type can write back to.

    A connector exposes one or more named *operations*; an action type binds
    to a single operation and maps its parameters onto the operation's fields
    (see ``ActionType.connector_id`` / ``connector_operation`` /
    ``parameter_bindings``).
    """

    __tablename__ = "connector"

    id: str = Field(default_factory=_uuid, primary_key=True)
    ontology_id: str = Field(index=True, foreign_key="ontology.id")
    api_name: str = Field(index=True)
    display_name: str
    description: str = ""
    kind: ConnectorKind = ConnectorKind.REST
    # Connection-level config: {"base_url": "...", "headers": {...}, "auth": "..."}
    config: dict[str, Any] = Field(default_factory=dict, sa_column=Column(SAJSON))
    # Operations: [{"api_name": "freeze", "display_name": "...",
    #               "method": "POST", "path": "/accounts/{id}/freeze",
    #               "description": "...", "params": ["freeze_reason"]}]
    operations: list[dict[str, Any]] = Field(
        default_factory=list, sa_column=Column(SAJSON)
    )
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class ObjectType(SQLModel, table=True):
    """A class of objects within an ontology."""

    __tablename__ = "object_type"

    id: str = Field(default_factory=_uuid, primary_key=True)
    ontology_id: str = Field(index=True, foreign_key="ontology.id")
    api_name: str = Field(index=True)
    display_name: str
    description: str = ""
    icon: str = "Box"
    color: str = "#3b82f6"
    primary_key_property: str = "id"
    title_property: str | None = None
    # Backing datasource (provenance). ``backing_table`` is the object/table
    # within the datasource that materialises this object type.
    datasource_id: str | None = Field(default=None, foreign_key="datasource.id")
    backing_table: str = ""
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class PropertyType(SQLModel, table=True):
    """A typed attribute on an object type."""

    __tablename__ = "property_type"

    id: str = Field(default_factory=_uuid, primary_key=True)
    object_type_id: str = Field(index=True, foreign_key="object_type.id")
    api_name: str
    display_name: str
    data_type: PropertyDataType = PropertyDataType.STRING
    required: bool = False
    is_primary_key: bool = False
    is_title: bool = False
    description: str = ""
    sort_order: int = 0
    # Source column in the object type's backing datasource. Empty means the
    # property maps to a column with the same name as ``api_name``.
    column_mapping: str = ""


class LinkType(SQLModel, table=True):
    """A relationship between two object types."""

    __tablename__ = "link_type"

    id: str = Field(default_factory=_uuid, primary_key=True)
    ontology_id: str = Field(index=True, foreign_key="ontology.id")
    api_name: str
    display_name: str
    description: str = ""
    source_object_type_id: str = Field(foreign_key="object_type.id")
    target_object_type_id: str = Field(foreign_key="object_type.id")
    cardinality: LinkCardinality = LinkCardinality.ONE_TO_MANY


class ActionType(SQLModel, table=True):
    """A parameterised action that mutates objects."""

    __tablename__ = "action_type"

    id: str = Field(default_factory=_uuid, primary_key=True)
    ontology_id: str = Field(index=True, foreign_key="ontology.id")
    api_name: str
    display_name: str
    description: str = ""
    object_type_id: str | None = Field(default=None, foreign_key="object_type.id")
    effect: ActionEffect = ActionEffect.MODIFY
    parameters: dict[str, Any] = Field(default_factory=dict, sa_column=Column(SAJSON))
    # Optional write-back binding: when set, executing the action also invokes
    # ``connector_operation`` on ``connector_id``, mapping action parameters
    # onto the operation's fields via ``parameter_bindings`` (action_param ->
    # operation_field).
    connector_id: str | None = Field(default=None, foreign_key="connector.id")
    connector_operation: str = ""
    parameter_bindings: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(SAJSON)
    )
    created_at: datetime = Field(default_factory=_now)


class ObjectInstance(SQLModel, table=True):
    """A concrete object (row) of an object type."""

    __tablename__ = "object_instance"

    id: str = Field(default_factory=_uuid, primary_key=True)
    object_type_id: str = Field(index=True, foreign_key="object_type.id")
    properties: dict[str, Any] = Field(default_factory=dict, sa_column=Column(SAJSON))
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class LinkInstance(SQLModel, table=True):
    """A concrete link between two object instances."""

    __tablename__ = "link_instance"

    id: str = Field(default_factory=_uuid, primary_key=True)
    link_type_id: str = Field(index=True, foreign_key="link_type.id")
    source_object_id: str = Field(index=True, foreign_key="object_instance.id")
    target_object_id: str = Field(index=True, foreign_key="object_instance.id")


class AgentBinding(SQLModel, table=True):
    """Binds an AgentScope agent to an ontology."""

    __tablename__ = "agent_binding"

    agent_id: str = Field(primary_key=True)
    ontology_id: str = Field(foreign_key="ontology.id")
    enabled: bool = True
    # Optional allow-lists; empty means "all".
    allowed_object_types: list[str] = Field(
        default_factory=list, sa_column=Column(SAJSON)
    )
    allowed_actions: list[str] = Field(
        default_factory=list, sa_column=Column(SAJSON)
    )
    updated_at: datetime = Field(default_factory=_now)
