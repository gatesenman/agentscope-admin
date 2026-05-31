<script lang="ts" setup>
import type {
  AgentRecord,
  CredentialRecord,
  ModelCard,
} from '#/api/agentscope';
import type { KnowledgeBaseListItem } from '#/api/agentscope/knowledge';
import type { Workflow, WorkflowRunEvent } from '#/api/agentscope/workflow';

import { computed, markRaw, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { Background } from '@vue-flow/background';
import { Controls } from '@vue-flow/controls';
import { useVueFlow, VueFlow } from '@vue-flow/core';
import {
  ElButton,
  ElCard,
  ElDrawer,
  ElEmpty,
  ElForm,
  ElFormItem,
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
  credentialApi,
  knowledgeApi,
  modelApi,
  workflowApi,
} from '#/api/agentscope';
import { $t } from '#/locales';

import FlowNode from './FlowNode.vue';

import '@vue-flow/core/dist/style.css';
import '@vue-flow/core/dist/theme-default.css';
import '@vue-flow/controls/dist/style.css';

const route = useRoute();
const router = useRouter();
const workflowId = route.params.id as string;

const {
  addEdges,
  addNodes,
  findNode,
  onConnect,
  onNodeClick,
  removeNodes,
  toObject,
} = useVueFlow();

const PALETTE = [
  { type: 'llm', label: 'LLM', icon: '🤖' },
  { type: 'agent', label: '智能体', icon: '🧠' },
  { type: 'knowledge', label: '知识检索', icon: '📚' },
  { type: 'condition', label: '条件分支', icon: '🔀' },
  { type: 'template', label: '模板', icon: '📝' },
  { type: 'answer', label: '回复', icon: '💬' },
];

const nodeTypes: any = {
  start: markRaw(FlowNode),
  llm: markRaw(FlowNode),
  agent: markRaw(FlowNode),
  knowledge: markRaw(FlowNode),
  condition: markRaw(FlowNode),
  template: markRaw(FlowNode),
  answer: markRaw(FlowNode),
  end: markRaw(FlowNode),
};

const loaded = ref(false);
const saving = ref(false);
const wf = ref<null | Workflow>(null);
const initialNodes = ref<any[]>([]);
const initialEdges = ref<any[]>([]);

// Reference data for node config selects.
const agents = ref<AgentRecord[]>([]);
const credentials = ref<CredentialRecord[]>([]);
const models = ref<ModelCard[]>([]);
const kbs = ref<KnowledgeBaseListItem[]>([]);

const selectedId = ref<string>('');
const selectedNode = computed(() =>
  selectedId.value ? findNode(selectedId.value) : undefined,
);

const operators = [
  'contains',
  'not_contains',
  'equals',
  'not_equals',
  'empty',
  'not_empty',
  'gt',
  'lt',
  'gte',
  'lte',
];

function defaultData(type: string): Record<string, any> {
  switch (type) {
    case 'agent': {
      return { title: '智能体', agent_id: '', prompt: '{{start.query}}' };
    }
    case 'answer': {
      return { title: '回复', answer: '' };
    }
    case 'condition': {
      return {
        title: '条件分支',
        variable: '{{start.query}}',
        operator: 'contains',
        value: '',
      };
    }
    case 'knowledge': {
      return {
        title: '知识检索',
        kb_id: '',
        query: '{{start.query}}',
        top_k: 4,
      };
    }
    case 'llm': {
      return {
        title: 'LLM',
        system_prompt: '',
        prompt: '{{start.query}}',
        type: '',
        credential_id: '',
        model: '',
        parameters: {},
      };
    }
    case 'template': {
      return { title: '模板', template: '' };
    }
    default: {
      return { title: type };
    }
  }
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
    // manual entry still allowed
  }
}

function onLlmCredentialChange(node: any, id: string) {
  node.data.type = credentialType(id);
  node.data.model = '';
  void loadModels(id);
}

