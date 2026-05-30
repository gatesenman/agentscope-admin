import type { CredentialRecord, CredentialSchema } from './types';

import { agentScopeClient } from './request';

export function listCredentialSchemas() {
  return agentScopeClient.get<{ schemas: CredentialSchema[] }>(
    '/credential/schemas',
  );
}

export function listCredentials() {
  return agentScopeClient.get<{
    credentials: CredentialRecord[];
    total: number;
  }>('/credential/');
}

export function createCredential(data: Record<string, any>) {
  return agentScopeClient.post<{ credential_id: string }>('/credential/', {
    data,
  });
}

export function updateCredential(
  credentialId: string,
  data: Record<string, any>,
) {
  return agentScopeClient.request(`/credential/${credentialId}`, {
    method: 'PATCH',
    data: { data },
  });
}

export function deleteCredential(credentialId: string) {
  return agentScopeClient.delete(`/credential/${credentialId}`);
}
