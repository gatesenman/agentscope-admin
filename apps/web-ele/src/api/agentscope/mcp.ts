import { agentScopeClient } from './request';

export interface McpServer {
  id: string;
  owner_user_id: string;
  name: string;
  description: string;
  transport: 'http' | 'stdio';
  command: string;
  args: string[];
  env: Record<string, string>;
  url: string;
  headers: Record<string, string>;
  timeout: null | number;
  is_stateful: boolean;
  enable_tools: string[];
  disable_tools: string[];
  execution_timeout: null | number;
  enabled: boolean;
  last_status: 'healthy' | 'unhealthy' | 'unknown';
  last_checked_at: null | string;
  last_error: string;
  created_at: string;
  updated_at: string;
}

export interface McpTool {
  name: string;
  description: string;
}

export interface McpTestResult {
  healthy: boolean;
  error: string;
  tools: McpTool[];
  server: McpServer;
}

export function listMcpServers() {
  return agentScopeClient.get<{ items: McpServer[]; total: number }>(
    '/admin/mcp-servers/',
  );
}

export function createMcpServer(payload: Partial<McpServer>) {
  return agentScopeClient.post<McpServer>('/admin/mcp-servers/', payload);
}

export function updateMcpServer(id: string, payload: Partial<McpServer>) {
  return agentScopeClient.put<McpServer>(`/admin/mcp-servers/${id}`, payload);
}

export function deleteMcpServer(id: string) {
  return agentScopeClient.delete(`/admin/mcp-servers/${id}`);
}

export function testMcpServer(id: string) {
  return agentScopeClient.post<McpTestResult>(
    `/admin/mcp-servers/${id}/test`,
    {},
  );
}

export function enabledMcpPayloads() {
  return agentScopeClient.get<{ items: Record<string, any>[] }>(
    '/admin/mcp-servers/enabled/payloads',
  );
}
