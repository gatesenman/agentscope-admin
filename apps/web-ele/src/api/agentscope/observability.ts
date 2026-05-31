import { agentScopeClient } from './request';

export interface UsageCreate {
  agent_id?: string;
  session_id?: string;
  source?: string;
  model_name?: string;
  input_tokens?: number;
  output_tokens?: number;
}

export interface UsageByModel {
  model_name: string;
  calls: number;
  input: number;
  output: number;
  cost: number;
}

export interface UsageByDay {
  date: string;
  calls: number;
  input: number;
  output: number;
}

export interface UsageSummary {
  days: number;
  total_calls: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  estimated_cost_usd: number;
  by_model: UsageByModel[];
  by_day: UsageByDay[];
}

export interface UsageRow {
  id: string;
  agent_id: string;
  session_id: string;
  source: string;
  model_name: string;
  input_tokens: number;
  output_tokens: number;
  cost: number;
  created_at: string;
}

export function recordUsage(payload: UsageCreate) {
  return agentScopeClient.post('/admin/usage/', payload);
}

export function usageSummary(days = 30) {
  return agentScopeClient.get<UsageSummary>('/admin/usage/summary', {
    params: { days },
  });
}

export function usageRecent(limit = 50) {
  return agentScopeClient.get<{ items: UsageRow[] }>('/admin/usage/recent', {
    params: { limit },
  });
}
