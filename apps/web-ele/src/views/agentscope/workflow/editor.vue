<script lang="ts" setup>
import type {
  AgentRecord,
  CredentialRecord,
  ModelCard,
} from '#/api/agentscope';
import type { KnowledgeBaseListItem } from '#/api/agentscope/knowledge';
import type { Workflow, WorkflowRunEvent } from '#/api/agentscope/workflow';

import { computed, markRaw, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { IconifyIcon } from '@vben/icons';

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
  ontologyApi,
  workflowApi,
} from '#/api/agentscope';
import { $t } from '#/locales';

import CodeEditor from '../components/CodeEditor.vue';
import JsonEditor from '../components/JsonEditor.vue';
import PanelSection from '../components/PanelSection.vue';
import VarInput from '../components/VarInput.vue';
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

// Full Dify-aligned node catalogue, grouped by category. The `start` node is
// implicit and cannot be added from the palette.
const PALETTE_GROUPS = [
  {
    label: '输入 / 触发',
    items: [
      {
        type: 'trigger-webhook',
        label: 'Webhook 触发',
        icon: 'lucide:webhook',
      },
      {
        type: 'trigger-schedule',
        label: '定时触发',
        icon: 'lucide:alarm-clock',
      },
    ],
  },
  {
    label: 'AI',
    items: [
      { type: 'llm', label: 'LLM', icon: 'lucide:sparkles' },
      { type: 'agent', label: '智能体', icon: 'lucide:bot' },
      {
        type: 'question-classifier',
        label: '问题分类器',
        icon: 'lucide:list-tree',
      },
      { type: 'parameter-extractor', label: '参数提取', icon: 'lucide:braces' },
    ],
  },
  {
    label: '知识 / 数据',
    items: [
      { type: 'knowledge', label: '知识检索', icon: 'lucide:book-open' },
      { type: 'knowledge-index', label: '知识写入', icon: 'lucide:database' },
      { type: 'datasource', label: '数据源', icon: 'lucide:folder-input' },
      {
        type: 'document-extractor',
        label: '文档提取',
        icon: 'lucide:file-text',
      },
      { type: 'ontology', label: '本体操作', icon: 'lucide:share-2' },
    ],
  },
  {
    label: '逻辑',
    items: [
      { type: 'condition', label: '条件分支', icon: 'lucide:git-branch' },
      { type: 'code', label: '代码执行', icon: 'lucide:code' },
      { type: 'template', label: '模板转换', icon: 'lucide:file-code' },
      { type: 'http-request', label: 'HTTP 请求', icon: 'lucide:globe' },
      { type: 'tool', label: '工具', icon: 'lucide:wrench' },
      { type: 'list-operator', label: '列表操作', icon: 'lucide:list-filter' },
    ],
  },
  {
    label: '流程',
    items: [
      { type: 'iteration', label: '迭代', icon: 'lucide:repeat' },
      { type: 'loop', label: '循环', icon: 'lucide:rotate-cw' },
      { type: 'human-input', label: '人工输入', icon: 'lucide:user-check' },
    ],
  },
  {
    label: '变量',
    items: [
      {
        type: 'variable-aggregator',
        label: '变量聚合',
        icon: 'lucide:combine',
      },
      { type: 'assigner', label: '变量赋值', icon: 'lucide:variable' },
    ],
  },
  {
    label: '输出',
    items: [
      { type: 'answer', label: '回复', icon: 'lucide:message-square' },
      { type: 'end', label: '结束', icon: 'lucide:flag' },
    ],
  },
];

const ALL_NODE_TYPES = [
  'start',
  'trigger-webhook',
  'trigger-schedule',
  'llm',
  'agent',
  'question-classifier',
  'parameter-extractor',
  'knowledge',
  'knowledge-index',
  'datasource',
  'document-extractor',
  'ontology',
  'condition',
  'code',
  'template',
  'http-request',
  'tool',
  'list-operator',
  'iteration',
  'loop',
  'human-input',
  'variable-aggregator',
  'assigner',
  'answer',
  'end',
];

const nodeTypes: any = Object.fromEntries(
  ALL_NODE_TYPES.map((t) => [t, markRaw(FlowNode)]),
);

const toolOptions = [
  { value: 'current_time', label: '当前时间' },
  { value: 'calculator', label: '计算器' },
  { value: 'knowledge_search', label: '知识检索' },
  { value: 'http_get', label: 'HTTP GET' },
];

const ontologyOps = [
  { value: 'query', label: '语义查询对象' },
  { value: 'traverse', label: '遍历关系' },
  { value: 'execute_action', label: '执行动作' },
];

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
const ontologies = ref<any[]>([]);
const ontObjectTypes = ref<any[]>([]);
const ontLinkTypes = ref<any[]>([]);
const ontActionTypes = ref<any[]>([]);

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

// ---- Variable reference helpers (for VarInput autocomplete) ----
interface VarGroup {
  fields: string[];
  node: string;
}

// Output fields a node exposes for `{{node.field}}` references.
function nodeOutputFields(type: string, data?: any): string[] {
  switch (type) {
    case 'assigner': {
      const vs = (data?.assignments ?? [])
        .map((a: any) => a.variable)
        .filter(Boolean);
      return vs.length > 0 ? vs : ['text'];
    }
    case 'code': {
      return ['result', 'text'];
    }
    case 'http-request': {
      return ['status', 'body', 'text'];
    }
    case 'iteration': {
      return ['results', 'text'];
    }
    case 'knowledge': {
      return ['text', 'chunks'];
    }
    case 'list-operator': {
      return ['result', 'text'];
    }
    case 'ontology': {
      return ['text', 'objects'];
    }
    case 'parameter-extractor': {
      const fs = (data?.parameters_schema ?? [])
        .map((p: any) => p.name)
        .filter(Boolean);
      return ['text', ...fs];
    }
    case 'question-classifier': {
      return ['text', 'class_name'];
    }
    case 'start':
    case 'trigger-schedule':
    case 'trigger-webhook': {
      const vars = (data?.variables ?? [])
        .map((v: any) => v.name)
        .filter(Boolean);
      return vars.length > 0 ? vars : ['query'];
    }
    case 'tool': {
      return ['result', 'text'];
    }
    case 'variable-aggregator': {
      return ['output', 'text'];
    }
    default: {
      return ['text'];
    }
  }
}

