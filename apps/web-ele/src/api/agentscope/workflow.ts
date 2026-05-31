import { useAppConfig } from '@vben/hooks';

import { agentScopeClient, getAgentScopeUserId } from './request';

const { apiURL } = useAppConfig(import.meta.env, import.meta.env.PROD);

export interface WorkflowNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: Record<string, any>;
}

export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle?: null | string;
  targetHandle?: null | string;
}

export interface WorkflowGraph {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
}

export interface Workflow {
  id: string;
  owner_user_id: string;
  name: string;
  description: string;
  icon: string;
  graph: WorkflowGraph;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export function listWorkflows() {
  return agentScopeClient.get<{ items: Workflow[]; total: number }>(
    '/admin/workflows/',
  );
}

export function createWorkflow(payload: Partial<Workflow>) {
  return agentScopeClient.post<Workflow>('/admin/workflows/', payload);
}

export function getWorkflow(id: string) {
  return agentScopeClient.get<Workflow>(`/admin/workflows/${id}`);
}

export function updateWorkflow(id: string, payload: Partial<Workflow>) {
  return agentScopeClient.request<Workflow>(`/admin/workflows/${id}`, {
    method: 'PATCH',
    data: payload,
  });
}

export function deleteWorkflow(id: string) {
  return agentScopeClient.delete(`/admin/workflows/${id}`);
}

export interface WorkflowRunEvent {
  type:
    | 'error'
    | 'node_finished'
    | 'node_started'
    | 'text_delta'
    | 'workflow_finished'
    | 'workflow_started';
  node_id?: string;
  node_type?: string;
  title?: string;
  delta?: string;
  output?: any;
  message?: string;
}

export interface RunWorkflowOptions {
  id: string;
  inputs: Record<string, any>;
  onEvent: (event: WorkflowRunEvent) => void;
  signal?: AbortSignal;
}

function apiBaseUrl(): string {
  return apiURL.startsWith('http')
    ? apiURL
    : `${globalThis.location?.origin ?? ''}${apiURL}`;
}

/** Run a workflow, invoking `onEvent` for every streamed SSE event. */
export async function runWorkflow(options: RunWorkflowOptions): Promise<void> {
  const { id, inputs, onEvent, signal } = options;
  const response = await fetch(`${apiBaseUrl()}/admin/workflows/${id}/run`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-User-ID': getAgentScopeUserId(),
    },
    body: JSON.stringify({ inputs }),
    signal,
  });
  if (!response.ok || !response.body) {
    throw new Error(`Workflow run failed: ${response.status}`);
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
