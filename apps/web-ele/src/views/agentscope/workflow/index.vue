<script lang="ts" setup>
import type { Workflow } from '#/api/agentscope/workflow';

import { onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';

import { Page } from '@vben/common-ui';

import {
  ElButton,
  ElCard,
  ElDialog,
  ElEmpty,
  ElForm,
  ElFormItem,
  ElInput,
  ElMessage,
  ElPopconfirm,
  ElSwitch,
  ElTable,
  ElTableColumn,
} from 'element-plus';

import { workflowApi } from '#/api/agentscope';
import { $t } from '#/locales';

const router = useRouter();
const loading = ref(false);
const workflows = ref<Workflow[]>([]);

const dialog = ref(false);
const saving = ref(false);
const form = reactive({ name: '', description: '', icon: '🔗' });

async function load() {
  loading.value = true;
  try {
    const res = await workflowApi.listWorkflows();
    workflows.value = res.items ?? [];
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  form.name = '';
  form.description = '';
  form.icon = '🔗';
  dialog.value = true;
}

async function create() {
  if (!form.name) {
    ElMessage.warning($t('agentscope.common.name'));
    return;
  }
  saving.value = true;
  try {
    const wf = await workflowApi.createWorkflow({ ...form });
    dialog.value = false;
    await router.push(`/agentscope/workflow/${wf.id}`);
  } finally {
    saving.value = false;
  }
}

async function toggle(row: Workflow) {
  await workflowApi.updateWorkflow(row.id, { enabled: !row.enabled });
  await load();
}

async function remove(row: Workflow) {
  await workflowApi.deleteWorkflow(row.id);
  ElMessage.success($t('agentscope.common.deleteSuccess'));
  await load();
}

function edit(row: Workflow) {
  router.push(`/agentscope/workflow/${row.id}`);
}

onMounted(load);
</script>

<template>
  <Page :title="$t('agentscope.menu.workflow')">
    <template #extra>
      <ElButton type="primary" @click="openCreate">
        {{ $t('agentscope.workflow.newWorkflow') }}
      </ElButton>
    </template>

    <ElCard shadow="never">
      <ElTable v-loading="loading" :data="workflows" stripe>
        <ElTableColumn :label="$t('agentscope.common.name')" min-width="220">
          <template #default="{ row }">
            <span style="margin-right: 6px">{{ row.icon }}</span>
            <strong>{{ row.name }}</strong>
            <div style="font-size: 12px; color: var(--el-text-color-secondary)">
              {{ row.description }}
            </div>
          </template>
        </ElTableColumn>
        <ElTableColumn :label="$t('agentscope.workflow.nodes')" width="100">
          <template #default="{ row }">
            {{ row.graph?.nodes?.length ?? 0 }}
          </template>
        </ElTableColumn>
        <ElTableColumn :label="$t('agentscope.common.enabled')" width="100">
          <template #default="{ row }">
            <ElSwitch :model-value="row.enabled" @change="toggle(row)" />
          </template>
        </ElTableColumn>
        <ElTableColumn :label="$t('agentscope.common.actions')" width="200">
          <template #default="{ row }">
            <ElButton link type="primary" @click="edit(row)">
              {{ $t('agentscope.workflow.editCanvas') }}
            </ElButton>
            <ElPopconfirm
              :title="$t('agentscope.common.confirmDelete')"
              @confirm="remove(row)"
            >
              <template #reference>
                <ElButton link type="danger">
                  {{ $t('agentscope.common.delete') }}
                </ElButton>
              </template>
            </ElPopconfirm>
          </template>
        </ElTableColumn>
        <template #empty>
          <ElEmpty :description="$t('agentscope.workflow.empty')" />
        </template>
      </ElTable>
    </ElCard>

    <ElDialog
      v-model="dialog"
      :title="$t('agentscope.workflow.newWorkflow')"
      width="480px"
    >
      <ElForm label-width="80px">
        <ElFormItem :label="$t('agentscope.knowledge.icon')">
          <ElInput v-model="form.icon" style="width: 80px" />
        </ElFormItem>
        <ElFormItem :label="$t('agentscope.common.name')">
          <ElInput v-model="form.name" />
        </ElFormItem>
        <ElFormItem :label="$t('agentscope.common.description')">
          <ElInput v-model="form.description" type="textarea" :rows="2" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="dialog = false">
          {{ $t('agentscope.common.cancel') }}
        </ElButton>
        <ElButton type="primary" :loading="saving" @click="create">
          {{ $t('agentscope.common.confirm') }}
        </ElButton>
      </template>
    </ElDialog>
  </Page>
</template>
