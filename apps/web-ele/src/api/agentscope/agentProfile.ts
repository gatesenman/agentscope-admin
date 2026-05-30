import type { AgentProfile } from './types';

import { agentScopeClient } from './request';

export type AgentProfilePayload = Omit<AgentProfile, 'agent_id' | 'updated_at'>;

export function listProfiles() {
  return agentScopeClient.get<{ items: AgentProfile[]; total: number }>(
    '/admin/agent-profiles/',
  );
}

export function getProfile(agentId: string) {
  return agentScopeClient.get<AgentProfile | null>(
    `/admin/agent-profiles/${agentId}`,
  );
}

export function putProfile(agentId: string, payload: AgentProfilePayload) {
  return agentScopeClient.request<AgentProfile>(
    `/admin/agent-profiles/${agentId}`,
    { method: 'PUT', data: payload },
  );
}

export function deleteProfile(agentId: string) {
  return agentScopeClient.delete(`/admin/agent-profiles/${agentId}`);
}
