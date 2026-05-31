<script lang="ts" setup>
import type { McpServer, McpTool } from '#/api/agentscope/mcp';

import { onMounted, reactive, ref } from 'vue';

import { Page } from '@vben/common-ui';

import {
  ElButton,
  ElCard,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElMessage,
  ElOption,
  ElPopconfirm,
  ElSelect,
  ElSwitch,
  ElTable,
  ElTableColumn,
  ElTag,
} from 'element-plus';

import { mcpApi } from '#/api/agentscope';
import { $t } from '#/locales';

const loading = ref(false);
const servers = ref<McpServer[]>([]);

const dialog = ref(false);
const saving = ref(false);
const editingId = ref<string>('');

const form = reactive({
  name: '',
  description: '',
  transport: 'stdio' as 'http' | 'stdio',
  command: '',
  argsText: '',
  envText: '',
  url: '',
  headersText: '',
  timeout: null as null | number,
  is_stateful: true,
  enableToolsText: '',
  disableToolsText: '',
  execution_timeout: null as null | number,
  enabled: true,
});

// Test-connection state keyed by server id.
const testing = ref<string>('');
const testDialog = ref(false);
const testResult = ref<{ error: string; healthy: boolean; tools: McpTool[] }>({
  error: '',
  healthy: false,
  tools: [],
});

function linesToArray(text: string): string[] {
  return text
    .split('\n')
    .map((s) => s.trim())
    .filter(Boolean);
}

function linesToRecord(text: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const line of linesToArray(text)) {
    const idx = line.indexOf('=');
    if (idx > 0) out[line.slice(0, idx).trim()] = line.slice(idx + 1).trim();
  }
  return out;
}

function recordToLines(rec: Record<string, string>): string {
  return Object.entries(rec ?? {})
    .map(([k, v]) => `${k}=${v}`)
    .join('\n');
}

async function load() {
  loading.value = true;
  try {
    const res = await mcpApi.listMcpServers();
    servers.value = res.items ?? [];
  } finally {
    loading.value = false;
  }
}

function resetForm() {
  form.name = '';
  form.description = '';
  form.transport = 'stdio';
  form.command = '';
  form.argsText = '';
  form.envText = '';
  form.url = '';
  form.headersText = '';
  form.timeout = null;
  form.is_stateful = true;
  form.enableToolsText = '';
  form.disableToolsText = '';
  form.execution_timeout = null;
  form.enabled = true;
}

function openCreate() {
  editingId.value = '';
  resetForm();
  dialog.value = true;
}

function openEdit(row: McpServer) {
  editingId.value = row.id;
  form.name = row.name;
  form.description = row.description;
  form.transport = row.transport;
  form.command = row.command;
  form.argsText = (row.args ?? []).join('\n');
  form.envText = recordToLines(row.env);
  form.url = row.url;
  form.headersText = recordToLines(row.headers);
  form.timeout = row.timeout;
  form.is_stateful = row.is_stateful;
  form.enableToolsText = (row.enable_tools ?? []).join('\n');
  form.disableToolsText = (row.disable_tools ?? []).join('\n');
  form.execution_timeout = row.execution_timeout;
  form.enabled = row.enabled;
  dialog.value = true;
}

// HTTP transport supports stateless connections; STDIO must be stateful.
function onTransportChange(t: 'http' | 'stdio') {
  if (t === 'stdio') form.is_stateful = true;
}

function buildPayload(): Partial<McpServer> {
  return {
    name: form.name,
    description: form.description,
    transport: form.transport,
    command: form.command,
    args: linesToArray(form.argsText),
    env: linesToRecord(form.envText),
    url: form.url,
    headers: linesToRecord(form.headersText),
    timeout: form.timeout,
    is_stateful: form.transport === 'stdio' ? true : form.is_stateful,
    enable_tools: linesToArray(form.enableToolsText),
    disable_tools: linesToArray(form.disableToolsText),
    execution_timeout: form.execution_timeout,
    enabled: form.enabled,
  };
}

