import { agentScopeClient } from './request';

export function listSchedules() {
  return agentScopeClient.get<{ schedules: any[]; total: number }>(
    '/schedule/',
  );
}

export function createSchedule(payload: Record<string, any>) {
  return agentScopeClient.post('/schedule/', payload);
}

export function deleteSchedule(scheduleId: string) {
  return agentScopeClient.delete(`/schedule/${scheduleId}`);
}
