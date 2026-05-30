import type { SessionRecord } from './types';

import { agentScopeClient } from './request';

export interface ChatModelConfig {
  type: string;
  credential_id: string;
  model: string;
  parameters?: Record<string, any>;
}

export interface CreateSessionPayload {
  agent_id: string;
  workspace_id?: string;
  name?: string;
  chat_model_config?: ChatModelConfig;
  fallback_chat_model_config?: ChatModelConfig;
}

export function listSessions(agentId: string) {
  return agentScopeClient.get<{ sessions: SessionRecord[]; total: number }>(
    '/sessions/',
    { params: { agent_id: agentId } },
  );
}

export function createSession(payload: CreateSessionPayload) {
  return agentScopeClient.post<{ session_id: string }>('/sessions/', payload);
}

export interface UpdateSessionPayload {
  name?: string;
  chat_model_config?: ChatModelConfig | null;
  fallback_chat_model_config?: ChatModelConfig | null;
  permission_mode?: string;
}

export function updateSession(
  sessionId: string,
  agentId: string,
  payload: UpdateSessionPayload,
) {
  return agentScopeClient.request(`/sessions/${sessionId}`, {
    method: 'PATCH',
    params: { agent_id: agentId },
    data: payload,
  });
}

export function deleteSession(sessionId: string, agentId: string) {
  return agentScopeClient.delete(`/sessions/${sessionId}`, {
    params: { agent_id: agentId },
  });
}

export function listMessages(sessionId: string, agentId: string) {
  return agentScopeClient.get<{ is_running: boolean; messages: any[] }>(
    `/sessions/${sessionId}/messages`,
    { params: { agent_id: agentId } },
  );
}