async function save() {
  if (!form.name) {
    ElMessage.warning($t('agentscope.mcp.nameRequired'));
    return;
  }
  if (form.transport === 'stdio' && !form.command) {
    ElMessage.warning($t('agentscope.mcp.commandRequired'));
    return;
  }
  if (form.transport === 'http' && !form.url) {
    ElMessage.warning($t('agentscope.mcp.urlRequired'));
    return;
  }
  saving.value = true;
  try {
    await (editingId.value
      ? mcpApi.updateMcpServer(editingId.value, buildPayload())
      : mcpApi.createMcpServer(buildPayload()));
    ElMessage.success($t('agentscope.common.save'));
    dialog.value = false;
    await load();
  } finally {
    saving.value = false;
  }
}

async function toggleEnabled(row: McpServer) {
  await mcpApi.updateMcpServer(row.id, { enabled: !row.enabled });
  await load();
}

async function remove(row: McpServer) {
  await mcpApi.deleteMcpServer(row.id);
  await load();
}

async function test(row: McpServer) {
  testing.value = row.id;
  try {
    const res = await mcpApi.testMcpServer(row.id);
    testResult.value = {
      error: res.error,
      healthy: res.healthy,
      tools: res.tools ?? [],
    };
    testDialog.value = true;
    await load();
  } finally {
    testing.value = '';
  }
}

function statusType(status: string): 'danger' | 'info' | 'success' {
  if (status === 'healthy') return 'success';
  if (status === 'unhealthy') return 'danger';
  return 'info';
}

onMounted(load);
</script>

