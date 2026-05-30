import type {
  ActionType,
  AgentBinding,
  LinkType,
  ListResponse,
  ObjectInstance,
  ObjectType,
  Ontology,
  OntologyGraph,
  PropertyType,
} from './types';

import { agentScopeClient } from './request';

const base = '/ontology';

/* ----------------------------- ontology ---------------------------------- */
export function listOntologies() {
  return agentScopeClient.get<ListResponse<Ontology>>(`${base}/`);
}

export function createOntology(payload: {
  api_name: string;
  description?: string;
  display_name: string;
}) {
  return agentScopeClient.post<Ontology>(`${base}/`, payload);
}

export function updateOntology(id: string, payload: Partial<Ontology>) {
  return agentScopeClient.request<Ontology>(`${base}/${id}`, {
    method: 'PATCH',
    data: payload,
  });
}

export function deleteOntology(id: string) {
  return agentScopeClient.delete(`${base}/${id}`);
}

/* --------------------------- object types --------------------------------- */
export function listObjectTypes(ontologyId: string) {
  return agentScopeClient.get<ListResponse<ObjectType>>(
    `${base}/${ontologyId}/object-types`,
  );
}

export function createObjectType(
  ontologyId: string,
  payload: {
    api_name: string;
    color?: string;
    description?: string;
    display_name: string;
    icon?: string;
    primary_key_property?: string;
    properties?: Partial<PropertyType>[];
    title_property?: string;
  },
) {
  return agentScopeClient.post<ObjectType>(
    `${base}/${ontologyId}/object-types`,
    payload,
  );
}

export function updateObjectType(
  ontologyId: string,
  objectTypeId: string,
  payload: Partial<ObjectType>,
) {
  return agentScopeClient.request<ObjectType>(
    `${base}/${ontologyId}/object-types/${objectTypeId}`,
    { method: 'PATCH', data: payload },
  );
}

export function deleteObjectType(ontologyId: string, objectTypeId: string) {
  return agentScopeClient.delete(
    `${base}/${ontologyId}/object-types/${objectTypeId}`,
  );
}

/* ---------------------------- link types ---------------------------------- */
export function listLinkTypes(ontologyId: string) {
  return agentScopeClient.get<ListResponse<LinkType>>(
    `${base}/${ontologyId}/link-types`,
  );
}

export function createLinkType(
  ontologyId: string,
  payload: {
    api_name: string;
    cardinality?: string;
    description?: string;
    display_name: string;
    source_object_type_id: string;
    target_object_type_id: string;
  },
) {
  return agentScopeClient.post<LinkType>(
    `${base}/${ontologyId}/link-types`,
    payload,
  );
}

export function deleteLinkType(ontologyId: string, linkTypeId: string) {
  return agentScopeClient.delete(
    `${base}/${ontologyId}/link-types/${linkTypeId}`,
  );
}

/* --------------------------- action types --------------------------------- */
export function listActionTypes(ontologyId: string) {
  return agentScopeClient.get<ListResponse<ActionType>>(
    `${base}/${ontologyId}/action-types`,
  );
}

export function createActionType(
  ontologyId: string,
  payload: {
    api_name: string;
    description?: string;
    display_name: string;
    effect: string;
    object_type_id?: string;
    parameters?: Record<string, any>;
  },
) {
  return agentScopeClient.post<ActionType>(
    `${base}/${ontologyId}/action-types`,
    payload,
  );
}

export function deleteActionType(ontologyId: string, actionTypeId: string) {
  return agentScopeClient.delete(
    `${base}/${ontologyId}/action-types/${actionTypeId}`,
  );
}

/* ------------------------------ objects ----------------------------------- */
export function listObjects(ontologyId: string, objectTypeId: string) {
  return agentScopeClient.get<ListResponse<ObjectInstance>>(
    `${base}/${ontologyId}/object-types/${objectTypeId}/objects`,
  );
}

export function createObject(
  ontologyId: string,
  objectTypeId: string,
  properties: Record<string, any>,
) {
  return agentScopeClient.post<ObjectInstance>(
    `${base}/${ontologyId}/object-types/${objectTypeId}/objects`,
    { properties },
  );
}

export function updateObject(
  ontologyId: string,
  objectTypeId: string,
  objectId: string,
  properties: Record<string, any>,
) {
  return agentScopeClient.request<ObjectInstance>(
    `${base}/${ontologyId}/object-types/${objectTypeId}/objects/${objectId}`,
    { method: 'PATCH', data: { properties } },
  );
}

export function deleteObject(
  ontologyId: string,
  objectTypeId: string,
  objectId: string,
) {
  return agentScopeClient.delete(
    `${base}/${ontologyId}/object-types/${objectTypeId}/objects/${objectId}`,
  );
}

/* ---------------------- semantic query / actions -------------------------- */
export function queryObjects(
  ontologyId: string,
  payload: {
    filters?: Record<string, any>;
    limit?: number;
    object_type: string;
    offset?: number;
    search?: string;
  },
) {
  return agentScopeClient.post<{
    items: ObjectInstance[];
    object_type: string;
    total: number;
  }>(`${base}/${ontologyId}/query`, payload);
}

export function executeAction(
  ontologyId: string,
  payload: {
    action: string;
    object_id?: string;
    parameters?: Record<string, any>;
  },
) {
  return agentScopeClient.post(
    `${base}/${ontologyId}/actions/execute`,
    payload,
  );
}

export function getGraph(ontologyId: string) {
  return agentScopeClient.get<OntologyGraph>(`${base}/${ontologyId}/graph`);
}

/* ------------------------------ bindings ---------------------------------- */
export function getAllBindings() {
  return agentScopeClient.get<ListResponse<AgentBinding>>(
    `${base}/bindings/all`,
  );
}

export function getBinding(agentId: string) {
  return agentScopeClient.get<AgentBinding | null>(
    `${base}/bindings/${agentId}`,
  );
}

export function putBinding(agentId: string, payload: Partial<AgentBinding>) {
  return agentScopeClient.put<AgentBinding>(
    `${base}/bindings/${agentId}`,
    payload,
  );
}

export function deleteBinding(agentId: string) {
  return agentScopeClient.delete(`${base}/bindings/${agentId}`);
}
