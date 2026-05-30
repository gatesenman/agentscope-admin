import type { ModelCard } from './types';

import { agentScopeClient } from './request';

export function listModels(provider: string) {
  return agentScopeClient.get<{ models: ModelCard[]; total: number }>(
    '/model/',
    { params: { provider } },
  );
}
