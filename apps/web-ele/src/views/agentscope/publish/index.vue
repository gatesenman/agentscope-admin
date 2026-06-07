<script lang="ts" setup>
import type { AgentRecord } from '#/api/agentscope';
import type { AppApiKey, PublishedApp } from '#/api/agentscope/publish';

import { computed, onMounted, reactive, ref } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  ElButton,
  ElCard,
  ElDialog,
  ElDrawer,
  ElEmpty,
  ElForm,
  ElFormItem,
  ElInput,
  ElLink,
  ElMessage,
  ElMessageBox,
  ElOption,
  ElPopconfirm,
  ElSelect,
  ElSwitch,
  ElTable,
  ElTableColumn,
  ElTabPane,
  ElTabs,
  ElTag,
} from 'element-plus';

import { agentApi, publishApi } from '#/api/agentscope';
import { $t } from '#/locales';

const loading = ref(false);
const apps = ref<{ app: PublishedApp; key_count: number }[]>([]);
const agents = ref<AgentRecord[]>([]);

const permissionModes = [
  'default',
  'accept_edits',
  'explore',
  'bypass',
  'dont_ask',
];

// ---- publish dialog ----
const dialog = ref(false);
const saving = ref(false);
const form = reactive({
  agent_id: '',
  name: '',
  icon: 'lucide:bot',
  description: '',
  opening_statement: '',
  suggested_questions: '',
});

function agentName(id: string): string {
  return agents.value.find((a) => a.id === id)?.data?.name ?? id;
}

async function load() {
  loading.value = true;
  try {
    const [a, ag] = await Promise.all([
      publishApi.listApps(),
      agentApi.listAgents(),
    ]);
    apps.value = a.items ?? [];
    agents.value = ag.agents ?? [];
  } finally {
    loading.value = false;
  }
}

function openPublish() {
  form.agent_id = agents.value[0]?.id ?? '';
  form.name = '';
  form.icon = 'lucide:bot';
  form.description = '';
  form.opening_statement = '';
  form.suggested_questions = '';
  dialog.value = true;
}

async function doPublish() {
  if (!form.agent_id) {
    ElMessage.warning($t('agentscope.publish.selectAgent'));
    return;
  }
  saving.value = true;
  try {
    await publishApi.publishApp({
      agent_id: form.agent_id,
      name: form.name || agentName(form.agent_id),
      icon: form.icon,
      description: form.description,
      opening_statement: form.opening_statement,
      suggested_questions: form.suggested_questions
        .split('\n')
        .map((s) => s.trim())
        .filter(Boolean),
    });
    ElMessage.success($t('agentscope.publish.published'));
    dialog.value = false;
    await load();
  } finally {
    saving.value = false;
  }
}

async function toggleEnabled(row: PublishedApp) {
  await publishApi.updateApp(row.id, { enabled: !row.enabled });
  await load();
}

async function removeApp(row: PublishedApp) {
  await publishApi.deleteApp(row.id);
  ElMessage.success($t('agentscope.common.deleteSuccess'));
  if (current.value?.id === row.id) drawer.value = false;
  await load();
}

// ---- detail drawer ----
const drawer = ref(false);
const current = ref<null | PublishedApp>(null);
const keys = ref<AppApiKey[]>([]);
const activeTab = ref('overview');

const webAppUrl = computed(() =>
  current.value ? publishApi.webAppUrl(current.value.token) : '',
);
const apiEndpoint = computed(() =>
  current.value
    ? `${publishApi.apiBaseUrl()}/v1/apps/${current.value.token}/chat-messages`
    : '',
);
const curlSnippet = computed(() =>
  current.value
    ? String.raw`curl -X POST "${apiEndpoint.value}" \
  -H "Authorization: Bearer <YOUR_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"query": "你好", "response_mode": "blocking"}'`
    : '',
);
const iframeSnippet = computed(() =>
  current.value
    ? `<iframe
  src="${webAppUrl.value}"
  title="${current.value.name}"
  style="width:100%;height:700px;border:0;border-radius:12px"
  allow="microphone"
  allowfullscreen>
</iframe>`
    : '',
);
// Use a tag-name variable so no literal closing script tag appears in this
// SFC's own block (a literal one would terminate the block early).
const tag = 'script';
const bubbleSnippet = computed(() =>
  current.value
    ? [
        `<${tag}>`,
        `  // url required; color/width/height/title optional`,
        `  window.AGENTSCOPE_APP = { url: "${webAppUrl.value}", color: "#2563eb" };`,
        `</${tag}>`,
        `<${tag} src="${publishApi.apiBaseUrl()}/static/embed.js" defer></${tag}>`,
      ].join('\n')
    : '',
);