<template>
  <Page
    :description="$t('agentscope.mcp.description')"
    :title="$t('agentscope.menu.mcp')"
  >
    <template #extra>
      <ElButton type="primary" @click="openCreate">
        {{ $t('agentscope.mcp.newServer') }}
      </ElButton>
    </template>

    <ElCard shadow="never">
      <ElTable v-loading="loading" :data="servers" stripe>
        <ElTableColumn :label="$t('agentscope.common.name')">
          <template #default="{ row }">
            <div class="font-medium">{{ row.name }}</div>
            <div class="text-muted-foreground text-xs">
              {{ row.description }}
            </div>
          </template>
        </ElTableColumn>
        <ElTableColumn :label="$t('agentscope.mcp.transport')" width="100">
          <template #default="{ row }">
            <ElTag size="small">{{ row.transport }}</ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn :label="$t('agentscope.mcp.target')">
          <template #default="{ row }">
            <code class="text-xs">
              {{ row.transport === 'http' ? row.url : row.command }}
            </code>
          </template>
        </ElTableColumn>
        <ElTableColumn :label="$t('agentscope.mcp.health')" width="150">
          <template #default="{ row }">
            <ElTag :type="statusType(row.last_status)" size="small">
              {{ $t(`agentscope.mcp.status.${row.last_status}`) }}
            </ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn :label="$t('agentscope.mcp.enabled')" width="90">
          <template #default="{ row }">
            <ElSwitch :model-value="row.enabled" @change="toggleEnabled(row)" />
          </template>
        </ElTableColumn>
        <ElTableColumn :label="$t('agentscope.common.actions')" width="220">
          <template #default="{ row }">
            <ElButton
              :loading="testing === row.id"
              link
              type="primary"
              @click="test(row)"
            >
              {{ $t('agentscope.mcp.test') }}
            </ElButton>
            <ElButton link type="primary" @click="openEdit(row)">
              {{ $t('agentscope.common.edit') }}
            </ElButton>
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
      :title="
        editingId
          ? $t('agentscope.mcp.editServer')
          : $t('agentscope.mcp.newServer')
      "
      width="600px"
    >
      <ElForm label-position="top">
        <ElFormItem :label="$t('agentscope.common.name')">
          <ElInput v-model="form.name" />
        </ElFormItem>
        <ElFormItem :label="$t('agentscope.mcp.descriptionField')">
          <ElInput v-model="form.description" />
        </ElFormItem>
        <ElFormItem :label="$t('agentscope.mcp.transport')">
          <ElSelect
            v-model="form.transport"
            class="w-full"
            @change="onTransportChange"
          >
            <ElOption label="stdio" value="stdio" />
            <ElOption label="http" value="http" />
          </ElSelect>
        </ElFormItem>

        <template v-if="form.transport === 'stdio'">
          <ElFormItem :label="$t('agentscope.mcp.command')">
            <ElInput v-model="form.command" placeholder="npx" />
          </ElFormItem>
          <ElFormItem :label="$t('agentscope.mcp.args')">
            <ElInput
              v-model="form.argsText"
              :rows="3"
              placeholder="-y&#10;@modelcontextprotocol/server-filesystem"
              type="textarea"
            />
            <div class="text-muted-foreground mt-1 text-xs">
              {{ $t('agentscope.mcp.argsHint') }}
            </div>
          </ElFormItem>
          <ElFormItem :label="$t('agentscope.mcp.env')">
            <ElInput
              v-model="form.envText"
              :rows="2"
              placeholder="KEY=value"
              type="textarea"
            />
            <div class="text-muted-foreground mt-1 text-xs">
              {{ $t('agentscope.mcp.kvHint') }}
            </div>
          </ElFormItem>
        </template>

        <template v-else>
          <ElFormItem :label="$t('agentscope.mcp.url')">
            <ElInput v-model="form.url" placeholder="https://host/mcp" />
          </ElFormItem>
          <ElFormItem :label="$t('agentscope.mcp.headers')">
            <ElInput
              v-model="form.headersText"
              :rows="2"
              placeholder="Authorization=Bearer xxx"
              type="textarea"
            />
            <div class="text-muted-foreground mt-1 text-xs">
              {{ $t('agentscope.mcp.kvHint') }}
            </div>
          </ElFormItem>
          <ElFormItem :label="$t('agentscope.mcp.timeout')">
            <ElInputNumber v-model="form.timeout" :min="0" />
          </ElFormItem>
          <ElFormItem :label="$t('agentscope.mcp.stateful')">
            <ElSwitch v-model="form.is_stateful" />
            <div class="text-muted-foreground ml-3 text-xs">
              {{ $t('agentscope.mcp.statefulHint') }}
            </div>
          </ElFormItem>
        </template>

        <ElFormItem :label="$t('agentscope.mcp.enableTools')">
          <ElInput v-model="form.enableToolsText" :rows="2" type="textarea" />
          <div class="text-muted-foreground mt-1 text-xs">
            {{ $t('agentscope.mcp.toolFilterHint') }}
          </div>
        </ElFormItem>
        <ElFormItem :label="$t('agentscope.mcp.disableTools')">
          <ElInput v-model="form.disableToolsText" :rows="2" type="textarea" />
        </ElFormItem>
        <ElFormItem :label="$t('agentscope.mcp.enabled')">
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

    <ElDialog
      v-model="testDialog"
      :title="$t('agentscope.mcp.testResult')"
      width="520px"
    >
      <div class="mb-3">
        <ElTag :type="testResult.healthy ? 'success' : 'danger'">
          {{
            testResult.healthy
              ? $t('agentscope.mcp.status.healthy')
              : $t('agentscope.mcp.status.unhealthy')
          }}
        </ElTag>
      </div>
      <div v-if="testResult.error" class="text-danger mb-3 text-sm">
        {{ testResult.error }}
      </div>
      <ElTable
        v-if="testResult.tools.length > 0"
        :data="testResult.tools"
        stripe
      >
        <ElTableColumn :label="$t('agentscope.mcp.toolName')" prop="name" />
        <ElTableColumn
          :label="$t('agentscope.mcp.toolDescription')"
          prop="description"
        />
      </ElTable>
      <div v-else-if="testResult.healthy" class="text-muted-foreground text-sm">
        {{ $t('agentscope.mcp.noTools') }}
      </div>
    </ElDialog>
  </Page>
</template>
