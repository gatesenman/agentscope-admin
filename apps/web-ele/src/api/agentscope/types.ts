/** Shared types for the AgentScope + Ontology API. */

export interface JsonSchema {
  type?: string;
  title?: string;
  description?: string;
  default?: any;
  format?: string;
  enum?: any[];
  minimum?: number;
  maximum?: number;
  properties?: Record<string, JsonSchema>;
  required?: string[];
  items?: JsonSchema;
  [key: string]: any;
}

export interface AgentSchemaResponse {
  identity: JsonSchema;
  context_config: JsonSchema;
  react_config: JsonSchema;
}

export interface AgentData {
  id: string;
  name: string;
  system_prompt: string;
  context_config: Record<string, any>;
  react_config: Record<string, any>;
}

export interface AgentRecord {
  id: string;
  user_id: string;
  data: AgentData;
  created_at: string;
  updated_at: string;
}

export interface CredentialSchema extends JsonSchema {
  title: string;
}

export interface CredentialRecord {
  id: string;
  user_id: string;
  data: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface AgentProfile {
  agent_id: string;
  default_provider?: null | string;
  default_credential_id?: null | string;
  default_model?: null | string;
  parameters: Record<string, any>;
  fallback_provider?: null | string;
  fallback_credential_id?: null | string;
  fallback_model?: null | string;
  stream: boolean;
  permission_mode: string;
  description: string;
  tags: string[];
  updated_at?: string;
}

export interface ModelCard {
  type: string;
  name: string;
  label?: string;
  status?: string;
  input_types?: string[];
  output_types?: string[];
  context_size?: number;
  [key: string]: any;
}

export interface SessionRecord {
  id: string;
  user_id: string;
  config: Record<string, any>;
  created_at: string;
  updated_at: string;
  [key: string]: any;
}

/* -------------------------------------------------------------------------- */
/* Ontology                                                                   */
/* -------------------------------------------------------------------------- */
export type PropertyDataType =
  | 'array'
  | 'boolean'
  | 'date'
  | 'double'
  | 'geo_point'
  | 'integer'
  | 'string'
  | 'timestamp';

export type LinkCardinality = 'many_to_many' | 'one_to_many' | 'one_to_one';

export type ActionEffect = 'create' | 'custom' | 'delete' | 'modify';

export interface Ontology {
  id: string;
  api_name: string;
  display_name: string;
  description: string;
  created_at: string;
  updated_at: string;
}

export interface PropertyType {
  id?: string;
  api_name: string;
  display_name: string;
  data_type: PropertyDataType;
  required: boolean;
  is_primary_key: boolean;
  is_title: boolean;
  description: string;
  sort_order: number;
  /** Name of the column in the backing datasource (empty = use api_name). */
  column_mapping?: string;
}

export interface ObjectType {
  id: string;
  ontology_id: string;
  api_name: string;
  display_name: string;
  description: string;
  icon: string;
  color: string;
  primary_key_property: string;
  title_property?: string;
  properties: PropertyType[];
  /** Backing datasource (data lineage). */
  datasource_id?: string;
  /** Table/dataset/endpoint within the datasource. */
  backing_table?: string;
}

export type DatasourceKind = 'dataset' | 'inline' | 'rest_api' | 'sql';

export interface DatasourceColumn {
  name: string;
  data_type: string;
}

export interface Datasource {
  id: string;
  ontology_id: string;
  api_name: string;
  display_name: string;
  description: string;
  kind: DatasourceKind;
  connection: Record<string, any>;
  columns: DatasourceColumn[];
  created_at: string;
}

export type ConnectorKind = 'internal' | 'rest' | 'sql' | 'webhook';

export interface ConnectorOperation {
  api_name: string;
  display_name?: string;
  method?: string;
  path?: string;
  description?: string;
  params?: string[];
}

export interface Connector {
  id: string;
  ontology_id: string;
  api_name: string;
  display_name: string;
  description: string;
  kind: ConnectorKind;
  config: Record<string, any>;
  operations: ConnectorOperation[];
  created_at: string;
}

export interface LinkType {
  id: string;
  ontology_id: string;
  api_name: string;
  display_name: string;
  description: string;
  source_object_type_id: string;
  target_object_type_id: string;
  cardinality: LinkCardinality;
}

export interface ActionType {
  id: string;
  ontology_id: string;
  api_name: string;
  display_name: string;
  description: string;
  object_type_id?: string;
  effect: ActionEffect;
  parameters: Record<string, any>;
  /** Bound connector that this action writes back to (optional). */
  connector_id?: string;
  /** api_name of the connector operation to invoke. */
  connector_operation?: string;
  /** Maps action parameter name -> connector operation field name. */
  parameter_bindings?: Record<string, string>;
}

export interface ObjectInstance {
  id: string;
  object_type_id: string;
  properties: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface AgentBinding {
  agent_id: string;
  ontology_id: string;
  enabled: boolean;
  allowed_object_types: string[];
  allowed_actions: string[];
}

export interface OntologyGraph {
  nodes: {
    api_name: string;
    color: string;
    icon: string;
    id: string;
    label: string;
  }[];
  edges: {
    cardinality: LinkCardinality;
    id: string;
    label: string;
    source: string;
    target: string;
  }[];
}

export interface DashboardStats {
  agents: number;
  credentials: number;
  schedules: number;
  sessions: number;
  ontologies: number;
  object_types: number;
  link_types: number;
  action_types: number;
  objects: number;
}

export interface ListResponse<T> {
  items: T[];
  total: number;
}