async function openDetail(row: PublishedApp) {
  current.value = { ...row };
  activeTab.value = 'overview';
  drawer.value = true;
  await loadKeys();
}

async function loadKeys() {
  if (!current.value) return;
  const res = await publishApi.listKeys(current.value.id);
  keys.value = res.items ?? [];
}

async function saveOverview() {
  if (!current.value) return;
  await publishApi.updateApp(current.value.id, {
    name: current.value.name,
    icon: current.value.icon,
    description: current.value.description,
    opening_statement: current.value.opening_statement,
    permission_mode: current.value.permission_mode,
    suggested_questions: current.value.suggested_questions,
  });
  ElMessage.success($t('agentscope.common.saveSuccess'));
  await load();
}

const newKeyName = ref('');
async function createKey() {
  if (!current.value) return;
  const res = await publishApi.createKey(
    current.value.id,
    newKeyName.value || 'default',
  );
  newKeyName.value = '';
  await loadKeys();
  await ElMessageBox.alert(res.key, $t('agentscope.publish.keyCreated'), {
    confirmButtonText: $t('agentscope.publish.copyKey'),
    callback: () => copy(res.key),
  });
}

async function revoke(key: AppApiKey) {
  if (!current.value) return;
  await publishApi.revokeKey(current.value.id, key.id);
  await loadKeys();
}

async function copy(text: string) {
  try {
    await navigator.clipboard.writeText(text);
    ElMessage.success($t('agentscope.integration.copied'));
  } catch {
    ElMessage.error('Copy failed');
  }
}

onMounted(load);
</script>

