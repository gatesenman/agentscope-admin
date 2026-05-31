import { agentScopeClient } from './request';

// AgentScope's workspace MCP/skill endpoints are scoped to a running session
// (agent_id + session_id), not a standalone workspace id.
export function listMcps(agentId: string, sessionId: string) {
  return agentScopeClient.get<any[]>('/workspace/mcp', {
    params: { agent_id: agentId, session_id: sessionId },
  });
}

export function addMcp(
  agentId: string,
  sessionId: string,
  mcp: Record<string, any>,
) {
  return agentScopeClient.post('/workspace/mcp', mcp, {
    params: { agent_id: agentId, session_id: sessionId },
  });
}

export function removeMcp(agentId: string, sessionId: string, mcpName: string) {
  return agentScopeClient.delete(`/workspace/mcp/${mcpName}`, {
    params: { agent_id: agentId, session_id: sessionId },
  });
}

export function listSkills(agentId: string, sessionId: string) {
  return agentScopeClient.get<any[]>('/workspace/skill', {
    params: { agent_id: agentId, session_id: sessionId },
  });
}
