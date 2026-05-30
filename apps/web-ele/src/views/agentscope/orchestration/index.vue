<script lang="ts" setup>
import type {
  AgentRecord,
  CredentialRecord,
  ModelCard,
} from '#/api/agentscope';

import { computed, onMounted, ref, watch } from 'vue';

import { Page } from '@vben/common-ui';

import {
  ElButton,
  ElCard,
  ElEmpty,
  ElInput,
  ElMessage,
  ElOption,
  ElSelect,
  ElStep,
  ElSteps,
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

interface PipelineStep {
  agentId: string;
  output: string;
  running: boolean;
  done: boolean;
}

const agents = ref<AgentRecord[]>([]);
const credentials = ref<CredentialRecord[]>([]);
const models = ref<ModelCard[]>([]);

const credentialId = ref('');
const modelName = ref('');
const initialInput = ref('');
const steps = ref<PipelineStep[]>([]);
const running = ref(false);

const selectedCredential = computed(() =>
  credentials.value.find((c) => c.id === credentialId.value),
);

function agentName(id: string) {
  return agents.value.find((a) => a.id === id)?.data.name ?? id;
}

async function loadBase() {
  const [a, c] = await Promise.all([
    agentApi.listAgents(),
    credentialApi.listCredentials(),
  ]);
  agents.value = a.agents ?? [];
  credentials.value = c.credentials ?? [];
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
    // ignore
  }
}

watch(credentialId, loadModels);

function addStep() {
  if (agents.value.length === 0) return;
  steps.value.push({
    agentId: agents.value[0]?.id ?? '',
    output: '',
    running: false,
    done: false,
  });
}

function removeStep(index: number) {
  steps.value.splice(index, 1);
}

async function runOne(step: PipelineStep, text: string): Promise<string> {
  const cred = selectedCredential.value;
  const session = await sessionApi.createSession({
    agent_id: step.agentId,
    name: `Orchestration ${Date.now()}`,
    chat_model_config:
      cred && modelName.value
        ? {
            type: cred.data.type,
            credential_id: cred.id,
            model: modelName.value,
          }
        : undefined,
  });
  let out = '';
  await chatApi.streamChat({
    agentId: step.agentId,
    sessionId: session.session_id,
    input: { name: 'user', role: 'user', content: [{ type: 'text', text }] },
    onEvent: (event) => {
      if (event.type === 'TEXT_BLOCK_DELTA') {
        out += event.delta ?? '';
        step.output = out;
      }
    },
  });
  return out;
}

async function run() {
  if (steps.value.length === 0 || !initialInput.value.trim()) {
    ElMessage.warning($t('agentscope.session.inputPlaceholder'));
    return;
  }
  running.value = true;
  let carry = initialInput.value.trim();
  try {
    for (const step of steps.value) {
      step.running = true;
      step.done = false;
      step.output = '';

      carry = await runOne(step, carry);
      step.running = false;
      step.done = true;
    }
    ElMessage.success('Pipeline finished');
  } catch (error: any) {
    ElMessage.error(error?.message ?? 'Pipeline failed');
  } finally {
    running.value = false;
  }
}

onMounted(async () => {
  await loadBase();
  await loadModels();
});
</script>

<template>
  <Page :title="$t('agentscope.orchestration.title')">
    <div class="flex gap-4">
      <ElCard class="w-80 shrink-0" shadow="never">
        <div class="space-y-4">
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
            <div class="mb-1 text-sm font-medium">Input</div>
            <ElInput
              v-model="initialInput"
              :autosize="{ minRows: 3, maxRows: 6 }"
              type="textarea"
            />
          </div>
          <div class="flex gap-2">
            <ElButton class="flex-1" @click="addStep">
              {{ $t('agentscope.orchestration.addNode') }}
            </ElButton>
            <ElButton
              :loading="running"
              class="flex-1"
              type="primary"
              @click="run"
            >
              {{ $t('agentscope.orchestration.run') }}
            </ElButton>
          </div>
        </div>
      </ElCard>

      <ElCard class="min-w-0 flex-1" shadow="never">
        <ElEmpty
          v-if="steps.length === 0"
          :description="$t('agentscope.orchestration.pipeline')"
        />
        <ElSteps v-else direction="vertical" :active="steps.length">
          <ElStep
            v-for="(step, i) in steps"
            :key="i"
            :status="step.done ? 'success' : step.running ? 'process' : 'wait'"
          >
            <template #title>
              <div class="flex items-center gap-2">
                <ElSelect v-model="step.agentId" class="w-48" size="small">
                  <ElOption
                    v-for="a in agents"
                    :key="a.id"
                    :label="a.data.name"
                    :value="a.id"
                  />
                </ElSelect>
                <ElTag v-if="step.running" size="small" type="warning">
                  running
                </ElTag>
                <ElButton link type="danger" @click="removeStep(i)">×</ElButton>
              </div>
            </template>
            <template #description>
              <div
                v-if="step.output"
                class="bg-accent mt-2 whitespace-pre-wrap rounded p-2 text-sm"
              >
                {{ step.output }}
              </div>
              <span v-else class="text-foreground/40 text-xs">
                {{ agentName(step.agentId) }}
              </span>
            </template>
          </ElStep>
        </ElSteps>
      </ElCard>
    </div>
  </Page>
</template>
