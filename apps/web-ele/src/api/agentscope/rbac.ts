import { agentScopeClient } from './request';

export interface RbacUser {
  id: string;
  username: string;
  display_name: string;
  role: string;
  enabled: boolean;
  permissions: string[];
  created_at: string;
  updated_at: string;
}

export interface RbacRole {
  name: string;
  label: string;
  permissions: string[];
}

export interface UserCreate {
  username: string;
  display_name?: string;
  role?: string;
  enabled?: boolean;
}

export interface UserUpdate {
  display_name?: string;
  role?: string;
  enabled?: boolean;
}

export function listUsers() {
  return agentScopeClient.get<{ items: RbacUser[] }>('/admin/rbac/users');
}

export function listRoles() {
  return agentScopeClient.get<{ items: RbacRole[] }>('/admin/rbac/roles');
}

export function whoami() {
  return agentScopeClient.get<RbacUser & { registered: boolean }>(
    '/admin/rbac/me',
  );
}

export function createUser(payload: UserCreate) {
  return agentScopeClient.post<RbacUser>('/admin/rbac/users', payload);
}

export function updateUser(id: string, payload: UserUpdate) {
  return agentScopeClient.put<RbacUser>(`/admin/rbac/users/${id}`, payload);
}

export function deleteUser(id: string) {
  return agentScopeClient.delete(`/admin/rbac/users/${id}`);
}
