<script lang="ts" setup>
import type {
  AgentRecord,
  CredentialRecord,
  ModelCard,
} from '#/api/agentscope';

import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue';

import { Page } from '@vben/common-ui';

import {
  ElButton,
  ElCard,
  ElEmpty,
  ElInput,
  ElInputNumber,
  ElMessage,
  ElOption,
  ElScrollbar,
  ElSelect,
  ElTag,
} from 'element-plus';

import {
  agentApi,
  agentProfileApi,
  chatApi,
  credentialApi,
  mcpApi,
  modelApi,
  observabilityApi,
  sessionApi,
  workspaceApi,
} from '#/api/agentscope';
import { $t } from '#/locales';

interface ToolEntry {
  id: string;
  name: string;
  args: string;
  result: string;
}

interface PendingConfirm {
  replyId: string;
  toolCalls: { id: string; input: Record<string, any>; name: string }[];
}

interface ChatMessage {
  role: 'assistant' | 'user';
  text: string;
  thinking?: string;
  tools: ToolEntry[];
  pending?: boolean;
  // Set when the agent paused to request human approval of tool calls.
  confirm?: null | PendingConfirm;
}

const agents = ref<AgentRecord[]>([]);
const credentials = ref<CredentialRecord[]>([]);
const models = ref<ModelCard[]>([]);

const agentId = ref('');
const credentialId = ref('');
const modelName = ref('');
const sessionId = ref('');

const modelParams = reactive<{
  max_tokens?: number;
  temperature?: number;
  top_p?: number;
}>({});
const fallbackConfig = ref<null | {
  credential_id: string;
  model: string;
  type: string;
}>(null);
const permissionMode = ref('default');
const permissionModes = [
  'default',
  'accept_edits',
  'explore',
  'bypass',
  'dont_ask',
];

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

// When the selected agent changes, prefill model + parameters from its
// saved profile (the agent-level model defaults configured in the admin).
async function applyAgentProfile(id: string) {
  if (!id) return;
  const p = await agentProfileApi.getProfile(id);
  if (!p) return;
  if (p.default_credential_id) credentialId.value = p.default_credential_id;
  await loadModels();
  if (p.default_model) modelName.value = p.default_model;
  modelParams.temperature = p.parameters?.temperature;
  modelParams.top_p = p.parameters?.top_p;
  modelParams.max_tokens = p.parameters?.max_tokens;
  permissionMode.value = p.permission_mode ?? 'default';
  fallbackConfig.value =
    p.fallback_credential_id && p.fallback_model
      ? {
          type: p.fallback_provider ?? '',
          credential_id: p.fallback_credential_id,
          model: p.fallback_model,
        }
      : null;
}

watch(agentId, applyAgentProfile);

// Push every enabled MCP server from the registry into the freshly created
// session's workspace. Failures are surfaced as warnings but never block chat.
async function attachEnabledMcps(sid: string) {
  let payloads: Record<string, any>[];
  try {
    const res = await mcpApi.enabledMcpPayloads();
    payloads = res.items ?? [];
  } catch {
    return;
  }
  for (const payload of payloads) {
    try {
      await workspaceApi.addMcp(agentId.value, sid, payload);
    } catch {
      ElMessage.warning(
        $t('agentscope.session.mcpAttachFailed', { name: payload.name }),
      );
    }
  }
}

async function ensureSession() {
  if (sessionId.value) return sessionId.value;
  if (!agentId.value) {
    ElMessage.warning($t('agentscope.session.selectAgent'));
    return '';
  }
  const cred = selectedCredential.value;
  const parameters: Record<string, number> = {};
  if (modelParams.temperature !== undefined)
    parameters.temperature = modelParams.temperature;
  if (modelParams.top_p !== undefined) parameters.top_p = modelParams.top_p;
  if (modelParams.max_tokens !== undefined)
    parameters.max_tokens = modelParams.max_tokens;
  const res = await sessionApi.createSession({
    agent_id: agentId.value,
    name: `Playground ${new Date().toLocaleString()}`,
    chat_model_config:
      cred && modelName.value
        ? {
            type: cred.data.type,
            credential_id: cred.id,
            model: modelName.value,
            parameters,
          }
        : undefined,
    fallback_chat_model_config: fallbackConfig.value
      ? {
          type: fallbackConfig.value.type,
          credential_id: fallbackConfig.value.credential_id,
          model: fallbackConfig.value.model,
          parameters,
        }
      : undefined,
  });
  sessionId.value = res.session_id;
  // Apply the tool-execution permission mode (set via PATCH; not accepted
  // by the create endpoint).
  if (permissionMode.value && permissionMode.value !== 'default') {
    await sessionApi.updateSession(sessionId.value, agentId.value, {
      permission_mode: permissionMode.value,
    });
  }
  // Attach every enabled MCP server from the registry to this session so the
  // agent gains their tools. Best-effort: a single bad server must not block
  // the playground.
  await attachEnabledMcps(sessionId.value);
  return sessionId.value;
}

async function scrollToBottom() {
  await nextTick();
  const wrap = scrollRef.value?.wrapRef as HTMLElement | undefined;
  if (wrap) wrap.scrollTop = wrap.scrollHeight;
}

