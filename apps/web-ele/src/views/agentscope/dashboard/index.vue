<script lang="ts" setup>
import type { DashboardStats } from '#/api/agentscope';

import { onMounted, ref } from 'vue';

import { Page } from '@vben/common-ui';

import { ElCard, ElCol, ElEmpty, ElRow, ElSkeleton } from 'element-plus';

import { dashboardApi } from '#/api/agentscope';
import { $t } from '#/locales';

const loading = ref(true);
const stats = ref<DashboardStats>();

const cards = [
  { key: 'agents', label: $t('agentscope.menu.agents'), color: '#3b82f6' },
  {
    key: 'ontologies',
    label: $t('agentscope.menu.ontology'),
    color: '#8b5cf6',
  },
  {
    key: 'object_types',
    label: $t('agentscope.ontology.objectTypes'),
    color: '#06b6d4',
  },
  {
    key: 'objects',
    label: $t('agentscope.ontology.objects'),
    color: '#10b981',
  },
  {
    key: 'credentials',
    label: $t('agentscope.menu.credentials'),
    color: '#f59e0b',
  },
  { key: 'sessions', label: $t('agentscope.menu.sessions'), color: '#ef4444' },
  {
    key: 'action_types',
    label: $t('agentscope.ontology.actionTypes'),
    color: '#ec4899',
  },
  {
    key: 'link_types',
    label: $t('agentscope.ontology.linkTypes'),
    color: '#6366f1',
  },
] as const;

async function load() {
  loading.value = true;
  try {
    stats.value = await dashboardApi.getDashboardStats();
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <Page :title="$t('agentscope.menu.dashboard')">
    <ElSkeleton v-if="loading" :rows="5" animated />
    <ElEmpty v-else-if="!stats" :description="$t('agentscope.common.empty')" />
    <ElRow v-else :gutter="16">
      <ElCol
        v-for="card in cards"
        :key="card.key"
        :lg="6"
        :md="8"
        :sm="12"
        :xs="24"
        class="mb-4"
      >
        <ElCard shadow="hover">
          <div class="flex items-center justify-between">
            <div>
              <div class="text-foreground/60 text-sm">{{ card.label }}</div>
              <div class="mt-2 text-3xl font-semibold">
                {{ stats[card.key] ?? 0 }}
              </div>
            </div>
            <div
              class="h-12 w-2 rounded-full"
              :style="{ backgroundColor: card.color }"
            ></div>
          </div>
        </ElCard>
      </ElCol>
    </ElRow>
  </Page>
</template>