function outputFieldHint(type: string): string {
  return nodeOutputFields(type)[0] ?? 'text';
}

// Human-readable "this node outputs" hint, e.g. "{{code-1.result}}".
const selectedOutputExpr = computed(() => {
  const node = selectedNode.value;
  if (!node) return '';
  return `{{${node.id}.${outputFieldHint(node.type)}}}`;
});

// Walk edges backwards to collect ancestor node ids of the selected node.
const upstreamVars = computed<VarGroup[]>(() => {
  if (!selectedId.value) return [];
  const obj = toObject();
  const nodes = obj.nodes ?? [];
  const edges = obj.edges ?? [];
  const incoming = new Map<string, string[]>();
  for (const e of edges) {
    const list = incoming.get(e.target) ?? [];
    list.push(e.source);
    incoming.set(e.target, list);
  }
  const seen = new Set<string>();
  const queue = [...(incoming.get(selectedId.value) ?? [])];
  while (queue.length > 0) {
    const id = queue.shift();
    if (!id || seen.has(id)) continue;
    seen.add(id);
    for (const p of incoming.get(id) ?? []) queue.push(p);
  }
  const byId = new Map(nodes.map((n: any) => [n.id, n]));
  // Fall back to all other nodes when the graph isn't wired up yet.
  const ids =
    seen.size > 0
      ? [...seen]
      : nodes
          .map((n: any) => n.id)
          .filter((id: string) => id !== selectedId.value);
  const groups: VarGroup[] = [];
  for (const id of ids) {
    const n = byId.get(id);
    if (!n) continue;
    groups.push({ node: id, fields: nodeOutputFields(n.type, n.data) });
  }
  return groups;
});

// Iteration exposes per-item built-ins; loop exposes the round index.
const iterationVars = computed<VarGroup[]>(() => [
  { node: '', fields: ['item', 'index'] },
  ...upstreamVars.value,
]);
const loopVars = computed<VarGroup[]>(() => [
  { node: '', fields: ['loop_index'] },
  ...upstreamVars.value,
]);

