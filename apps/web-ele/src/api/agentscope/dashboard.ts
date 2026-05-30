import type { DashboardStats } from './types';

import { agentScopeClient } from './request';

export function getDashboardStats() {
  return agentScopeClient.get<DashboardStats>('/dashboard/stats');
}