async function load() {
  const [w, ag, cr, kb] = await Promise.all([
    workflowApi.getWorkflow(workflowId),
    agentApi.listAgents(),
    credentialApi.listCredentials(),
    knowledgeApi.listKnowledgeBases(),
  ]);
  wf.value = w;
  agents.value = ag.agents ?? [];
  credentials.value = cr.credentials ?? [];
  kbs.value = kb.items ?? [];
  initialNodes.value = (w.graph.nodes ?? []).map((n, i) => ({
    id: n.id,
    type: n.type,
    position: n.position ?? { x: 120 + i * 220, y: 120 },
    data: { ...n.data },
  }));
  initialEdges.value = (w.graph.edges ?? []).map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    sourceHandle: e.sourceHandle ?? undefined,
    label: e.sourceHandle ?? undefined,
    animated: true,
  }));
  loaded.value = true;
}

onConnect((params) => {
  addEdges([
    {
      id: `e-${crypto.randomUUID().slice(0, 8)}`,
      source: params.source,
      target: params.target,
      sourceHandle: params.sourceHandle ?? undefined,
      label: params.sourceHandle ?? undefined,
      animated: true,
    },
  ]);
});

onNodeClick(({ node }) => {
  selectedId.value = node.id;
  const cid = node.data?.credential_id;
  if (node.type === 'llm' && cid) void loadModels(cid);
});

function addNode(type: string) {
  const id = `${type}-${crypto.randomUUID().slice(0, 8)}`;
  addNodes([
    {
      id,
      type,
      position: { x: 240 + Math.random() * 120, y: 200 + Math.random() * 120 },
      data: defaultData(type),
    },
  ]);
  selectedId.value = id;
}

function deleteSelected() {
  if (!selectedId.value || selectedId.value === 'start') return;
  removeNodes([selectedId.value]);
  selectedId.value = '';
}

async function save() {
  const obj = toObject();
  const graph = {
    nodes: obj.nodes.map((n: any) => ({
      id: n.id,
      type: n.type,
      position: n.position,
      data: n.data,
    })),
    edges: obj.edges.map((e: any) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      sourceHandle: e.sourceHandle ?? null,
    })),
  };
  saving.value = true;
  try {
    await workflowApi.updateWorkflow(workflowId, {
      name: wf.value?.name,
      graph,
    });
    ElMessage.success($t('agentscope.common.saveSuccess'));
  } finally {
    saving.value = false;
  }
}

// ---- Run panel ----
const runDrawer = ref(false);
const running = ref(false);
const runInputs = ref<Record<string, any>>({});
const runLog = ref<{ text: string; type: string }[]>([]);
const runAnswer = ref('');

const startVariables = computed<{ name: string; type: string }[]>(() => {
  const start = (toObject().nodes ?? []).find((n: any) => n.type === 'start');
  return start?.data?.variables ?? [{ name: 'query', type: 'string' }];
});

function openRun() {
  runInputs.value = {};
  for (const v of startVariables.value) runInputs.value[v.name] = '';
  runLog.value = [];
  runAnswer.value = '';
  runDrawer.value = true;
}