function defaultData(type: string): Record<string, any> {
  switch (type) {
    case 'agent': {
      return { title: '智能体', agent_id: '', prompt: '{{start.query}}' };
    }
    case 'answer': {
      return { title: '回复', answer: '' };
    }
    // ---- Variables ----
    case 'assigner': {
      return {
        title: '变量赋值',
        assignments: [{ variable: 'my_var', value: '{{start.query}}' }],
      };
    }
    // ---- Logic ----
    case 'code': {
      return {
        title: '代码执行',
        language: 'python',
        variables: [{ name: 'arg1', value: '{{start.query}}' }],
        code: 'outputs = {"result": arg1}',
      };
    }
    case 'condition': {
      return {
        title: '条件分支',
        variable: '{{start.query}}',
        operator: 'contains',
        value: '',
      };
    }
    // ---- Data / Knowledge ----
    case 'datasource': {
      return { title: '数据源', source_type: 'text', value: '' };
    }
    case 'document-extractor': {
      return { title: '文档提取', input: '{{start.query}}' };
    }
    case 'end': {
      return { title: '结束', answer: '' };
    }

    case 'http-request': {
      return {
        title: 'HTTP 请求',
        method: 'GET',
        url: 'https://httpbin.org/get',
        headers: {},
        params: {},
        body: '',
        timeout: 30,
      };
    }
    // ---- Flow ----
    case 'human-input': {
      return { title: '人工输入', prompt: '请审核并补充', default: '' };
    }

    case 'iteration': {
      return {
        title: '迭代',
        input: '',
        item_template: '{{item}}',
        max_items: 50,
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

    case 'knowledge-index': {
      return { title: '知识写入', kb_id: '', input: '{{start.query}}' };
    }
    case 'list-operator': {
      return {
        title: '列表操作',
        variable: '',
        filter_field: '',
        filter_operator: 'eq',
        filter_value: '',
        order: '',
        order_field: '',
        limit: 0,
        extract_field: '',
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

    case 'loop': {
      return {
        title: '循环',
        template: 'round {{loop_index}}',
        max_loops: 3,
        break_when: { variable: '', operator: 'eq', value: '' },
      };
    }
    case 'ontology': {
      return {
        title: '本体操作',
        ontology_id: ontologies.value[0]?.id ?? '',
        operation: 'query',
        object_type: '',
        search: '{{start.query}}',
        filters: {},
        limit: 10,
        link_type: '',
        source_object_id: '',
        action: '',
        object_id: '',
        parameters: {},
      };
    }
    // ---- AI ----
    case 'parameter-extractor': {
      return {
        title: '参数提取',
        query: '{{start.query}}',
        type: '',
        credential_id: '',
        model: '',
        parameters_schema: [
          { name: 'name', type: 'string', description: '', required: false },
        ],
      };
    }
    case 'question-classifier': {
      return {
        title: '问题分类器',
        query: '{{start.query}}',
        type: '',
        credential_id: '',
        model: '',
        classes: [
          { id: `c-${crypto.randomUUID().slice(0, 6)}`, name: '类别 1' },
          { id: `c-${crypto.randomUUID().slice(0, 6)}`, name: '类别 2' },
        ],
      };
    }

    case 'template': {
      return { title: '模板转换', template: '' };
    }
    case 'tool': {
      return { title: '工具', tool: 'current_time', parameters: {} };
    }
    // ---- Entry triggers ----
    case 'trigger-schedule': {
      return { title: '定时触发', cron: '0 9 * * *', timezone: 'UTC' };
    }

    case 'trigger-webhook': {
      return { title: 'Webhook 触发', path: '/hooks/my-hook', method: 'POST' };
    }
    case 'variable-aggregator': {
      return { title: '变量聚合', mode: 'first', variables: [''] };
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

// ---- Ontology node helpers ----
async function loadOntologyMeta(ontologyId: string) {
  ontObjectTypes.value = [];
  ontLinkTypes.value = [];
  ontActionTypes.value = [];
  if (!ontologyId) return;
  try {
    const [ot, lt, at] = await Promise.all([
      ontologyApi.listObjectTypes(ontologyId),
      ontologyApi.listLinkTypes(ontologyId),
      ontologyApi.listActionTypes(ontologyId),
    ]);
    ontObjectTypes.value = ot.items ?? [];
    ontLinkTypes.value = lt.items ?? [];
    ontActionTypes.value = at.items ?? [];
  } catch {
    // manual entry still allowed
  }
}

function onOntologyChange(node: any, id: string) {
  node.data.ontology_id = id;
  void loadOntologyMeta(id);
}

// JSON proxies for the filters / parameters maps. Parsed on blur so partial
// edits don't blow up; invalid JSON is simply ignored until valid.
const filtersText = ref('{}');
const paramsText = ref('{}');

function syncOntologyText() {
  const d = selectedNode.value?.data;
  filtersText.value = JSON.stringify(d?.filters ?? {}, null, 2);
  paramsText.value = JSON.stringify(d?.parameters ?? {}, null, 2);
}

function commitFilters() {
  try {
    if (selectedNode.value) {
      selectedNode.value.data.filters = JSON.parse(filtersText.value || '{}');
    }
  } catch {
    // Invalid JSON while typing; JsonEditor shows the validity indicator.
  }
}

function commitParams() {
  try {
    if (selectedNode.value) {
      selectedNode.value.data.parameters = JSON.parse(paramsText.value || '{}');
    }
  } catch {
    // Invalid JSON while typing; JsonEditor shows the validity indicator.
  }
}

// ---- Generic JSON map editors (http headers/params, tool parameters) ----
const httpHeadersText = ref('{}');
const httpParamsText = ref('{}');
const toolParamsText = ref('{}');

function commitJson(text: string, field: string) {
  try {
    if (selectedNode.value) {
      selectedNode.value.data[field] = JSON.parse(text || '{}');
    }
  } catch {
    // Invalid JSON while typing; JsonEditor shows the validity indicator.
  }
}

function onFiltersInput(v: string) {
  filtersText.value = v;
  commitFilters();
}
function onParamsInput(v: string) {
  paramsText.value = v;
  commitParams();
}
function onHttpHeadersInput(v: string) {
  httpHeadersText.value = v;
  commitJson(v, 'headers');
}
function onHttpParamsInput(v: string) {
  httpParamsText.value = v;
  commitJson(v, 'params');
}
function onToolParamsInput(v: string) {
  toolParamsText.value = v;
  commitJson(v, 'parameters');
}

// ---- Row editors for structured array configs ----
function pushRow(field: string, row: any) {
  const arr = selectedNode.value?.data?.[field];
  if (Array.isArray(arr)) arr.push(row);
}
function removeRow(field: string, index: number | string) {
  const arr = selectedNode.value?.data?.[field];
  if (Array.isArray(arr)) arr.splice(Number(index), 1);
}
function addClass() {
  const n = (selectedNode.value?.data?.classes?.length ?? 0) + 1;
  pushRow('classes', {
    id: `c-${crypto.randomUUID().slice(0, 6)}`,
    name: `类别 ${n}`,
  });
}

watch(selectedId, () => {
  const node = selectedNode.value;
  if (!node) return;
  if (node.type === 'ontology') {
    syncOntologyText();
    if (node.data?.ontology_id) void loadOntologyMeta(node.data.ontology_id);
  }
  if (node.type === 'http-request') {
    httpHeadersText.value = JSON.stringify(node.data?.headers ?? {}, null, 2);
    httpParamsText.value = JSON.stringify(node.data?.params ?? {}, null, 2);
  }
  if (node.type === 'tool') {
    toolParamsText.value = JSON.stringify(node.data?.parameters ?? {}, null, 2);
  }
  // AI nodes share credential/model fields with the LLM node.
  if (
    (node.type === 'question-classifier' ||
      node.type === 'parameter-extractor') &&
    node.data?.credential_id
  ) {
    void loadModels(node.data.credential_id);
  }
});

async function load() {
  const [w, ag, cr, kb, ont] = await Promise.all([
    workflowApi.getWorkflow(workflowId),
    agentApi.listAgents(),
    credentialApi.listCredentials(),
    knowledgeApi.listKnowledgeBases(),
    ontologyApi.listOntologies(),
  ]);
  wf.value = w;
  agents.value = ag.agents ?? [];
  credentials.value = cr.credentials ?? [];
  kbs.value = kb.items ?? [];
  ontologies.value = ont.items ?? [];
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
const runLog = ref<{ detail?: string; text: string; type: string }[]>([]);
const runAnswer = ref('');
const nodeTitles = ref<Record<string, string>>({});

function previewOutput(output: any): string {
  if (output === null || output === undefined) return '';
  if (typeof output === 'string') return output.slice(0, 600);
  if (typeof output === 'object') {
    const text = (output as Record<string, any>).text;
    const body =
      typeof text === 'string' && text.length > 0
        ? text
        : JSON.stringify(output, null, 2);
    return body.length > 600 ? `${body.slice(0, 600)}…` : body;
  }
  return String(output);
}

const startVariables = computed<{ name: string; type: string }[]>(() => {
  const start = (toObject().nodes ?? []).find((n: any) => n.type === 'start');
  return start?.data?.variables ?? [{ name: 'query', type: 'string' }];
});

function openRun() {
  runInputs.value = {};
  for (const v of startVariables.value) runInputs.value[v.name] = '';
  runLog.value = [];
  runAnswer.value = '';
  nodeTitles.value = {};
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
            runLog.value.push({ type: 'error', text: ev.message ?? 'error' });

            break;
          }
          case 'node_finished': {
            const nid = ev.node_id ?? '';
            const label = nodeTitles.value[nid] ?? nid;
            runLog.value.push({
              type: 'done',
              text: label,
              detail: previewOutput(ev.output),
            });

            break;
          }
          case 'node_started': {
            if (ev.node_id)
              nodeTitles.value[ev.node_id] = ev.title ?? ev.node_id;
            runLog.value.push({ type: 'node', text: ev.title ?? '' });

            break;
          }
          case 'text_delta': {
            runAnswer.value += ev.delta ?? '';

            break;
          }
          case 'workflow_finished': {
            if (ev.output) runAnswer.value = ev.output;
            runLog.value.push({ type: 'done', text: 'finished' });

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
        <IconifyIcon icon="lucide:chevron-left" />
        {{ $t('agentscope.common.back') }}
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
        <ElScrollbar>
          <div class="wf-palette__title">
            {{ $t('agentscope.workflow.addNode') }}
          </div>
          <div
            v-for="g in PALETTE_GROUPS"
            :key="g.label"
            class="wf-palette__group"
          >
            <div class="wf-palette__group-label">{{ g.label }}</div>
            <ElButton
              v-for="p in g.items"
              :key="p.type"
              class="wf-palette__btn"
              @click="addNode(p.type)"
            >
              <IconifyIcon :icon="p.icon" style="margin-right: 4px" />
              {{ p.label }}
            </ElButton>
          </div>
        </ElScrollbar>
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
              <PanelSection title="基本" icon="lucide:tag">
                <ElFormItem :label="$t('agentscope.workflow.nodeTitle')">
                  <ElInput v-model="selectedNode.data.title" />
                </ElFormItem>
                <p class="wf-varhint">
                  本节点输出变量：<code>{{ selectedOutputExpr }}</code>
                </p>
              </PanelSection>

              <!-- start -->
              <template v-if="selectedNode.type === 'start'">
                <PanelSection title="说明" icon="lucide:info">
                  <p class="wf-hint">
                    {{ $t('agentscope.workflow.startHint') }}
                  </p>
                </PanelSection>
              </template>

              <!-- llm -->
              <template v-if="selectedNode.type === 'llm'">
                <PanelSection title="模型" icon="lucide:sparkles">
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
                </PanelSection>
                <PanelSection title="提示词" icon="lucide:message-square-text">
                  <ElFormItem :label="$t('agentscope.workflow.systemPrompt')">
                    <VarInput
                      v-model="selectedNode.data.system_prompt"
                      type="textarea"
                      :rows="3"
                      :variables="upstreamVars"
                    />
                  </ElFormItem>
                  <ElFormItem :label="$t('agentscope.workflow.prompt')">
                    <VarInput
                      v-model="selectedNode.data.prompt"
                      type="textarea"
                      :rows="3"
                      :variables="upstreamVars"
                    />
                  </ElFormItem>
                </PanelSection>
              </template>

              <!-- agent -->
              <template v-if="selectedNode.type === 'agent'">
                <PanelSection title="配置" icon="lucide:bot">
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
                    <VarInput
                      v-model="selectedNode.data.prompt"
                      type="textarea"
                      :rows="3"
                      :variables="upstreamVars"
                    />
                  </ElFormItem>
                </PanelSection>
              </template>

              <!-- knowledge -->
              <template v-if="selectedNode.type === 'knowledge'">
                <PanelSection title="检索配置" icon="lucide:book-open">
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
                    <VarInput
                      v-model="selectedNode.data.query"
                      :variables="upstreamVars"
                    />
                  </ElFormItem>
                  <ElFormItem label="Top-K">
                    <ElInputNumber
                      v-model="selectedNode.data.top_k"
                      :min="1"
                      :max="20"
                    />
                  </ElFormItem>
                </PanelSection>
              </template>

              <!-- condition -->
              <template v-if="selectedNode.type === 'condition'">
                <PanelSection title="条件" icon="lucide:git-branch">
                  <ElFormItem :label="$t('agentscope.workflow.variable')">
                    <VarInput
                      v-model="selectedNode.data.variable"
                      :variables="upstreamVars"
                    />
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
                    <VarInput
                      v-model="selectedNode.data.value"
                      :variables="upstreamVars"
                    />
                  </ElFormItem>
                </PanelSection>
              </template>

              <!-- ontology -->
              <template v-if="selectedNode.type === 'ontology'">
                <PanelSection title="本体操作" icon="lucide:share-2">
                  <ElFormItem label="本体">
                    <ElSelect
                      v-model="selectedNode.data.ontology_id"
                      @change="
                        (v: string) => onOntologyChange(selectedNode!, v)
                      "
                    >
                      <ElOption
                        v-for="o in ontologies"
                        :key="o.id"
                        :label="o.display_name || o.api_name"
                        :value="o.id"
                      />
                    </ElSelect>
                  </ElFormItem>
                  <ElFormItem label="操作">
                    <ElSelect v-model="selectedNode.data.operation">
                      <ElOption
                        v-for="op in ontologyOps"
                        :key="op.value"
                        :label="op.label"
                        :value="op.value"
                      />
                    </ElSelect>
                  </ElFormItem>

                  <!-- query fields -->
                  <template v-if="selectedNode.data.operation === 'query'">
                    <ElFormItem label="对象类型">
                      <ElSelect
                        v-model="selectedNode.data.object_type"
                        filterable
                        allow-create
                      >
                        <ElOption
                          v-for="ot in ontObjectTypes"
                          :key="ot.id"
                          :label="ot.display_name || ot.api_name"
                          :value="ot.api_name"
                        />
                      </ElSelect>
                    </ElFormItem>
                    <ElFormItem label="搜索表达式">
                      <VarInput
                        v-model="selectedNode.data.search"
                        :variables="upstreamVars"
                      />
                    </ElFormItem>
                    <ElFormItem label="过滤条件 (JSON)">
                      <JsonEditor
                        :model-value="filtersText"
                        :min-height="100"
                        @update:model-value="onFiltersInput"
                      />
                    </ElFormItem>
                    <ElFormItem label="返回数量">
                      <ElInputNumber
                        v-model="selectedNode.data.limit"
                        :min="1"
                        :max="100"
                      />
                    </ElFormItem>
                  </template>

                  <!-- traverse fields -->
                  <template v-if="selectedNode.data.operation === 'traverse'">
                    <ElFormItem label="关系类型">
                      <ElSelect
                        v-model="selectedNode.data.link_type"
                        filterable
                        allow-create
                      >
                        <ElOption
                          v-for="lt in ontLinkTypes"
                          :key="lt.id"
                          :label="lt.display_name || lt.api_name"
                          :value="lt.api_name"
                        />
                      </ElSelect>
                    </ElFormItem>
                    <ElFormItem label="源对象 ID">
                      <VarInput
                        v-model="selectedNode.data.source_object_id"
                        :variables="upstreamVars"
                      />
                    </ElFormItem>
                  </template>

                  <!-- execute_action fields -->
                  <template
                    v-if="selectedNode.data.operation === 'execute_action'"
                  >
                    <ElFormItem label="动作">
                      <ElSelect
                        v-model="selectedNode.data.action"
                        filterable
                        allow-create
                      >
                        <ElOption
                          v-for="at in ontActionTypes"
                          :key="at.id"
                          :label="at.display_name || at.api_name"
                          :value="at.api_name"
                        />
                      </ElSelect>
                    </ElFormItem>
                    <ElFormItem label="对象 ID">
                      <VarInput
                        v-model="selectedNode.data.object_id"
                        :variables="upstreamVars"
                      />
                    </ElFormItem>
                    <ElFormItem label="参数 (JSON)">
                      <JsonEditor
                        :model-value="paramsText"
                        :min-height="100"
                        @update:model-value="onParamsInput"
                      />
                    </ElFormItem>
                  </template>
                </PanelSection>
              </template>

              <!-- template -->
              <template v-if="selectedNode.type === 'template'">
                <PanelSection title="模板" icon="lucide:file-code">
                  <ElFormItem :label="$t('agentscope.workflow.template')">
                    <VarInput
                      v-model="selectedNode.data.template"
                      type="textarea"
                      :rows="5"
                      :variables="upstreamVars"
                    />
                  </ElFormItem>
                </PanelSection>
              </template>

              <!-- answer / end -->
              <template
                v-if="
                  selectedNode.type === 'answer' || selectedNode.type === 'end'
                "
              >
                <PanelSection title="输出" icon="lucide:message-square">
                  <ElFormItem :label="$t('agentscope.workflow.answer')">
                    <VarInput
                      v-model="selectedNode.data.answer"
                      type="textarea"
                      :rows="5"
                      :variables="upstreamVars"
                    />
                  </ElFormItem>
                </PanelSection>
              </template>

              <!-- trigger-schedule -->
              <template v-if="selectedNode.type === 'trigger-schedule'">
                <PanelSection title="触发" icon="lucide:alarm-clock">
                  <ElFormItem label="Cron 表达式">
                    <ElInput v-model="selectedNode.data.cron" />
                  </ElFormItem>
                  <ElFormItem label="时区">
                    <ElInput v-model="selectedNode.data.timezone" />
                  </ElFormItem>
                  <p class="wf-hint">
                    定时触发节点等价于开始节点，按 cron 周期运行工作流。
                  </p>
                </PanelSection>
              </template>

              <!-- trigger-webhook -->
              <template v-if="selectedNode.type === 'trigger-webhook'">
                <PanelSection title="触发" icon="lucide:webhook">
                  <ElFormItem label="路径">
                    <ElInput v-model="selectedNode.data.path" />
                  </ElFormItem>
                  <ElFormItem label="方法">
                    <ElSelect v-model="selectedNode.data.method">
                      <ElOption label="POST" value="POST" />
                      <ElOption label="GET" value="GET" />
                    </ElSelect>
                  </ElFormItem>
                  <p class="wf-hint">
                    Webhook 触发节点等价于开始节点，由外部请求携带变量触发。
                  </p>
                </PanelSection>
              </template>

              <!-- question-classifier -->
              <template v-if="selectedNode.type === 'question-classifier'">
                <PanelSection title="模型" icon="lucide:sparkles">
                  <ElFormItem :label="$t('agentscope.workflow.credential')">
                    <ElSelect
                      v-model="selectedNode.data.credential_id"
                      @change="
                        (v: string) => onLlmCredentialChange(selectedNode, v)
                      "
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
                </PanelSection>
                <PanelSection title="分类" icon="lucide:list-tree">
                  <ElFormItem :label="$t('agentscope.workflow.query')">
                    <VarInput
                      v-model="selectedNode.data.query"
                      :variables="upstreamVars"
                    />
                  </ElFormItem>
                  <ElFormItem label="分类类别（每个类别一个输出分支）">
                    <div class="wf-rows">
                      <div
                        v-for="(c, i) in selectedNode.data.classes"
                        :key="c.id"
                        class="wf-row"
                      >
                        <ElInput v-model="c.name" placeholder="类别名称" />
                        <ElButton
                          link
                          type="danger"
                          @click="removeRow('classes', i)"
                        >
                          <IconifyIcon icon="lucide:trash-2" />
                        </ElButton>
                      </div>
                      <ElButton size="small" @click="addClass">
                        <IconifyIcon icon="lucide:plus" />
                        添加类别
                      </ElButton>
                    </div>
                  </ElFormItem>
                </PanelSection>
              </template>

              <!-- parameter-extractor -->
              <template v-if="selectedNode.type === 'parameter-extractor'">
                <PanelSection title="模型" icon="lucide:sparkles">
                  <ElFormItem :label="$t('agentscope.workflow.credential')">
                    <ElSelect
                      v-model="selectedNode.data.credential_id"
                      @change="
                        (v: string) => onLlmCredentialChange(selectedNode, v)
                      "
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
                </PanelSection>
                <PanelSection title="提取参数" icon="lucide:braces">
                  <ElFormItem :label="$t('agentscope.workflow.query')">
                    <VarInput
                      v-model="selectedNode.data.query"
                      :variables="upstreamVars"
                    />
                  </ElFormItem>
                  <ElFormItem label="提取参数">
                    <div class="wf-rows">
                      <div
                        v-for="(p, i) in selectedNode.data.parameters_schema"
                        :key="i"
                        class="wf-row"
                      >
                        <ElInput v-model="p.name" placeholder="字段名" />
                        <ElSelect v-model="p.type" style="width: 110px">
                          <ElOption label="string" value="string" />
                          <ElOption label="number" value="number" />
                          <ElOption label="boolean" value="boolean" />
                          <ElOption label="array" value="array" />
                        </ElSelect>
                        <ElButton
                          link
                          type="danger"
                          @click="removeRow('parameters_schema', i)"
                        >
                          <IconifyIcon icon="lucide:trash-2" />
                        </ElButton>
                      </div>
                      <ElButton
                        size="small"
                        @click="
                          pushRow('parameters_schema', {
                            name: '',
                            type: 'string',
                            description: '',
                            required: false,
                          })
                        "
                      >
                        <IconifyIcon icon="lucide:plus" />
                        添加字段
                      </ElButton>
                    </div>
                  </ElFormItem>
                </PanelSection>
              </template>

              <!-- datasource -->
              <template v-if="selectedNode.type === 'datasource'">
                <PanelSection title="数据源" icon="lucide:folder-input">
                  <ElFormItem label="数据源类型">
                    <ElSelect v-model="selectedNode.data.source_type">
                      <ElOption label="文本" value="text" />
                      <ElOption label="URL" value="url" />
                    </ElSelect>
                  </ElFormItem>
                  <ElFormItem label="内容 / 地址">
                    <VarInput
                      v-model="selectedNode.data.value"
                      type="textarea"
                      :rows="4"
                      :variables="upstreamVars"
                    />
                  </ElFormItem>
                </PanelSection>
              </template>

              <!-- document-extractor -->
              <template v-if="selectedNode.type === 'document-extractor'">
                <PanelSection title="提取" icon="lucide:file-text">
                  <ElFormItem label="输入变量">
                    <VarInput
                      v-model="selectedNode.data.input"
                      :variables="upstreamVars"
                    />
                  </ElFormItem>
                  <p class="wf-hint">
                    从输入中抽取纯文本并规整空白，输出到 node.text。
                  </p>
                </PanelSection>
              </template>

              <!-- knowledge-index -->
              <template v-if="selectedNode.type === 'knowledge-index'">
                <PanelSection title="写入" icon="lucide:database">
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
                  <ElFormItem label="写入内容">
                    <VarInput
                      v-model="selectedNode.data.input"
                      :variables="upstreamVars"
                    />
                  </ElFormItem>
                </PanelSection>
              </template>

              <!-- code -->
              <template v-if="selectedNode.type === 'code'">
                <PanelSection title="输入变量" icon="lucide:braces">
                  <div class="wf-rows">
                    <div
                      v-for="(v, i) in selectedNode.data.variables"
                      :key="i"
                      class="wf-row"
                    >
                      <ElInput v-model="v.name" placeholder="变量名" />
                      <VarInput v-model="v.value" :variables="upstreamVars" />
                      <ElButton
                        link
                        type="danger"
                        @click="removeRow('variables', i)"
                      >
                        <IconifyIcon icon="lucide:trash-2" />
                      </ElButton>
                    </div>
                    <ElButton
                      size="small"
                      @click="pushRow('variables', { name: '', value: '' })"
                    >
                      <IconifyIcon icon="lucide:plus" />
                      添加变量
                    </ElButton>
                  </div>
                </PanelSection>
                <PanelSection title="代码" icon="lucide:code">
                  <ElFormItem label="语言">
                    <ElSelect v-model="selectedNode.data.language">
                      <ElOption label="Python" value="python" />
                      <ElOption label="JavaScript" value="javascript" />
                    </ElSelect>
                  </ElFormItem>
                  <ElFormItem label="代码（赋值 outputs 字典）">
                    <CodeEditor
                      v-model="selectedNode.data.code"
                      :language="
                        selectedNode.data.language === 'javascript'
                          ? 'javascript'
                          : 'python'
                      "
                      :min-height="180"
                    />
                  </ElFormItem>
                </PanelSection>
              </template>

              <!-- http-request -->
              <template v-if="selectedNode.type === 'http-request'">
                <PanelSection title="请求" icon="lucide:globe">
                  <ElFormItem label="方法">
                    <ElSelect v-model="selectedNode.data.method">
                      <ElOption
                        v-for="m in ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']"
                        :key="m"
                        :label="m"
                        :value="m"
                      />
                    </ElSelect>
                  </ElFormItem>
                  <ElFormItem label="URL">
                    <VarInput
                      v-model="selectedNode.data.url"
                      :variables="upstreamVars"
                    />
                  </ElFormItem>
                  <ElFormItem label="请求头 (JSON)">
                    <JsonEditor
                      :model-value="httpHeadersText"
                      :min-height="80"
                      @update:model-value="onHttpHeadersInput"
                    />
                  </ElFormItem>
                  <ElFormItem label="Query 参数 (JSON)">
                    <JsonEditor
                      :model-value="httpParamsText"
                      :min-height="80"
                      @update:model-value="onHttpParamsInput"
                    />
                  </ElFormItem>
                  <ElFormItem label="请求体">
                    <VarInput
                      v-model="selectedNode.data.body"
                      type="textarea"
                      :rows="3"
                      :variables="upstreamVars"
                    />
                  </ElFormItem>
                </PanelSection>
                <PanelSection title="高级" icon="lucide:sliders-horizontal">
                  <ElFormItem label="超时（秒）">
                    <ElInputNumber
                      v-model="selectedNode.data.timeout"
                      :min="1"
                      :max="300"
                    />
                  </ElFormItem>
                </PanelSection>
              </template>

              <!-- tool -->
              <template v-if="selectedNode.type === 'tool'">
                <PanelSection title="工具" icon="lucide:wrench">
                  <ElFormItem label="工具">
                    <ElSelect v-model="selectedNode.data.tool">
                      <ElOption
                        v-for="t in toolOptions"
                        :key="t.value"
                        :label="t.label"
                        :value="t.value"
                      />
                    </ElSelect>
                  </ElFormItem>
                  <ElFormItem label="参数 (JSON)">
                    <JsonEditor
                      :model-value="toolParamsText"
                      :min-height="100"
                      @update:model-value="onToolParamsInput"
                    />
                  </ElFormItem>
                </PanelSection>
              </template>

              <!-- list-operator -->
              <template v-if="selectedNode.type === 'list-operator'">
                <PanelSection title="输入" icon="lucide:list-filter">
                  <ElFormItem label="输入列表变量">
                    <VarInput
                      v-model="selectedNode.data.variable"
                      placeholder="如 node.result"
                      :variables="upstreamVars"
                    />
                  </ElFormItem>
                </PanelSection>
                <PanelSection title="过滤" icon="lucide:filter">
                  <ElFormItem label="过滤字段">
                    <ElInput v-model="selectedNode.data.filter_field" />
                  </ElFormItem>
                  <ElFormItem label="过滤运算符">
                    <ElSelect v-model="selectedNode.data.filter_operator">
                      <ElOption
                        v-for="op in operators"
                        :key="op"
                        :label="op"
                        :value="op"
                      />
                    </ElSelect>
                  </ElFormItem>
                  <ElFormItem label="过滤值">
                    <VarInput
                      v-model="selectedNode.data.filter_value"
                      :variables="upstreamVars"
                    />
                  </ElFormItem>
                </PanelSection>
                <PanelSection title="排序 / 截取" icon="lucide:arrow-down-up">
                  <ElFormItem label="排序">
                    <ElSelect v-model="selectedNode.data.order" clearable>
                      <ElOption label="升序" value="asc" />
                      <ElOption label="降序" value="desc" />
                    </ElSelect>
                  </ElFormItem>
                  <ElFormItem label="排序字段">
                    <ElInput v-model="selectedNode.data.order_field" />
                  </ElFormItem>
                  <ElFormItem label="限制数量（0 不限制）">
                    <ElInputNumber v-model="selectedNode.data.limit" :min="0" />
                  </ElFormItem>
                  <ElFormItem label="提取字段">
                    <ElInput v-model="selectedNode.data.extract_field" />
                  </ElFormItem>
                </PanelSection>
              </template>

              <!-- iteration -->
              <template v-if="selectedNode.type === 'iteration'">
                <PanelSection title="迭代" icon="lucide:repeat">
                  <ElFormItem label="输入列表变量">
                    <VarInput
                      v-model="selectedNode.data.input"
                      placeholder="如 node.result"
                      :variables="upstreamVars"
                    />
                  </ElFormItem>
                  <ElFormItem label="每项模板（可用变量 item / index）">
                    <VarInput
                      v-model="selectedNode.data.item_template"
                      type="textarea"
                      :rows="3"
                      :variables="iterationVars"
                    />
                  </ElFormItem>
                  <ElFormItem label="最大迭代项">
                    <ElInputNumber
                      v-model="selectedNode.data.max_items"
                      :min="1"
                      :max="1000"
                    />
                  </ElFormItem>
                </PanelSection>
              </template>

              <!-- loop -->
              <template v-if="selectedNode.type === 'loop'">
                <PanelSection title="循环" icon="lucide:rotate-cw">
                  <ElFormItem label="每轮模板（可用变量 loop_index）">
                    <VarInput
                      v-model="selectedNode.data.template"
                      type="textarea"
                      :rows="3"
                      :variables="loopVars"
                    />
                  </ElFormItem>
                  <ElFormItem label="最大循环次数">
                    <ElInputNumber
                      v-model="selectedNode.data.max_loops"
                      :min="1"
                      :max="100"
                    />
                  </ElFormItem>
                </PanelSection>
                <PanelSection title="终止条件" icon="lucide:circle-stop">
                  <ElFormItem label="终止条件变量">
                    <VarInput
                      v-model="selectedNode.data.break_when.variable"
                      :variables="loopVars"
                    />
                  </ElFormItem>
                  <ElFormItem label="终止运算符">
                    <ElSelect v-model="selectedNode.data.break_when.operator">
                      <ElOption
                        v-for="op in operators"
                        :key="op"
                        :label="op"
                        :value="op"
                      />
                    </ElSelect>
                  </ElFormItem>
                  <ElFormItem label="终止比较值">
                    <ElInput v-model="selectedNode.data.break_when.value" />
                  </ElFormItem>
                </PanelSection>
              </template>

              <!-- human-input -->
              <template v-if="selectedNode.type === 'human-input'">
                <PanelSection title="人工输入" icon="lucide:user-check">
                  <ElFormItem label="提示语">
                    <ElInput v-model="selectedNode.data.prompt" />
                  </ElFormItem>
                  <ElFormItem label="默认回填值（测试运行时使用）">
                    <VarInput
                      v-model="selectedNode.data.default"
                      type="textarea"
                      :rows="2"
                      :variables="upstreamVars"
                    />
                  </ElFormItem>
                </PanelSection>
              </template>

              <!-- assigner -->
              <template v-if="selectedNode.type === 'assigner'">
                <PanelSection title="变量赋值" icon="lucide:variable">
                  <ElFormItem label="变量赋值">
                    <div class="wf-rows">
                      <div
                        v-for="(a, i) in selectedNode.data.assignments"
                        :key="i"
                        class="wf-row"
                      >
                        <ElInput v-model="a.variable" placeholder="变量名" />
                        <VarInput
                          v-model="a.value"
                          placeholder="值或 {{ref}}"
                          :variables="upstreamVars"
                        />
                        <ElButton
                          link
                          type="danger"
                          @click="removeRow('assignments', i)"
                        >
                          <IconifyIcon icon="lucide:trash-2" />
                        </ElButton>
                      </div>
                      <ElButton
                        size="small"
                        @click="
                          pushRow('assignments', { variable: '', value: '' })
                        "
                      >
                        <IconifyIcon icon="lucide:plus" />
                        添加赋值
                      </ElButton>
                    </div>
                  </ElFormItem>
                </PanelSection>
              </template>

              <!-- variable-aggregator -->
              <template v-if="selectedNode.type === 'variable-aggregator'">
                <PanelSection title="变量聚合" icon="lucide:combine">
                  <ElFormItem label="聚合模式">
                    <ElSelect v-model="selectedNode.data.mode">
                      <ElOption label="第一个非空值" value="first" />
                      <ElOption label="合并为数组" value="array" />
                    </ElSelect>
                  </ElFormItem>
                  <ElFormItem label="变量引用">
                    <div class="wf-rows">
                      <div
                        v-for="(v, i) in selectedNode.data.variables"
                        :key="i"
                        :title="String(v)"
                        class="wf-row"
                      >
                        <VarInput
                          v-model="selectedNode.data.variables[i]"
                          placeholder="如 nodeA.text"
                          :variables="upstreamVars"
                        />
                        <ElButton
                          link
                          type="danger"
                          @click="removeRow('variables', i)"
                        >
                          <IconifyIcon icon="lucide:trash-2" />
                        </ElButton>
                      </div>
                      <ElButton size="small" @click="pushRow('variables', '')">
                        <IconifyIcon icon="lucide:plus" />
                        添加引用
                      </ElButton>
                    </div>
                  </ElFormItem>
                </PanelSection>
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
        <div v-for="(l, i) in runLog" :key="i" style="margin-bottom: 4px">
          <div
            :style="{ color: l.type === 'error' ? '#ef4444' : undefined }"
            style="
              display: flex;
              gap: 6px;
              align-items: center;
              font-family: monospace;
              font-size: 12px;
              line-height: 1.8;
            "
          >
            <IconifyIcon
              :icon="
                l.type === 'error'
                  ? 'lucide:x-circle'
                  : l.type === 'node'
                    ? 'lucide:play'
                    : 'lucide:check'
              "
            />
            {{ l.text }}
          </div>
          <div
            v-if="l.detail"
            style="
              padding: 6px 8px;
              margin: 2px 0 0 20px;
              font-family: monospace;
              font-size: 11px;
              line-height: 1.5;
              color: var(--el-text-color-regular);
              overflow-wrap: anywhere;
              white-space: pre-wrap;
              background: var(--el-fill-color-light);
              border-radius: 4px;
            "
          >
            {{ l.detail }}
          </div>
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
  width: 168px;
  padding: 12px 8px 12px 12px;
  background: var(--el-bg-color);
  border-right: 1px solid var(--el-border-color-light);
}

.wf-palette__title {
  margin-bottom: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.wf-palette__group {
  margin-bottom: 12px;
}

.wf-palette__group-label {
  margin-bottom: 4px;
  font-size: 11px;
  font-weight: 600;
  color: var(--el-text-color-secondary);
}

.wf-palette__btn {
  display: flex;
  justify-content: flex-start;
  width: 100%;
  margin-bottom: 4px;
  margin-left: 0 !important;
}

.wf-hint {
  font-size: 12px;
  line-height: 1.6;
  color: var(--el-text-color-secondary);
}

.wf-varhint {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  color: var(--el-text-color-secondary);
}

.wf-varhint code {
  padding: 1px 5px;
  font-family: ui-monospace, monospace;
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
  border-radius: 4px;
}

.wf-rows {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
}

.wf-row {
  display: flex;
  gap: 4px;
  align-items: center;
}

.wf-canvas {
  flex: 1;
  min-width: 0;
  height: 100%;
}

.wf-config {
  width: 360px;
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