<template>
  <Page :title="$t('agentscope.publish.title')">
    <template #extra>
      <ElButton type="primary" @click="openPublish">
        {{ $t('agentscope.publish.publishAgent') }}
      </ElButton>
    </template>

    <ElCard shadow="never">
      <ElTable v-loading="loading" :data="apps.map((i) => i.app)" stripe>
        <ElTableColumn :label="$t('agentscope.common.name')" min-width="200">
          <template #default="{ row }">
            <div class="flex items-center gap-2">
              <IconifyIcon
                v-if="row.icon && row.icon.includes(':')"
                :icon="row.icon"
                class="text-xl"
              />
              <span v-else class="text-xl">{{ row.icon }}</span>
              <div>
                <div class="font-medium">{{ row.name }}</div>
                <div class="text-muted-foreground text-xs">
                  {{ agentName(row.agent_id) }}
                </div>
              </div>
            </div>
          </template>
        </ElTableColumn>
        <ElTableColumn :label="$t('agentscope.agent.defaultModel')" width="150">
          <template #default="{ row }">
            <ElTag size="small" type="info">
              {{ row.chat_model_name || '—' }}
            </ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn :label="$t('agentscope.publish.apiKeys')" width="90">
          <template #default="{ row }">
            {{ apps.find((i) => i.app.id === row.id)?.key_count ?? 0 }}
          </template>
        </ElTableColumn>
        <ElTableColumn :label="$t('agentscope.publish.status')" width="90">
          <template #default="{ row }">
            <ElSwitch :model-value="row.enabled" @change="toggleEnabled(row)" />
          </template>
        </ElTableColumn>
        <ElTableColumn :label="$t('agentscope.common.actions')" width="180">
          <template #default="{ row }">
            <ElButton link type="primary" @click="openDetail(row)">
              {{ $t('agentscope.publish.manage') }}
            </ElButton>
            <ElPopconfirm
              :title="$t('agentscope.common.deleteConfirm')"
              @confirm="removeApp(row)"
            >
              <template #reference>
                <ElButton link type="danger">
                  {{ $t('agentscope.publish.unpublish') }}
                </ElButton>
              </template>
            </ElPopconfirm>
          </template>
        </ElTableColumn>
        <template #empty>
          <ElEmpty :description="$t('agentscope.publish.empty')" />
        </template>
      </ElTable>
    </ElCard>

    <!-- Publish dialog -->
    <ElDialog
      v-model="dialog"
      :title="$t('agentscope.publish.publishAgent')"
      width="560px"
    >
      <ElForm label-position="top">
        <ElFormItem :label="$t('agentscope.schedule.agent')">
          <ElSelect v-model="form.agent_id" class="w-full">
            <ElOption
              v-for="a in agents"
              :key="a.id"
              :label="a.data?.name || a.id"
              :value="a.id"
            />
          </ElSelect>
        </ElFormItem>
        <div class="flex gap-3">
          <ElFormItem :label="$t('agentscope.publish.icon')" class="w-24">
            <ElInput v-model="form.icon" placeholder="lucide:bot" />
          </ElFormItem>
          <ElFormItem :label="$t('agentscope.publish.appName')" class="flex-1">
            <ElInput
              v-model="form.name"
              :placeholder="agentName(form.agent_id)"
            />
          </ElFormItem>
        </div>
        <ElFormItem :label="$t('agentscope.publish.openingStatement')">
          <ElInput v-model="form.opening_statement" :rows="2" type="textarea" />
        </ElFormItem>
        <ElFormItem :label="$t('agentscope.publish.suggestedQuestions')">
          <ElInput
            v-model="form.suggested_questions"
            :placeholder="$t('agentscope.publish.suggestedHint')"
            :rows="3"
            type="textarea"
          />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="dialog = false">
          {{ $t('agentscope.common.cancel') }}
        </ElButton>
        <ElButton :loading="saving" type="primary" @click="doPublish">
          {{ $t('agentscope.publish.publishAgent') }}
        </ElButton>
      </template>
    </ElDialog>

    <!-- Detail drawer -->
    <ElDrawer v-model="drawer" :title="current?.name" size="640px">
      <ElTabs v-if="current" v-model="activeTab">
        <!-- Overview -->
        <ElTabPane :label="$t('agentscope.publish.overview')" name="overview">
          <ElForm label-position="top">
            <div class="flex gap-3">
              <ElFormItem :label="$t('agentscope.publish.icon')" class="w-24">
                <ElInput v-model="current.icon" placeholder="lucide:bot" />
              </ElFormItem>
              <ElFormItem
                :label="$t('agentscope.publish.appName')"
                class="flex-1"
              >
                <ElInput v-model="current.name" />
              </ElFormItem>
            </div>
            <ElFormItem :label="$t('agentscope.publish.openingStatement')">
              <ElInput
                v-model="current.opening_statement"
                :rows="2"
                type="textarea"
              />
            </ElFormItem>
            <ElFormItem :label="$t('agentscope.agent.permissionMode')">
              <ElSelect v-model="current.permission_mode" class="w-full">
                <ElOption
                  v-for="pm in permissionModes"
                  :key="pm"
                  :label="$t(`agentscope.agent.permission.${pm}`)"
                  :value="pm"
                />
              </ElSelect>
            </ElFormItem>
            <ElButton type="primary" @click="saveOverview">
              {{ $t('agentscope.common.save') }}
            </ElButton>
          </ElForm>
        </ElTabPane>

        <!-- Web App -->
        <ElTabPane :label="$t('agentscope.publish.webApp')" name="webapp">
          <p class="text-muted-foreground mb-2 text-sm">
            {{ $t('agentscope.publish.webAppHint') }}
          </p>
          <div class="flex items-center gap-2">
            <ElInput :model-value="webAppUrl" readonly />
            <ElButton @click="copy(webAppUrl)">
              {{ $t('agentscope.integration.copy') }}
            </ElButton>
            <ElButton type="primary">
              <ElLink :href="webAppUrl" :underline="false" target="_blank">
                {{ $t('agentscope.publish.open') }}
              </ElLink>
            </ElButton>
          </div>
        </ElTabPane>

        <!-- API -->
        <ElTabPane :label="$t('agentscope.publish.api')" name="api">
          <p class="text-muted-foreground mb-1 text-sm">
            {{ $t('agentscope.publish.endpoint') }}
          </p>
          <div class="mb-4 flex items-center gap-2">
            <ElInput :model-value="apiEndpoint" readonly />
            <ElButton @click="copy(apiEndpoint)">
              {{ $t('agentscope.integration.copy') }}
            </ElButton>
          </div>

          <div class="mb-2 flex items-center justify-between">
            <span class="text-sm font-medium">
              {{ $t('agentscope.publish.apiKeys') }}
            </span>
            <div class="flex gap-2">
              <ElInput
                v-model="newKeyName"
                :placeholder="$t('agentscope.publish.keyName')"
                class="w-40"
                size="small"
              />
              <ElButton size="small" type="primary" @click="createKey">
                {{ $t('agentscope.publish.createKey') }}
              </ElButton>
            </div>
          </div>
          <ElTable :data="keys" size="small">
            <ElTableColumn :label="$t('agentscope.common.name')" prop="name" />
            <ElTableColumn label="Key" prop="key_prefix" width="160">
              <template #default="{ row }">
                <code>{{ row.key_prefix }}…</code>
              </template>
            </ElTableColumn>
            <ElTableColumn :label="$t('agentscope.publish.status')" width="90">
              <template #default="{ row }">
                <ElTag :type="row.revoked ? 'danger' : 'success'" size="small">
                  {{
                    row.revoked
                      ? $t('agentscope.publish.revoked')
                      : $t('agentscope.publish.active')
                  }}
                </ElTag>
              </template>
            </ElTableColumn>
            <ElTableColumn :label="$t('agentscope.common.actions')" width="80">
              <template #default="{ row }">
                <ElButton
                  v-if="!row.revoked"
                  link
                  type="danger"
                  @click="revoke(row)"
                >
                  {{ $t('agentscope.publish.revoke') }}
                </ElButton>
              </template>
            </ElTableColumn>
          </ElTable>

          <p class="mb-1 mt-4 text-sm font-medium">cURL</p>
          <div class="flex justify-end">
            <ElButton link type="primary" @click="copy(curlSnippet)">
              {{ $t('agentscope.integration.copy') }}
            </ElButton>
          </div>
          <pre
            class="bg-accent overflow-auto rounded p-3 text-xs leading-relaxed"
            v-text="curlSnippet"
          ></pre>
        </ElTabPane>

        <!-- Embed -->
        <ElTabPane :label="$t('agentscope.publish.embed')" name="embed">
          <p class="mb-1 text-sm font-medium">
            {{ $t('agentscope.publish.iframe') }}
          </p>
          <div class="flex justify-end">
            <ElButton link type="primary" @click="copy(iframeSnippet)">
              {{ $t('agentscope.integration.copy') }}
            </ElButton>
          </div>
          <pre
            class="bg-accent overflow-auto rounded p-3 text-xs leading-relaxed"
            v-text="iframeSnippet"
          ></pre>

          <p class="mb-1 mt-4 text-sm font-medium">
            {{ $t('agentscope.publish.bubble') }}
          </p>
          <div class="flex justify-end">
            <ElButton link type="primary" @click="copy(bubbleSnippet)">
              {{ $t('agentscope.integration.copy') }}
            </ElButton>
          </div>
          <pre
            class="bg-accent overflow-auto rounded p-3 text-xs leading-relaxed"
            v-text="bubbleSnippet"
          ></pre>
        </ElTabPane>
      </ElTabs>
    </ElDrawer>
  </Page>
</template>