async function doRun() {
  await save();
  running.value = true;
  runLog.value = [];
  runAnswer.value = '';
  try {
    await workflowApi.runWorkflow({
      id: workflowId,
      inputs: { ...runInputs.value },
      onEvent: (ev: WorkflowRunEvent) => {
        switch (ev.type) {
          case 'error': {
            runLog.value.push({ type: 'error', text: `✗ ${ev.message}` });

            break;
          }
          case 'node_finished': {
            runLog.value.push({ type: 'done', text: `✓ ${ev.node_id}` });

            break;
          }
          case 'node_started': {
            runLog.value.push({ type: 'node', text: `▶ ${ev.title}` });

            break;
          }
          case 'text_delta': {
            runAnswer.value += ev.delta ?? '';

            break;
          }
          case 'workflow_finished': {
            if (ev.output) runAnswer.value = ev.output;
            runLog.value.push({ type: 'done', text: '✓ finished' });

            break;
          }
          // No default
        }
      },
    });
  } catch (error: any) {
    ElMessage.error(error?.message ?? 'run failed');
  } finally {
    running.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="wf-editor">
    <div class="wf-toolbar">
      <ElButton link @click="router.back()">
        ‹ {{ $t('agentscope.common.back') }}
      </ElButton>
      <ElInput v-if="wf" v-model="wf.name" size="small" style="width: 240px" />
      <div style="flex: 1"></div>
      <ElButton :loading="saving" @click="save">
        {{ $t('agentscope.common.save') }}
      </ElButton>
      <ElButton type="primary" @click="openRun">
        {{ $t('agentscope.workflow.run') }}
      </ElButton>
    </div>

    <div class="wf-main">
      <!-- Palette -->
      <div class="wf-palette">
        <div class="wf-palette__title">
          {{ $t('agentscope.workflow.addNode') }}
        </div>
        <ElButton
          v-for="p in PALETTE"
          :key="p.type"
          class="wf-palette__btn"
          @click="addNode(p.type)"
        >
          {{ p.icon }} {{ p.label }}
        </ElButton>
      </div>

      <!-- Canvas -->
      <div class="wf-canvas">
        <VueFlow
          v-if="loaded"
          :nodes="initialNodes"
          :edges="initialEdges"
          :node-types="nodeTypes"
          fit-view-on-init
        >
          <Background />
          <Controls />
        </VueFlow>
      </div>

      <!-- Config panel -->
      <div class="wf-config">
        <ElScrollbar>
          <div v-if="!selectedNode" class="wf-config__empty">
            <ElEmpty :description="$t('agentscope.workflow.selectNode')" />
          </div>
          <div v-else style="padding: 12px">
            <div class="wf-config__head">
              <ElTag>{{ selectedNode.type }}</ElTag>
              <ElButton
                v-if="selectedNode.type !== 'start'"
                link
                type="danger"
                @click="deleteSelected"
              >
                {{ $t('agentscope.common.delete') }}
              </ElButton>
            </div>
            <ElForm label-position="top">
              <ElFormItem :label="$t('agentscope.workflow.nodeTitle')">
                <ElInput v-model="selectedNode.data.title" />
              </ElFormItem>

              <!-- start -->
              <template v-if="selectedNode.type === 'start'">
                <p
                  style="font-size: 12px; color: var(--el-text-color-secondary)"
                >
                  {{ $t('agentscope.workflow.startHint') }}
                </p>
              </template>

              <!-- llm -->
              <template v-if="selectedNode.type === 'llm'">
                <ElFormItem :label="$t('agentscope.workflow.credential')">
                  <ElSelect
                    v-model="selectedNode.data.credential_id"
                    @change="(v) => onLlmCredentialChange(selectedNode, v)"
                  >
                    <ElOption
                      v-for="c in credentials"
                      :key="c.id"
                      :label="`${c.data?.name || c.id} (${c.data?.type})`"
                      :value="c.id"
                    />
                  </ElSelect>
                </ElFormItem>
                <ElFormItem :label="$t('agentscope.workflow.model')">
                  <ElSelect
                    v-model="selectedNode.data.model"
                    filterable
                    allow-create
                    default-first-option
                  >
                    <ElOption
                      v-for="m in models"
                      :key="m.model"
                      :label="m.model"
                      :value="m.model"
                    />
                  </ElSelect>
                </ElFormItem>
                <ElFormItem :label="$t('agentscope.workflow.systemPrompt')">
                  <ElInput
                    v-model="selectedNode.data.system_prompt"
                    type="textarea"
                    :rows="3"
                  />
                </ElFormItem>
                <ElFormItem :label="$t('agentscope.workflow.prompt')">
                  <ElInput
                    v-model="selectedNode.data.prompt"
                    type="textarea"
                    :rows="3"
                  />
                </ElFormItem>
              </template>

              <!-- agent -->
              <template v-if="selectedNode.type === 'agent'">
                <ElFormItem :label="$t('agentscope.workflow.agent')">
                  <ElSelect v-model="selectedNode.data.agent_id">
                    <ElOption
                      v-for="a in agents"
                      :key="a.id"
                      :label="a.data?.name || a.id"
                      :value="a.id"
                    />
                  </ElSelect>
                </ElFormItem>
                <ElFormItem :label="$t('agentscope.workflow.prompt')">
                  <ElInput
                    v-model="selectedNode.data.prompt"
                    type="textarea"
                    :rows="3"
                  />
                </ElFormItem>
              </template>

              <!-- knowledge -->
              <template v-if="selectedNode.type === 'knowledge'">
                <ElFormItem :label="$t('agentscope.menu.knowledge')">
                  <ElSelect v-model="selectedNode.data.kb_id">
                    <ElOption
                      v-for="k in kbs"
                      :key="k.kb.id"
                      :label="k.kb.name"
                      :value="k.kb.id"
                    />
                  </ElSelect>
                </ElFormItem>
                <ElFormItem :label="$t('agentscope.workflow.query')">
                  <ElInput v-model="selectedNode.data.query" />
                </ElFormItem>
                <ElFormItem label="Top-K">
                  <ElInputNumber
                    v-model="selectedNode.data.top_k"
                    :min="1"
                    :max="20"
                  />
                </ElFormItem>
              </template>

              <!-- condition -->
              <template v-if="selectedNode.type === 'condition'">
                <ElFormItem :label="$t('agentscope.workflow.variable')">
                  <ElInput v-model="selectedNode.data.variable" />
                </ElFormItem>
                <ElFormItem :label="$t('agentscope.workflow.operator')">
                  <ElSelect v-model="selectedNode.data.operator">
                    <ElOption
                      v-for="op in operators"
                      :key="op"
                      :label="op"
                      :value="op"
                    />
                  </ElSelect>
                </ElFormItem>
                <ElFormItem :label="$t('agentscope.workflow.value')">
                  <ElInput v-model="selectedNode.data.value" />
                </ElFormItem>
              </template>

              <!-- template -->
              <template v-if="selectedNode.type === 'template'">
                <ElFormItem :label="$t('agentscope.workflow.template')">
                  <ElInput
                    v-model="selectedNode.data.template"
                    type="textarea"
                    :rows="4"
                  />
                </ElFormItem>
              </template>

              <!-- answer -->
              <template v-if="selectedNode.type === 'answer'">
                <ElFormItem :label="$t('agentscope.workflow.answer')">
                  <ElInput
                    v-model="selectedNode.data.answer"
                    type="textarea"
                    :rows="4"
                  />
                </ElFormItem>
              </template>
            </ElForm>
          </div>
        </ElScrollbar>
      </div>
    </div>

    <!-- Run drawer -->
    <ElDrawer
      v-model="runDrawer"
      :title="$t('agentscope.workflow.run')"
      size="520px"
    >
      <ElForm label-position="top">
        <ElFormItem v-for="v in startVariables" :key="v.name" :label="v.name">
          <ElInput v-model="runInputs[v.name]" type="textarea" :rows="2" />
        </ElFormItem>
        <ElButton type="primary" :loading="running" @click="doRun">
          {{ $t('agentscope.workflow.run') }}
        </ElButton>
      </ElForm>

      <ElCard
        v-if="runLog.length > 0"
        shadow="never"
        style="margin-top: 16px"
        :header="$t('agentscope.workflow.executionLog')"
      >
        <div
          v-for="(l, i) in runLog"
          :key="i"
          :style="{ color: l.type === 'error' ? '#ef4444' : undefined }"
          style="font-family: monospace; font-size: 12px; line-height: 1.8"
        >
          {{ l.text }}
        </div>
      </ElCard>

      <ElCard
        v-if="runAnswer"
        shadow="never"
        style="margin-top: 16px"
        :header="$t('agentscope.workflow.answer')"
      >
        <div style="white-space: pre-wrap">{{ runAnswer }}</div>
      </ElCard>
    </ElDrawer>
  </div>
</template>

<style scoped>
.wf-editor {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 90px);
}

.wf-toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 8px 12px;
  background: var(--el-bg-color);
  border-bottom: 1px solid var(--el-border-color-light);
}

.wf-main {
  display: flex;
  flex: 1;
  min-height: 0;
}

.wf-palette {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 150px;
  padding: 12px;
  background: var(--el-bg-color);
  border-right: 1px solid var(--el-border-color-light);
}

.wf-palette__title {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.wf-palette__btn {
  justify-content: flex-start;
  margin-left: 0 !important;
}

.wf-canvas {
  flex: 1;
  min-width: 0;
  height: 100%;
}

.wf-config {
  width: 340px;
  background: var(--el-bg-color);
  border-left: 1px solid var(--el-border-color-light);
}

.wf-config__empty {
  padding-top: 60px;
}

.wf-config__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
</style>
