import type { ChatModelConfig } from './session';

import { agentScopeClient } from './request';

export interface ScheduleData {
  name: string;
  description: string;
  enabled: boolean;
  timezone: string;
  cron_expression: string;
  started_at?: string;
  ended_at?: null | string;
  chat_model_config?: ChatModelConfig;
  stateful: boolean;
  permission_mode: string;
  source?: string;
}

export interface ScheduleRecord {
  id: string;
  user_id: string;
  agent_id: string;
  data: ScheduleData;
  created_at?: string;
  updated_at?: string;
}

export interface CreateSchedulePayload {
  name: string;
  description?: string;
  cron_expression: string;
  timezone?: string;
  agent_id: string;
  chat_model_config: ChatModelConfig;
  enabled?: boolean;
  stateful?: boolean;
  permission_mode?: string;
}

export interface UpdateSchedulePayload {
  name?: string;
  description?: string;
  cron_expression?: string;
  timezone?: string;
  enabled?: boolean;
  stateful?: boolean;
  permission_mode?: string;
}

export function listSchedules() {
  return agentScopeClient.get<{ schedules: ScheduleRecord[]; total: number }>(
    '/schedule/',
  );
}

export function createSchedule(payload: CreateSchedulePayload) {
  return agentScopeClient.post<{ schedule_id: string }>('/schedule/', payload);
}

export function updateSchedule(
  scheduleId: string,
  payload: UpdateSchedulePayload,
) {
  return agentScopeClient.request<ScheduleRecord>(`/schedule/${scheduleId}`, {
    method: 'PATCH',
    data: payload,
  });
}

export function deleteSchedule(scheduleId: string) {
  return agentScopeClient.delete(`/schedule/${scheduleId}`);
}
