import { agentScopeClient } from './request';

export function listMcps(workspaceId: string) {
  return agentScopeClient.get<{ mcps: any[] }>('/workspace/mcp', {
    params: { workspace_id: workspaceId },
  });
}

export function listSkills(workspaceId: string) {
  return agentScopeClient.get<{ skills: any[] }>('/workspace/skill', {
    params: { workspace_id: workspaceId },
  });
}
