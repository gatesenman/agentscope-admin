import { useAppConfig } from '@vben/hooks';

import { agentScopeClient, getAgentScopeUserId } from './request';

const { apiURL } = useAppConfig(import.meta.env, import.meta.env.PROD);

export interface PublishedApp {
  id: string;
  token: string;
  owner_user_id: string;
  agent_id: string;
  name: string;
  description: string;
  icon: string;
  opening_statement: string;
  suggested_questions: string[];
  chat_model_type?: null | string;
  chat_model_credential_id?: null | string;
  chat_model_name?: null | string;
  parameters: Record<string, any>;
  permission_mode: string;
  enabled: boolean;
  allowed_origins: string[];
  rate_limit_per_min: number;
  created_at: string;
  updated_at: string;
}

export interface AppApiKey {
  id: string;
  app_id: string;
  name: string;
  key_prefix: string;
  revoked: boolean;
  last_used_at?: null | string;
  created_at: string;
}

export interface PublishPayload {
  agent_id: string;
  name?: string;
  description?: string;
  icon?: string;
  opening_statement?: string;
  suggested_questions?: string[];
  allowed_origins?: string[];
  rate_limit_per_min?: number;
}

export interface UpdateAppPayload {
  name?: string;
  description?: string;
  icon?: string;
  opening_statement?: string;
  suggested_questions?: string[];
  allowed_origins?: string[];
  rate_limit_per_min?: number;
  enabled?: boolean;
  permission_mode?: string;
}

export function listApps() {
  return agentScopeClient.get<{
    items: { app: PublishedApp; key_count: number }[];
    total: number;
  }>('/admin/published-apps/');
}

export function publishApp(payload: PublishPayload) {
  return agentScopeClient.post<PublishedApp>('/admin/published-apps/', payload);
}

export function getApp(appId: string) {
  return agentScopeClient.get<PublishedApp>(`/admin/published-apps/${appId}`);
}

export function updateApp(appId: string, payload: UpdateAppPayload) {
  return agentScopeClient.request<PublishedApp>(
    `/admin/published-apps/${appId}`,
    { method: 'PATCH', data: payload },
  );
}

export function deleteApp(appId: string) {
  return agentScopeClient.delete(`/admin/published-apps/${appId}`);
}

export function listKeys(appId: string) {
  return agentScopeClient.get<{ items: AppApiKey[]; total: number }>(
    `/admin/published-apps/${appId}/keys`,
  );
}

export function createKey(appId: string, name: string) {
  return agentScopeClient.post<{ key: string; record: AppApiKey }>(
    `/admin/published-apps/${appId}/keys`,
    { name },
  );
}

export function revokeKey(appId: string, keyId: string) {
  return agentScopeClient.post(
    `/admin/published-apps/${appId}/keys/${keyId}/revoke`,
  );
}

/** Absolute base URL of the AgentScope backend (for snippets + public URL). */
export function apiBaseUrl(): string {
  return apiURL.startsWith('http')
    ? apiURL
    : `${globalThis.location?.origin ?? ''}${apiURL}`;
}

/** Public hosted Web App URL for an app token. */
export function webAppUrl(token: string): string {
  return `${globalThis.location?.origin ?? ''}/app/${token}`;
}

export interface PublicAppMeta {
  token: string;
  name: string;
  description: string;
  icon: string;
  opening_statement: string;
  suggested_questions: string[];
  enabled: boolean;
}

/** Fetch public metadata for the hosted Web App (no auth). */
export async function getPublicAppMeta(token: string): Promise<PublicAppMeta> {
  const res = await fetch(`${apiBaseUrl()}/public/apps/${token}`);
  if (!res.ok) throw new Error(`App not found: ${res.status}`);
  return res.json();
}

export interface PublicChatOptions {
  token: string;
  query: string;
  conversationId?: string;
  onDelta: (text: string) => void;
  signal?: AbortSignal;
}

/**
 * Stream a chat reply from a published app's public Web App endpoint.
 *
 * Returns the conversation id (echoed by the server header) so the caller can
 * keep multi-turn context.
 */
export async function streamPublicChat(
  options: PublicChatOptions,
): Promise<string> {
  const { token, query, conversationId, onDelta, signal } = options;
  const response = await fetch(`${apiBaseUrl()}/public/apps/${token}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, conversation_id: conversationId }),
    signal,
  });
  if (!response.ok || !response.body) {
    throw new Error(`Chat failed: ${response.status}`);
  }
  const convId =
    response.headers.get('X-Conversation-Id') || conversationId || '';
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
          const event = JSON.parse(frame.slice(5).trim());
          if (event.type === 'TEXT_BLOCK_DELTA' && event.delta) {
            onDelta(event.delta);
          }
        } catch {
          // ignore malformed frame
        }
      }
      index = buffer.indexOf('\n\n');
    }
  }
  return convId;
}

/** Identity header value, exposed for raw-API snippets. */
export function ownerUserId(): string {
  return getAgentScopeUserId();
}
