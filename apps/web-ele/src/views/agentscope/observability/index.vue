<script lang="ts" setup>
import type {
  AgentTraceRow,
  SessionTraceRow,
  TraceAnalytics,
  TraceRun,
  UsageRow,
  UsageSummary,
} from '#/api/agentscope/observability';

import { computed, onMounted, ref } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  ElButton,
  ElCard,
  ElCol,
  ElEmpty,
  ElOption,
  ElRow,
  ElSelect,
  ElTable,
  ElTableColumn,
  ElTabPane,
  ElTabs,
  ElTag,
} from 'element-plus';

import { agentApi, observabilityApi } from '#/api/agentscope';
import { $t } from '#/locales';

import TraceTimeline from './TraceTimeline.vue';

const loading = ref(true);
const days = ref(30);
const tab = ref('overview');
const dayOptions = [7, 14, 30, 90];

// ---- data ----
const analytics = ref<TraceAnalytics>();
const agents = ref<AgentTraceRow[]>([]);
const summary = ref<UsageSummary>();
const recent = ref<UsageRow[]>([]);
const agentNames = ref<Record<string, string>>({});

// drill-down state for the Agents & Sessions tab
const selectedAgent = ref<AgentTraceRow | null>(null);
const sessions = ref<SessionTraceRow[]>([]);
const selectedSession = ref<null | SessionTraceRow>(null);
const runs = ref<TraceRun[]>([]);

function fmt(n: number) {
  return new Intl.NumberFormat().format(n ?? 0);
}

