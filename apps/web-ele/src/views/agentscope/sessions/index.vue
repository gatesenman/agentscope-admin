<script lang="ts" setup>
import type {
  AgentRecord,
  CredentialRecord,
  ModelCard,
} from '#/api/agentscope';

import { computed, nextTick, onMounted, ref, watch } from 'vue';

import { Page } from '@vben/common-ui';

import {
  ElButton,
  ElCard,
  ElEmpty,
  ElInput,
  ElMessage,
  ElOption,
  ElScrollbar,
  ElSelect,
  ElTag,
} from 'element-plus';

import {
  agentApi,
  chatApi,
  credentialApi,
  modelApi,
  sessionApi,
} from '#/api/agentscope';
import { $t } from '#/locales';

interface ToolEntry {
  id: string;
  name: string;
  args: string;
  result: string;
}

interface ChatMessage {
  role: 'assistant' | 'user';
  text: string;
  thinking?: string;
  tools: ToolEntry[];
  pending?: boolean;
}

const agents = ref<AgentRecord[]>([]);
const credentials = ref<CredentialRecord[]>([]);
const models = ref<ModelCard[]>([]);

const agentId = ref('');
const credentialId = ref('');
const modelName = ref('');
const sessionId = ref('');

const input = ref('');
const sending = ref(false);
const messages = ref<ChatMessage[]>([]);
const scrollRef = ref<any>();

const selectedCredential = computed(() =>
  credentials.value.find((c) => c.id === credentialId.value),
);

async function loadBase() {
  const [a, c] = await Promise.all([
    agentApi.listAgents(),
    credentialApi.listCredentials(),
  ]);
  agents.value = a.agents ?? [];
  credentials.value = c.credentials ?? [];
  if (agents.value[0]) agentId.value = agents.value[0].id;
  if (credentials.value.length > 0)
    credentialId.value = credentials.value[0]?.id ?? '';
}

async function loadModels() {
  models.value = [];
  modelName.value = '';
  const cred = selectedCredential.value;
  if (!cred?.data?.type) return;
  try {
    const res = await modelApi.listModels(cred.data.type);
    models.value = res.models ?? [];
    if (models.value[0]) modelName.value = models.value[0].name;
  } catch {
    // provider may not support listing; allow manual entry
  }
}

watch(credentialId, loadModels);

async function ensureSession() {
  if (sessionId.value) return sessionId.value;
  if (!agentId.value) {
    ElMessage.warning($t('agentscope.session.selectAgent'));
    return '';
  }
  const cred = selectedCredential.value;
  const res = await sessionApi.createSession({
    agent_id: agentId.value,
    name: `Playground ${new Date().toLocaleString()}`,
    chat_model_config:
      cred && modelName.value
        ? {
            type: cred.data.type,
            credential_id: cred.id,
            model: modelName.value,
          }
        : undefined,
  });
  sessionId.value = res.session_id;
  return sessionId.value;
}

async function scrollToBottom() {
  await nextTick();
  const wrap = scrollRef.value?.wrapRef as HTMLElement | undefined;
  if (wrap) wrap.scrollTop = wrap.scrollHeight;
}

async function send() {
  const text = input.value.trim();
  if (!text || sending.value) return;
  const sid = await ensureSession();
  if (!sid) return;

  input.value = '';
  messages.value.push({ role: 'user', text, tools: [] });
  const assistant: ChatMessage = {
    role: 'assistant',
    text: '',
    thinking: '',
    tools: [],
    pending: true,
  };
  messages.value.push(assistant);
  sending.value = true;
  await scrollToBottom();

  try {
    await chatApi.streamChat({
      agentId: agentId.value,
      sessionId: sid,
      input: { name: 'user', role: 'user', content: [{ type: 'text', text }] },
      onEvent: (event) => {
        switch (event.type) {
          case 'TEXT_BLOCK_DELTA': {
            assistant.text += event.delta ?? '';
            break;
          }
          case 'THINKING_BLOCK_DELTA': {
            assistant.thinking =
              (assistant.thinking ?? '') + (event.delta ?? '');
            break;
          }
          case 'TOOL_CALL_DELTA': {
            const t = assistant.tools.find((x) => x.id === event.tool_call_id);
            if (t) t.args += event.delta ?? '';
            break;
          }
          case 'TOOL_CALL_START': {
            assistant.tools.push({
              id: event.tool_call_id,
              name: event.tool_call_name,
              args: '',
              result: '',
            });
            break;
          }
          case 'TOOL_RESULT_TEXT_DELTA': {
            const t = assistant.tools.find((x) => x.id === event.tool_call_id);
            if (t) t.result += event.delta ?? '';
            break;
          }
        }
        void scrollToBottom();
      },
    });
  } catch (error: any) {
    assistant.text += `\n[error] ${error?.message ?? error}`;
  } finally {
    assistant.pending = false;
    sending.value = false;
    await scrollToBottom();
  }
}