// Apply a single streamed AgentEvent to the live assistant message.
function applyEvent(live: ChatMessage, event: any) {
  switch (event.type) {
    case 'MODEL_CALL_END': {
      // Persist token usage for the observability dashboard (best-effort).
      void observabilityApi
        .recordUsage({
          agent_id: agentId.value,
          session_id: sessionId.value,
          source: 'playground',
          model_name: modelName.value,
          input_tokens: event.input_tokens ?? 0,
          output_tokens: event.output_tokens ?? 0,
        })
        .catch(() => {});
      break;
    }
    case 'REQUIRE_USER_CONFIRM': {
      // The agent paused: surface the pending tool calls for approval.
      live.confirm = {
        replyId: event.reply_id,
        toolCalls: (event.tool_calls ?? []).map((tc: any) => ({
          id: tc.id,
          name: tc.name,
          input: tc.input ?? {},
        })),
      };
      break;
    }
    case 'TEXT_BLOCK_DELTA': {
      live.text += event.delta ?? '';
      break;
    }
    case 'THINKING_BLOCK_DELTA': {
      live.thinking = (live.thinking ?? '') + (event.delta ?? '');
      break;
    }
    case 'TOOL_CALL_DELTA': {
      const t = live.tools.find((x) => x.id === event.tool_call_id);
      if (t) t.args += event.delta ?? '';
      break;
    }
    case 'TOOL_CALL_START': {
      live.tools.push({
        id: event.tool_call_id,
        name: event.tool_call_name,
        args: '',
        result: '',
      });
      break;
    }
    case 'TOOL_RESULT_TEXT_DELTA': {
      const t = live.tools.find((x) => x.id === event.tool_call_id);
      if (t) t.result += event.delta ?? '';
      break;
    }
  }
  void scrollToBottom();
}

// Run one streaming turn, applying events to `live`. Used for both the initial
// user message and the resume after a human-in-the-loop confirmation.
async function runTurn(sid: string, live: ChatMessage, inputPayload: any) {
  sending.value = true;
  live.pending = true;
  try {
    await chatApi.streamChat({
      agentId: agentId.value,
      sessionId: sid,
      input: inputPayload,
      onEvent: (event) => applyEvent(live, event),
    });
  } catch (error: any) {
    live.text += `\n[error] ${error?.message ?? error}`;
  } finally {
    live.pending = false;
    sending.value = false;
    await scrollToBottom();
  }
}

async function send() {
  const text = input.value.trim();
  if (!text || sending.value) return;
  const sid = await ensureSession();
  if (!sid) return;

  input.value = '';
  messages.value.push(
    { role: 'user', text, tools: [] },
    {
      role: 'assistant',
      text: '',
      thinking: '',
      tools: [],
      pending: true,
      confirm: null,
    },
  );
  // Mutate through the reactive array element (not the raw object) so that
  // streamed deltas trigger re-renders.
  const live = messages.value[messages.value.length - 1] as ChatMessage;
  await scrollToBottom();
  await runTurn(sid, live, {
    name: 'user',
    role: 'user',
    content: [{ type: 'text', text }],
  });
}

// Approve or reject all pending tool calls, then resume the same reply.
async function resolveConfirm(live: ChatMessage, approve: boolean) {
  if (!live.confirm || !sessionId.value) return;
  const { replyId, toolCalls } = live.confirm;
  live.confirm = null;
  await runTurn(sessionId.value, live, {
    type: 'USER_CONFIRM_RESULT',
    reply_id: replyId,
    confirm_results: toolCalls.map((tc) => ({
      confirmed: approve,
      tool_call: {
        type: 'tool_use',
        id: tc.id,
        name: tc.name,
        input: tc.input,
      },
      rules: null,
    })),
  });
}

function newSession() {
  sessionId.value = '';
  messages.value = [];
}

onMounted(async () => {
  await loadBase();
  await loadModels();
  await applyAgentProfile(agentId.value);
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
          <div>
            <div class="mb-1 text-sm font-medium">
              {{ $t('agentscope.agent.temperature') }}
            </div>
            <ElInputNumber
              v-model="modelParams.temperature"
              :max="2"
              :min="0"
              :step="0.1"
              class="w-full"
            />
          </div>
          <div>
            <div class="mb-1 text-sm font-medium">
              {{ $t('agentscope.agent.maxTokens') }}
            </div>
            <ElInputNumber
              v-model="modelParams.max_tokens"
              :min="1"
              :step="256"
              class="w-full"
            />
          </div>
          <div>
            <div class="mb-1 text-sm font-medium">
              {{ $t('agentscope.agent.permissionMode') }}
            </div>
            <ElSelect v-model="permissionMode" class="w-full">
              <ElOption
                v-for="pm in permissionModes"
                :key="pm"
                :label="$t(`agentscope.agent.permission.${pm}`)"
                :value="pm"
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
              <!-- Human-in-the-loop: agent paused for tool-call approval -->
              <div
                v-if="m.confirm"
                class="border-warning/40 bg-warning/5 mt-2 rounded border p-3 text-xs"
              >
                <div class="text-warning mb-2 font-medium">
                  {{ $t('agentscope.session.confirmTitle') }}
                </div>
                <div
                  v-for="tc in m.confirm.toolCalls"
                  :key="tc.id"
                  class="border-border bg-background/40 my-1 rounded border p-2"
                >
                  <div class="font-medium">
                    <ElTag size="small" type="warning">tool</ElTag>
                    {{ tc.name }}
                  </div>
                  <pre
                    class="whitespace-pre-wrap"
                    v-text="JSON.stringify(tc.input, null, 2)"
                  ></pre>
                </div>
                <div class="mt-2 flex gap-2">
                  <ElButton
                    :loading="sending"
                    size="small"
                    type="primary"
                    @click="resolveConfirm(m, true)"
                  >
                    {{ $t('agentscope.session.confirmApprove') }}
                  </ElButton>
                  <ElButton
                    :loading="sending"
                    size="small"
                    type="danger"
                    @click="resolveConfirm(m, false)"
                  >
                    {{ $t('agentscope.session.confirmReject') }}
                  </ElButton>
                </div>
              </div>
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
