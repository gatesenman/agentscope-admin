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

// ---- Execution-trace observability ----

export interface TraceSpanIn {
  seq: number;
  kind: string;
  name?: string;
  status?: string;
  model_name?: string;
  input_text?: string;
  output_text?: string;
  input_tokens?: number;
  output_tokens?: number;
  duration_ms?: number;
}

export interface RunIn {
  agent_id: string;
  session_id: string;
  run_id: string;
  source?: string;
  spans: TraceSpanIn[];
}

export interface AgentTraceRow {
  agent_id: string;
  sessions: number;
  runs: number;
  model_calls: number;
  tool_calls: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cost: number;
  success_rate: number;
  avg_latency_ms: number;
  p95_latency_ms: number;
  last_active: null | string;
}

export interface SessionTraceRow {
  session_id: string;
  agent_id: string;
  source: string;
  runs: number;
  model_calls: number;
  tool_calls: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cost: number;
  errors: number;
  duration_ms: number;
  started_at: null | string;
  last_active: null | string;
}

export interface TraceSpan {
  id: string;
  seq: number;
  kind: string;
  name: string;
  status: string;
  model_name: string;
  input_text: string;
  output_text: string;
  input_tokens: number;
  output_tokens: number;
  duration_ms: number;
  created_at: string;
}

export interface TraceRun {
  run_id: string;
  started_at: string;
  duration_ms: number;
  total_tokens: number;
  cost: number;
  status: string;
  spans: TraceSpan[];
}

export interface TopTool {
  name: string;
  calls: number;
  errors: number;
  avg_latency_ms: number;
}

export interface TraceAnalytics {
  days: number;
  total_runs: number;
  model_calls: number;
  tool_calls: number;
  success_rate: number;
  error_runs: number;
  avg_latency_ms: number;
  p50_latency_ms: number;
  p95_latency_ms: number;
  p99_latency_ms: number;
  top_tools: TopTool[];
  by_day: { date: string; input: number; output: number; runs: number }[];
}

export function recordRun(payload: RunIn) {
  return agentScopeClient.post('/admin/trace/runs', payload);
}

export function traceAgents(days = 30) {
  return agentScopeClient.get<{ items: AgentTraceRow[] }>(
    '/admin/trace/agents',
    { params: { days } },
  );
}

export function traceSessions(agentId: string, days = 30) {
  return agentScopeClient.get<{ items: SessionTraceRow[] }>(
    '/admin/trace/sessions',
    { params: { agent_id: agentId, days } },
  );
}

export function traceSession(sessionId: string) {
  return agentScopeClient.get<{ runs: TraceRun[]; session_id: string }>(
    `/admin/trace/sessions/${sessionId}`,
  );
}

export function traceAnalytics(days = 30) {
  return agentScopeClient.get<TraceAnalytics>('/admin/trace/analytics', {
    params: { days },
  });
}