function newSession() {
  sessionId.value = '';
  messages.value = [];
}

onMounted(async () => {
  await loadBase();
  await loadModels();
});
</script>

<template>
  <Page :title="$t('agentscope.session.playground')">
    <div class="flex h-[calc(100vh-160px)] gap-4">
      <!-- Config panel -->
      <ElCard class="w-72 shrink-0" shadow="never">
        <div class="space-y-4">
          <div>
            <div class="mb-1 text-sm font-medium">
              {{ $t('agentscope.session.selectAgent') }}
            </div>
            <ElSelect v-model="agentId" class="w-full">
              <ElOption
                v-for="a in agents"
                :key="a.id"
                :label="a.data.name"
                :value="a.id"
              />
            </ElSelect>
          </div>
          <div>
            <div class="mb-1 text-sm font-medium">
              {{ $t('agentscope.menu.credentials') }}
            </div>
            <ElSelect v-model="credentialId" class="w-full">
              <ElOption
                v-for="c in credentials"
                :key="c.id"
                :label="c.data?.name || c.data?.type || c.id"
                :value="c.id"
              />
            </ElSelect>
          </div>
          <div>
            <div class="mb-1 text-sm font-medium">
              {{ $t('agentscope.session.selectModel') }}
            </div>
            <ElSelect
              v-model="modelName"
              allow-create
              class="w-full"
              filterable
            >
              <ElOption
                v-for="m in models"
                :key="m.name"
                :label="m.name"
                :value="m.name"
              />
            </ElSelect>
          </div>
          <ElButton class="w-full" @click="newSession">
            {{ $t('agentscope.session.newSession') }}
          </ElButton>
        </div>
      </ElCard>

      <!-- Chat panel -->
      <ElCard
        body-class="flex flex-col h-full"
        class="flex min-w-0 flex-1 flex-col"
        shadow="never"
      >
        <ElScrollbar ref="scrollRef" class="flex-1">
          <ElEmpty
            v-if="messages.length === 0"
            :description="$t('agentscope.session.inputPlaceholder')"
          />
          <div
            v-for="(m, i) in messages"
            :key="i"
            class="mb-4 flex"
            :class="[m.role === 'user' ? 'justify-end' : '']"
          >
            <div
              class="max-w-[80%] rounded-lg px-4 py-2"
              :class="[
                m.role === 'user'
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-accent',
              ]"
            >
              <div
                v-if="m.thinking"
                class="text-foreground/50 mb-2 text-xs italic"
              >
                {{ m.thinking }}
              </div>
              <div
                v-for="tool in m.tools"
                :key="tool.id"
                class="border-border my-2 rounded border bg-background/40 p-2 text-xs"
              >
                <div class="font-medium">
                  <ElTag size="small" type="warning">tool</ElTag>
                  {{ tool.name }}
                </div>
                <pre
                  v-if="tool.args"
                  class="whitespace-pre-wrap"
                  v-text="tool.args"
                ></pre>
                <pre
                  v-if="tool.result"
                  class="text-foreground/70 whitespace-pre-wrap"
                  v-text="tool.result"
                ></pre>
              </div>
              <div class="whitespace-pre-wrap">{{ m.text }}</div>
              <span v-if="m.pending" class="animate-pulse">▋</span>
            </div>
          </div>
        </ElScrollbar>

        <div class="mt-3 flex gap-2">
          <ElInput
            v-model="input"
            :autosize="{ minRows: 1, maxRows: 4 }"
            :placeholder="$t('agentscope.session.inputPlaceholder')"
            type="textarea"
            @keyup.enter.exact.prevent="send"
          />
          <ElButton :loading="sending" type="primary" @click="send">
            {{ $t('agentscope.session.send') }}
          </ElButton>
        </div>
      </ElCard>
    </div>
  </Page>
</template>