function fmtMs(ms: number): string {
  if (!ms) return '0ms';
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

function agentLabel(id: string): string {
  return agentNames.value[id] || id || 'unknown';
}

const maxDayTokens = computed(() =>
  Math.max(
    1,
    ...(analytics.value?.by_day ?? []).map((d) => d.input + d.output),
  ),
);

const hasTrace = computed(() => (analytics.value?.total_runs ?? 0) > 0);

async function loadAgentNames() {
  try {
    const res = await agentApi.listAgents();
    const map: Record<string, string> = {};
    for (const a of res.agents ?? []) {
      map[a.id] = a.data?.name || a.id;
    }
    agentNames.value = map;
  } catch {
    // best-effort: fall back to raw ids
  }
}

async function load() {
  loading.value = true;
  try {
    const [an, ag, s, r] = await Promise.all([
      observabilityApi.traceAnalytics(days.value),
      observabilityApi.traceAgents(days.value),
      observabilityApi.usageSummary(days.value),
      observabilityApi.usageRecent(50),
    ]);
    analytics.value = an;
    agents.value = ag.items ?? [];
    summary.value = s;
    recent.value = r.items ?? [];
  } finally {
    loading.value = false;
  }
}

async function openAgent(row: AgentTraceRow) {
  selectedAgent.value = row;
  selectedSession.value = null;
  const res = await observabilityApi.traceSessions(row.agent_id, days.value);
  sessions.value = res.items ?? [];
}

async function openSession(row: SessionTraceRow) {
  selectedSession.value = row;
  const res = await observabilityApi.traceSession(row.session_id);
  runs.value = res.runs ?? [];
}

function backToAgents() {
  selectedAgent.value = null;
  sessions.value = [];
}

function backToSessions() {
  selectedSession.value = null;
  runs.value = [];
}

onMounted(async () => {
  await loadAgentNames();
  await load();
});
</script>

<template>
  <Page :title="$t('agentscope.menu.observability')">
    <template #extra>
      <div class="flex items-center gap-2">
        <ElSelect v-model="days" class="w-32" @change="load">
          <ElOption
            v-for="d in dayOptions"
            :key="d"
            :label="$t('agentscope.obs.lastDays', { days: d })"
            :value="d"
          />
        </ElSelect>
        <ElButton :loading="loading" @click="load">
          {{ $t('agentscope.common.refresh') }}
        </ElButton>
      </div>
    </template>

    <ElTabs v-model="tab">
      <!-- ============ Overview / analytics ============ -->
      <ElTabPane :label="$t('agentscope.obs.tabOverview')" name="overview">
        <ElEmpty
          v-if="!loading && !hasTrace"
          :description="$t('agentscope.obs.noTrace')"
        />
        <template v-else>
          <ElRow :gutter="16">
            <ElCol :lg="6" :md="12" :xs="12" class="mb-4">
              <ElCard shadow="hover">
                <div class="kpi-label">
                  {{ $t('agentscope.obs.successRate') }}
                </div>
                <div class="kpi-value text-green-500">
                  {{ analytics?.success_rate ?? 0 }}%
                </div>
              </ElCard>
            </ElCol>
            <ElCol :lg="6" :md="12" :xs="12" class="mb-4">
              <ElCard shadow="hover">
                <div class="kpi-label">
                  {{ $t('agentscope.obs.totalRuns') }}
                </div>
                <div class="kpi-value">
                  {{ fmt(analytics?.total_runs ?? 0) }}
                </div>
              </ElCard>
            </ElCol>
            <ElCol :lg="6" :md="12" :xs="12" class="mb-4">
              <ElCard shadow="hover">
                <div class="kpi-label">
                  {{ $t('agentscope.obs.totalCalls') }}
                </div>
                <div class="kpi-value">
                  {{ fmt(analytics?.model_calls ?? 0) }}
                </div>
              </ElCard>
            </ElCol>
            <ElCol :lg="6" :md="12" :xs="12" class="mb-4">
              <ElCard shadow="hover">
                <div class="kpi-label">
                  {{ $t('agentscope.obs.toolCalls') }}
                </div>
                <div class="kpi-value">
                  {{ fmt(analytics?.tool_calls ?? 0) }}
                </div>
              </ElCard>
            </ElCol>
            <ElCol :lg="8" :md="12" :xs="12" class="mb-4">
              <ElCard shadow="hover">
                <div class="kpi-label">
                  {{ $t('agentscope.obs.avgLatency') }}
                </div>
                <div class="kpi-value">
                  {{ fmtMs(analytics?.avg_latency_ms ?? 0) }}
                </div>
              </ElCard>
            </ElCol>
            <ElCol :lg="8" :md="12" :xs="12" class="mb-4">
              <ElCard shadow="hover">
                <div class="kpi-label">
                  {{ $t('agentscope.obs.p95Latency') }}
                </div>
                <div class="kpi-value">
                  {{ fmtMs(analytics?.p95_latency_ms ?? 0) }}
                </div>
              </ElCard>
            </ElCol>
            <ElCol :lg="8" :md="12" :xs="12" class="mb-4">
              <ElCard shadow="hover">
                <div class="kpi-label">
                  {{ $t('agentscope.obs.p99Latency') }}
                </div>
                <div class="kpi-value">
                  {{ fmtMs(analytics?.p99_latency_ms ?? 0) }}
                </div>
              </ElCard>
            </ElCol>
          </ElRow>

          <ElRow :gutter="16">
            <!-- Token trend -->
            <ElCol :lg="14" :xs="24" class="mb-4">
              <ElCard shadow="never">
                <template #header>
                  {{ $t('agentscope.obs.tokenTrend') }}
                </template>
                <div class="trend">
                  <div
                    v-for="d in analytics?.by_day ?? []"
                    :key="d.date"
                    class="trend-col"
                  >
                    <div class="trend-bars">
                      <div
                        class="trend-bar trend-bar--in"
                        :style="{
                          height: `${(d.input / maxDayTokens) * 100}%`,
                        }"
                        :title="`${d.date} input ${d.input}`"
                      ></div>
                      <div
                        class="trend-bar trend-bar--out"
                        :style="{
                          height: `${(d.output / maxDayTokens) * 100}%`,
                        }"
                        :title="`${d.date} output ${d.output}`"
                      ></div>
                    </div>
                    <div class="trend-label">{{ d.date.slice(5) }}</div>
                  </div>
                </div>
                <div class="trend-legend">
                  <span class="legend-item">
                    <i class="dot dot--in"></i>
                    <span>{{ $t('agentscope.obs.inputTokens') }}</span>
                  </span>
                  <span class="legend-item">
                    <i class="dot dot--out"></i>
                    <span>{{ $t('agentscope.obs.outputTokens') }}</span>
                  </span>
                </div>
              </ElCard>
            </ElCol>
            <!-- Top tools -->
            <ElCol :lg="10" :xs="24" class="mb-4">
              <ElCard shadow="never">
                <template #header>{{ $t('agentscope.obs.topTools') }}</template>
                <ElTable :data="analytics?.top_tools ?? []" size="small">
                  <ElTableColumn
                    :label="$t('agentscope.obs.toolName')"
                    prop="name"
                  />
                  <ElTableColumn
                    :label="$t('agentscope.obs.calls')"
                    prop="calls"
                    width="70"
                  />
                  <ElTableColumn
                    :label="$t('agentscope.obs.errors')"
                    prop="errors"
                    width="70"
                  />
                  <ElTableColumn
                    :label="$t('agentscope.obs.avgLatency')"
                    width="90"
                  >
                    <template #default="{ row }">
                      {{ fmtMs(row.avg_latency_ms) }}
                    </template>
                  </ElTableColumn>
                </ElTable>
              </ElCard>
            </ElCol>
          </ElRow>
        </template>
      </ElTabPane>

      <!-- ============ Agents & sessions & trace ============ -->
      <ElTabPane :label="$t('agentscope.obs.tabAgents')" name="agents">
        <!-- level 1: agents -->
        <template v-if="!selectedAgent">
          <ElEmpty
            v-if="!loading && agents.length === 0"
            :description="$t('agentscope.obs.noTrace')"
          />
          <ElCard v-else shadow="never">
            <ElTable :data="agents" stripe @row-click="openAgent">
              <ElTableColumn :label="$t('agentscope.obs.agents')">
                <template #default="{ row }">
                  <div class="agent-cell">
                    <IconifyIcon icon="lucide:bot" class="agent-cell__icon" />
                    <span>{{ agentLabel(row.agent_id) }}</span>
                  </div>
                </template>
              </ElTableColumn>
              <ElTableColumn
                :label="$t('agentscope.obs.sessions')"
                prop="sessions"
                width="90"
              />
              <ElTableColumn
                :label="$t('agentscope.obs.runs')"
                prop="runs"
                width="80"
              />
              <ElTableColumn
                :label="$t('agentscope.obs.successRate')"
                width="90"
              >
                <template #default="{ row }">
                  <ElTag
                    size="small"
                    :type="row.success_rate >= 95 ? 'success' : 'warning'"
                  >
                    {{ row.success_rate }}%
                  </ElTag>
                </template>
              </ElTableColumn>
              <ElTableColumn
                :label="$t('agentscope.obs.p95Latency')"
                width="100"
              >
                <template #default="{ row }">
                  {{ fmtMs(row.p95_latency_ms) }}
                </template>
              </ElTableColumn>
              <ElTableColumn :label="$t('agentscope.obs.tokens')" width="100">
                <template #default="{ row }">
                  {{ fmt(row.total_tokens) }}
                </template>
              </ElTableColumn>
              <ElTableColumn :label="$t('agentscope.obs.cost')" width="100">
                <template #default="{ row }">
                  ${{ row.cost.toFixed(4) }}
                </template>
              </ElTableColumn>
              <ElTableColumn
                :label="$t('agentscope.obs.lastActive')"
                width="170"
              >
                <template #default="{ row }">
                  {{
                    row.last_active
                      ? new Date(row.last_active).toLocaleString()
                      : '-'
                  }}
                </template>
              </ElTableColumn>
              <ElTableColumn width="90">
                <template #default>
                  <ElButton link type="primary">
                    {{ $t('agentscope.obs.viewSessions') }}
                  </ElButton>
                </template>
              </ElTableColumn>
            </ElTable>
          </ElCard>
        </template>

        <!-- level 2: sessions of selected agent -->
        <template v-else-if="!selectedSession">
          <div class="crumb">
            <ElButton link @click="backToAgents">
              <IconifyIcon icon="lucide:arrow-left" />
              {{ $t('agentscope.obs.backToAgents') }}
            </ElButton>
            <span class="crumb__title">
              {{
                $t('agentscope.obs.sessionsOf', {
                  agent: agentLabel(selectedAgent.agent_id),
                })
              }}
            </span>
          </div>
          <ElCard shadow="never">
            <ElTable :data="sessions" stripe @row-click="openSession">
              <ElTableColumn :label="$t('agentscope.obs.sessions')">
                <template #default="{ row }">
                  <span class="mono">{{ row.session_id }}</span>
                </template>
              </ElTableColumn>
              <ElTableColumn :label="$t('agentscope.obs.source')" width="110">
                <template #default="{ row }">
                  <ElTag
                    size="small"
                    :type="row.source === 'app' ? 'success' : 'info'"
                  >
                    {{ row.source }}
                  </ElTag>
                </template>
              </ElTableColumn>
              <ElTableColumn
                :label="$t('agentscope.obs.runs')"
                prop="runs"
                width="70"
              />
              <ElTableColumn :label="$t('agentscope.obs.toolCalls')" width="90">
                <template #default="{ row }">{{ row.tool_calls }}</template>
              </ElTableColumn>
              <ElTableColumn :label="$t('agentscope.obs.tokens')" width="100">
                <template #default="{ row }">
                  {{ fmt(row.total_tokens) }}
                </template>
              </ElTableColumn>
              <ElTableColumn :label="$t('agentscope.obs.cost')" width="100">
                <template #default="{ row }">
                  ${{ row.cost.toFixed(4) }}
                </template>
              </ElTableColumn>
              <ElTableColumn
                :label="$t('agentscope.obs.lastActive')"
                width="170"
              >
                <template #default="{ row }">
                  {{
                    row.last_active
                      ? new Date(row.last_active).toLocaleString()
                      : '-'
                  }}
                </template>
              </ElTableColumn>
              <ElTableColumn width="90">
                <template #default>
                  <ElButton link type="primary">
                    {{ $t('agentscope.obs.viewTrace') }}
                  </ElButton>
                </template>
              </ElTableColumn>
            </ElTable>
          </ElCard>
        </template>

        <!-- level 3: trace timeline -->
        <template v-else>
          <div class="crumb">
            <ElButton link @click="backToSessions">
              <IconifyIcon icon="lucide:arrow-left" />
              {{ $t('agentscope.obs.backToSessions') }}
            </ElButton>
            <span class="crumb__title mono">
              {{ selectedSession.session_id }}
            </span>
          </div>
          <ElCard shadow="never">
            <TraceTimeline :runs="runs" />
          </ElCard>
        </template>
      </ElTabPane>

      <!-- ============ Usage & cost ============ -->
      <ElTabPane :label="$t('agentscope.obs.tabUsage')" name="usage">
        <ElRow :gutter="16">
          <ElCol :lg="6" :md="12" :xs="12" class="mb-4">
            <ElCard shadow="hover">
              <div class="kpi-label">{{ $t('agentscope.obs.totalCalls') }}</div>
              <div class="kpi-value">{{ fmt(summary?.total_calls ?? 0) }}</div>
            </ElCard>
          </ElCol>
          <ElCol :lg="6" :md="12" :xs="12" class="mb-4">
            <ElCard shadow="hover">
              <div class="kpi-label">
                {{ $t('agentscope.obs.inputTokens') }}
              </div>
              <div class="kpi-value">
                {{ fmt(summary?.total_input_tokens ?? 0) }}
              </div>
            </ElCard>
          </ElCol>
          <ElCol :lg="6" :md="12" :xs="12" class="mb-4">
            <ElCard shadow="hover">
              <div class="kpi-label">
                {{ $t('agentscope.obs.outputTokens') }}
              </div>
              <div class="kpi-value">
                {{ fmt(summary?.total_output_tokens ?? 0) }}
              </div>
            </ElCard>
          </ElCol>
          <ElCol :lg="6" :md="12" :xs="12" class="mb-4">
            <ElCard shadow="hover">
              <div class="kpi-label">{{ $t('agentscope.obs.estCost') }}</div>
              <div class="kpi-value">
                ${{ (summary?.estimated_cost_usd ?? 0).toFixed(4) }}
              </div>
            </ElCard>
          </ElCol>
        </ElRow>

        <ElCard class="mb-4" shadow="never">
          <template #header>{{ $t('agentscope.obs.byModel') }}</template>
          <ElTable :data="summary?.by_model ?? []" stripe>
            <ElTableColumn
              :label="$t('agentscope.obs.model')"
              prop="model_name"
            />
            <ElTableColumn :label="$t('agentscope.obs.calls')" prop="calls" />
            <ElTableColumn :label="$t('agentscope.obs.inputTokens')">
              <template #default="{ row }">{{ fmt(row.input) }}</template>
            </ElTableColumn>
            <ElTableColumn :label="$t('agentscope.obs.outputTokens')">
              <template #default="{ row }">{{ fmt(row.output) }}</template>
            </ElTableColumn>
            <ElTableColumn :label="$t('agentscope.obs.estCost')">
              <template #default="{ row }">${{ row.cost.toFixed(4) }}</template>
            </ElTableColumn>
          </ElTable>
        </ElCard>

        <ElCard shadow="never">
          <template #header>{{ $t('agentscope.obs.recent') }}</template>
          <ElTable :data="recent" stripe>
            <ElTableColumn :label="$t('agentscope.obs.time')" width="180">
              <template #default="{ row }">
                {{ new Date(row.created_at).toLocaleString() }}
              </template>
            </ElTableColumn>
            <ElTableColumn :label="$t('agentscope.obs.source')" width="120">
              <template #default="{ row }">
                <ElTag
                  size="small"
                  :type="row.source === 'app' ? 'success' : 'info'"
                >
                  {{ row.source }}
                </ElTag>
              </template>
            </ElTableColumn>
            <ElTableColumn
              :label="$t('agentscope.obs.model')"
              prop="model_name"
            />
            <ElTableColumn
              :label="$t('agentscope.obs.inputTokens')"
              width="120"
            >
              <template #default="{ row }">
                {{ fmt(row.input_tokens) }}
              </template>
            </ElTableColumn>
            <ElTableColumn
              :label="$t('agentscope.obs.outputTokens')"
              width="120"
            >
              <template #default="{ row }">
                {{ fmt(row.output_tokens) }}
              </template>
            </ElTableColumn>
            <ElTableColumn :label="$t('agentscope.obs.estCost')" width="120">
              <template #default="{ row }">${{ row.cost.toFixed(4) }}</template>
            </ElTableColumn>
          </ElTable>
        </ElCard>
      </ElTabPane>
    </ElTabs>
  </Page>
