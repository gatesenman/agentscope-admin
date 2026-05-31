<script lang="ts" setup>
import type { UsageRow, UsageSummary } from '#/api/agentscope/observability';

import { onMounted, ref } from 'vue';

import { Page } from '@vben/common-ui';

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
  ElTag,
} from 'element-plus';

import { observabilityApi } from '#/api/agentscope';
import { $t } from '#/locales';

const loading = ref(true);
const days = ref(30);
const summary = ref<UsageSummary>();
const recent = ref<UsageRow[]>([]);

const dayOptions = [7, 14, 30, 90];

function fmt(n: number) {
  return new Intl.NumberFormat().format(n ?? 0);
}

async function load() {
  loading.value = true;
  try {
    const [s, r] = await Promise.all([
      observabilityApi.usageSummary(days.value),
      observabilityApi.usageRecent(50),
    ]);
    summary.value = s;
    recent.value = r.items ?? [];
  } finally {
    loading.value = false;
  }
}

onMounted(load);
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

    <ElEmpty
      v-if="!loading && summary && summary.total_calls === 0"
      :description="$t('agentscope.obs.noData')"
    />

    <template v-else>
      <!-- Summary cards -->
      <ElRow :gutter="16">
        <ElCol :lg="6" :md="12" :sm="12" :xs="24" class="mb-4">
          <ElCard shadow="hover">
            <div class="text-foreground/60 text-sm">
              {{ $t('agentscope.obs.totalCalls') }}
            </div>
            <div class="mt-2 text-3xl font-semibold">
              {{ fmt(summary?.total_calls ?? 0) }}
            </div>
          </ElCard>
        </ElCol>
        <ElCol :lg="6" :md="12" :sm="12" :xs="24" class="mb-4">
          <ElCard shadow="hover">
            <div class="text-foreground/60 text-sm">
              {{ $t('agentscope.obs.inputTokens') }}
            </div>
            <div class="mt-2 text-3xl font-semibold">
              {{ fmt(summary?.total_input_tokens ?? 0) }}
            </div>
          </ElCard>
        </ElCol>
        <ElCol :lg="6" :md="12" :sm="12" :xs="24" class="mb-4">
          <ElCard shadow="hover">
            <div class="text-foreground/60 text-sm">
              {{ $t('agentscope.obs.outputTokens') }}
            </div>
            <div class="mt-2 text-3xl font-semibold">
              {{ fmt(summary?.total_output_tokens ?? 0) }}
            </div>
          </ElCard>
        </ElCol>
        <ElCol :lg="6" :md="12" :sm="12" :xs="24" class="mb-4">
          <ElCard shadow="hover">
            <div class="text-foreground/60 text-sm">
              {{ $t('agentscope.obs.estCost') }}
            </div>
            <div class="mt-2 text-3xl font-semibold">
              ${{ (summary?.estimated_cost_usd ?? 0).toFixed(4) }}
            </div>
          </ElCard>
        </ElCol>
      </ElRow>

      <!-- By model -->
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

      <!-- Recent calls (trace) -->
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
          <ElTableColumn :label="$t('agentscope.obs.inputTokens')" width="120">
            <template #default="{ row }">{{ fmt(row.input_tokens) }}</template>
          </ElTableColumn>
          <ElTableColumn :label="$t('agentscope.obs.outputTokens')" width="120">
            <template #default="{ row }">{{ fmt(row.output_tokens) }}</template>
          </ElTableColumn>
          <ElTableColumn :label="$t('agentscope.obs.estCost')" width="120">
            <template #default="{ row }">${{ row.cost.toFixed(4) }}</template>
          </ElTableColumn>
        </ElTable>
      </ElCard>
    </template>
  </Page>
</template>
