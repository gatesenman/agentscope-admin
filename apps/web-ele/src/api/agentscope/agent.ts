import type { AgentRecord, AgentSchemaResponse } from './types';

import { agentScopeClient } from './request';

export interface CreateAgentPayload {
  name: string;
  system_prompt: string;
  context_config: Record<string, any>;
  react_config: Record<string, any>;
}

export function getAgentSchema() {
  return agentScopeClient.get<AgentSchemaResponse>('/agent/schema');
}

export function listAgents() {
  return agentScopeClient.get<{ agents: AgentRecord[]; total: number }>(
    '/agent/',
  );
}

export function createAgent(payload: CreateAgentPayload) {
  return agentScopeClient.post<{ agent_id: string }>('/agent/', payload);
}

export function updateAgent(agentId: string, payload: CreateAgentPayload) {
  return agentScopeClient.request<AgentRecord>(`/agent/${agentId}`, {
    method: 'PATCH',
    data: payload,
  });
}

export function deleteAgent(agentId: string) {
  return agentScopeClient.delete(`/agent/${agentId}`);
}
