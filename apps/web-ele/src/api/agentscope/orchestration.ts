import { useAppConfig } from '@vben/hooks';

import { agentScopeClient, getAgentScopeUserId } from './request';

const { apiURL } = useAppConfig(import.meta.env, import.meta.env.PROD);

export type OrchestrationPattern =
  | 'aggregation'
  | 'handoff'
  | 'parallel'
  | 'router'
  | 'sequential'
  | 'supervisor';

export interface ModelConfig {
  credential_id: string;
  type: string;
  model: string;
  parameters: Record<string, any>;
}

export interface OrchestrationMember extends ModelConfig {
  id: string;
  name: string;
  role: string;
  instruction: string;
}

export interface OrchestrationConfig {
  members: OrchestrationMember[];
  coordinator: ModelConfig & { instruction: string };
  max_rounds: number;
}

export interface Orchestration {
  id: string;
  owner_user_id: string;
  name: string;
  description: string;
  icon: string;
  pattern: OrchestrationPattern;
  config: OrchestrationConfig;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export function listPatterns() {
  return agentScopeClient.get<{ items: { label: string; value: string }[] }>(
    '/admin/orchestrations/patterns',
  );
}

export function listOrchestrations() {
  return agentScopeClient.get<{ items: Orchestration[]; total: number }>(
    '/admin/orchestrations/',
  );
}

export function createOrchestration(payload: Partial<Orchestration>) {
  return agentScopeClient.post<Orchestration>(
    '/admin/orchestrations/',
    payload,
  );
}

export function getOrchestration(id: string) {
  return agentScopeClient.get<Orchestration>(`/admin/orchestrations/${id}`);
}

export function updateOrchestration(
  id: string,
  payload: Partial<Orchestration>,
) {
  return agentScopeClient.request<Orchestration>(
    `/admin/orchestrations/${id}`,
    { method: 'PATCH', data: payload },
  );
}

export function deleteOrchestration(id: string) {
  return agentScopeClient.delete(`/admin/orchestrations/${id}`);
}

export interface OrchestrationRunEvent {
  type:
    | 'error'
    | 'finished'
    | 'member_finished'
    | 'member_started'
    | 'text_delta';
  member?: string;
  role?: string;
  delta?: string;
  text?: string;
  output?: string;
  message?: string;
}

export interface RunOrchestrationOptions {
  id: string;
  query: string;
  onEvent: (event: OrchestrationRunEvent) => void;
  signal?: AbortSignal;
}

function apiBaseUrl(): string {
  return apiURL.startsWith('http')
    ? apiURL
    : `${globalThis.location?.origin ?? ''}${apiURL}`;
}

/** Run an orchestration, invoking `onEvent` for every streamed SSE event. */
export async function runOrchestration(
  options: RunOrchestrationOptions,
): Promise<void> {
  const { id, query, onEvent, signal } = options;
  const response = await fetch(
    `${apiBaseUrl()}/admin/orchestrations/${id}/run`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-User-ID': getAgentScopeUserId(),
      },
      body: JSON.stringify({ query }),
      signal,
    },
  );
  if (!response.ok || !response.body) {
    throw new Error(`Orchestration run failed: ${response.status}`);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let index = buffer.indexOf('\n\n');
    while (index !== -1) {
      const frame = buffer.slice(0, index).trim();
      buffer = buffer.slice(index + 2);
      if (frame.startsWith('data:')) {
        try {
          onEvent(JSON.parse(frame.slice(5).trim()));
        } catch {
          // ignore malformed frame
        }
      }
      index = buffer.indexOf('\n\n');
    }
  }
}
