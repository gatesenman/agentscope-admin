<script lang="ts" setup>
import type {
  AgentRecord,
  CredentialRecord,
  ModelCard,
} from '#/api/agentscope';
import type { ScheduleRecord } from '#/api/agentscope/schedule';

import { onMounted, reactive, ref } from 'vue';

import { Page } from '@vben/common-ui';

import {
  ElButton,
  ElCard,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElMessage,
  ElOption,
  ElPopconfirm,
  ElSelect,
  ElSwitch,
  ElTable,
  ElTableColumn,
  ElTag,
} from 'element-plus';

import {
  agentApi,
  agentProfileApi,
  credentialApi,
  modelApi,
  scheduleApi,
} from '#/api/agentscope';
import { $t } from '#/locales';

const loading = ref(false);
const schedules = ref<ScheduleRecord[]>([]);
const agents = ref<AgentRecord[]>([]);
const credentials = ref<CredentialRecord[]>([]);
const models = ref<ModelCard[]>([]);

const permissionModes = [
  'default',
  'accept_edits',
  'explore',
  'bypass',
  'dont_ask',
];

const dialog = ref(false);
const saving = ref(false);
const form = reactive({
  name: '',
  description: '',
  agent_id: '',
  cron_expression: '0 9 * * *',
  timezone: 'UTC',
  credential_id: '',
  model: '',
  permission_mode: 'dont_ask',
  enabled: true,
  stateful: false,
});

function agentName(id: string): string {
  return agents.value.find((a) => a.id === id)?.data?.name ?? id;
}

function credentialType(id: string): string {
  return credentials.value.find((c) => c.id === id)?.data?.type ?? '';
}

async function loadModels(credentialId: string) {
  models.value = [];
  const type = credentialType(credentialId);
  if (!type) return;
  try {
    const res = await modelApi.listModels(type);
    models.value = res.models ?? [];
  } catch {
    // provider may not support listing; manual entry still allowed
  }
}

async function load() {
  loading.value = true;
  try {
    const [sch, ag, cr] = await Promise.all([
      scheduleApi.listSchedules(),
      agentApi.listAgents(),
      credentialApi.listCredentials(),
    ]);
    schedules.value = sch.schedules ?? [];
    agents.value = ag.agents ?? [];
    credentials.value = cr.credentials ?? [];
  } finally {
    loading.value = false;
  }
}

// When an agent is chosen, prefill model defaults from its saved profile.
async function onAgentChange(id: string) {
  const p = await agentProfileApi.getProfile(id);
  if (!p) return;
  if (p.default_credential_id) {
    form.credential_id = p.default_credential_id;
    await loadModels(form.credential_id);
  }
  if (p.default_model) form.model = p.default_model;
  if (p.permission_mode) form.permission_mode = p.permission_mode;
}

function onCredentialChange(id: string) {
  form.model = '';
  void loadModels(id);
}

function openCreate() {
  form.name = '';
  form.description = '';
  form.agent_id = agents.value[0]?.id ?? '';
  form.cron_expression = '0 9 * * *';
  form.timezone = 'UTC';
  form.credential_id = '';
  form.model = '';
  form.permission_mode = 'dont_ask';
  form.enabled = true;
  form.stateful = false;
  models.value = [];
  if (form.agent_id) void onAgentChange(form.agent_id);
  dialog.value = true;
}

async function save() {
  if (!form.name || !form.agent_id || !form.cron_expression) {
    ElMessage.warning($t('agentscope.schedule.required'));
    return;
  }
  if (!form.credential_id || !form.model) {
    ElMessage.warning($t('agentscope.schedule.modelRequired'));
    return;
  }
  saving.value = true;
  try {
    await scheduleApi.createSchedule({
      name: form.name,
      description: form.description,
      agent_id: form.agent_id,
      cron_expression: form.cron_expression,
      timezone: form.timezone,
      chat_model_config: {
        type: credentialType(form.credential_id),
        credential_id: form.credential_id,
        model: form.model,
        parameters: {},
      },
      permission_mode: form.permission_mode,
      enabled: form.enabled,
      stateful: form.stateful,
    });
    ElMessage.success($t('agentscope.common.create'));
    dialog.value = false;
    await load();
  } finally {
    saving.value = false;
  }
}

async function toggleEnabled(row: ScheduleRecord) {
  await scheduleApi.updateSchedule(row.id, { enabled: !row.data.enabled });
  await load();
}

async function remove(row: ScheduleRecord) {
  await scheduleApi.deleteSchedule(row.id);
  await load();
}

onMounted(load);
</script>