</template>

<style scoped>
.kpi-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.kpi-value {
  margin-top: 6px;
  font-size: 28px;
  font-weight: 600;
}

.agent-cell {
  display: flex;
  gap: 8px;
  align-items: center;
}

.agent-cell__icon {
  font-size: 16px;
  color: var(--el-color-primary);
}

.mono {
  font-family: ui-monospace, monospace;
  font-size: 12px;
}

.crumb {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 12px;
}

.crumb__title {
  font-size: 14px;
  font-weight: 600;
}

/* token-trend mini bar chart */
.trend {
  display: flex;
  gap: 6px;
  align-items: flex-end;
  height: 180px;
  padding-top: 8px;
  overflow-x: auto;
}

.trend-col {
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: center;
  min-width: 24px;
  height: 100%;
}

.trend-bars {
  display: flex;
  flex: 1;
  gap: 2px;
  align-items: flex-end;
  justify-content: center;
  width: 100%;
  height: 100%;
}

.trend-bar {
  width: 9px;
  border-radius: 3px 3px 0 0;
  transition: height 0.3s;
}

.trend-bar--in {
  background: var(--el-color-primary);
}

.trend-bar--out {
  background: var(--el-color-success);
}

.trend-label {
  margin-top: 4px;
  font-size: 10px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}

.trend-legend {
  display: flex;
  gap: 16px;
  justify-content: center;
  margin-top: 10px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.legend-item {
  display: inline-flex;
  align-items: center;
}

.dot {
  display: inline-block;
  width: 9px;
  height: 9px;
  margin-right: 5px;
  border-radius: 2px;
}

.dot--in {
  background: var(--el-color-primary);
}

.dot--out {
  background: var(--el-color-success);
}
</style>