<template>
  <Page :title="$t('agentscope.menu.schedules')">
    <template #extra>
      <ElButton type="primary" @click="openCreate">
        {{ $t('agentscope.schedule.newSchedule') }}
      </ElButton>
    </template>

    <ElCard shadow="never">
      <ElTable v-loading="loading" :data="schedules" stripe>
        <ElTableColumn :label="$t('agentscope.common.name')">
          <template #default="{ row }">{{ row.data?.name || row.id }}</template>
        </ElTableColumn>
        <ElTableColumn :label="$t('agentscope.schedule.agent')">
          <template #default="{ row }">{{ agentName(row.agent_id) }}</template>
        </ElTableColumn>
        <ElTableColumn :label="$t('agentscope.schedule.cron')" width="140">
          <template #default="{ row }">
            <code>{{ row.data?.cron_expression }}</code>
          </template>
        </ElTableColumn>
        <ElTableColumn
          :label="$t('agentscope.schedule.timezone')"
          prop="data.timezone"
          width="110"
        />
        <ElTableColumn
          :label="$t('agentscope.agent.permissionMode')"
          width="140"
        >
          <template #default="{ row }">
            <ElTag size="small" type="info">
              {{
                $t(`agentscope.agent.permission.${row.data?.permission_mode}`)
              }}
            </ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn :label="$t('agentscope.schedule.enabled')" width="90">
          <template #default="{ row }">
            <ElSwitch
              :model-value="row.data?.enabled"
              @change="toggleEnabled(row)"
            />
          </template>
        </ElTableColumn>
        <ElTableColumn :label="$t('agentscope.common.actions')" width="90">
          <template #default="{ row }">
            <ElPopconfirm
              :title="$t('agentscope.common.deleteConfirm')"
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
      </ElTable>
    </ElCard>

    <ElDialog
      v-model="dialog"
      :title="$t('agentscope.schedule.newSchedule')"
      width="560px"
    >
      <ElForm label-position="top">
        <ElFormItem :label="$t('agentscope.common.name')">
          <ElInput v-model="form.name" />
        </ElFormItem>
        <ElFormItem :label="$t('agentscope.schedule.description')">
          <ElInput v-model="form.description" />
        </ElFormItem>
        <ElFormItem :label="$t('agentscope.schedule.agent')">
          <ElSelect
            v-model="form.agent_id"
            class="w-full"
            @change="onAgentChange"
          >
            <ElOption
              v-for="a in agents"
              :key="a.id"
              :label="a.data?.name || a.id"
              :value="a.id"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem :label="$t('agentscope.schedule.cron')">
          <ElInput v-model="form.cron_expression" placeholder="0 9 * * *" />
          <div class="text-muted-foreground mt-1 text-xs">
            {{ $t('agentscope.schedule.cronHint') }}
          </div>
        </ElFormItem>
        <ElFormItem :label="$t('agentscope.schedule.timezone')">
          <ElInput v-model="form.timezone" placeholder="UTC" />
        </ElFormItem>
        <ElFormItem :label="$t('agentscope.agent.defaultCredential')">
          <ElSelect
            v-model="form.credential_id"
            class="w-full"
            @change="onCredentialChange"
          >
            <ElOption
              v-for="c in credentials"
              :key="c.id"
              :label="`${c.data?.name || c.id} · ${c.data?.type}`"
              :value="c.id"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem :label="$t('agentscope.agent.defaultModel')">
          <ElSelect v-model="form.model" allow-create class="w-full" filterable>
            <ElOption
              v-for="m in models"
              :key="m.name"
              :label="m.name"
              :value="m.name"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem :label="$t('agentscope.agent.permissionMode')">
          <ElSelect v-model="form.permission_mode" class="w-full">
            <ElOption
              v-for="pm in permissionModes"
              :key="pm"
              :label="$t(`agentscope.agent.permission.${pm}`)"
              :value="pm"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem :label="$t('agentscope.schedule.stateful')">
          <ElSwitch v-model="form.stateful" />
          <div class="text-muted-foreground ml-3 text-xs">
            {{ $t('agentscope.schedule.statefulHint') }}
          </div>
        </ElFormItem>
        <ElFormItem :label="$t('agentscope.schedule.enabled')">
          <ElSwitch v-model="form.enabled" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="dialog = false">
          {{ $t('agentscope.common.cancel') }}
        </ElButton>
        <ElButton :loading="saving" type="primary" @click="save">
          {{ $t('agentscope.common.save') }}
        </ElButton>
      </template>
    </ElDialog>
  </Page>
</template>
