<script lang="ts" setup>
import type {
  ChunkStrategy,
  IndexMethod,
  KnowledgeBase,
  PipelineStage,
} from '#/api/agentscope/knowledge';

import { computed, markRaw, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { IconifyIcon } from '@vben/icons';

import { Background } from '@vue-flow/background';
import { Controls } from '@vue-flow/controls';
import { VueFlow } from '@vue-flow/core';
import {
  ElButton,
  ElEmpty,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElMessage,
  ElOption,
  ElScrollbar,
  ElSelect,
  ElSwitch,
} from 'element-plus';

import { credentialApi, knowledgeApi, modelApi } from '#/api/agentscope';

import PipelineNode from './PipelineNode.vue';

import '@vue-flow/core/dist/style.css';
import '@vue-flow/core/dist/theme-default.css';
import '@vue-flow/controls/dist/style.css';

const route = useRoute();
const router = useRouter();
const kbId = route.params.id as string;

const PIPELINE_NODE_TYPES = [
  'datasource',
  'extract',
  'clean',
  'split',
  'split_parent_child',
  'qa',
  'embed',
  'build_graph',
  'index',
];
const nodeTypes: any = Object.fromEntries(
  PIPELINE_NODE_TYPES.map((t) => [t, markRaw(PipelineNode)]),
);

const kb = ref<KnowledgeBase | null>(null);
const stages = ref<PipelineStage[]>([]);
const chunkStrategy = ref<ChunkStrategy>('general');
const indexMethod = ref<IndexMethod>('keyword');
const kgCredentialId = ref('');
const kgModel = ref('');
const selectedIndex = ref<number>(-1); // -1 = datasource; else index into stages
const saving = ref(false);
const reindexing = ref(false);

const credentials = ref<any[]>([]);
const models = ref<any[]>([]);

// Mirror of the backend ``build_pipeline`` so the canvas updates immediately
// when the strategy / method changes (before saving).
function buildStages(
  strategy: ChunkStrategy,
  method: IndexMethod,
): PipelineStage[] {
  const split: PipelineStage =
    strategy === 'parent_child'
      ? {
          type: 'split_parent_child',
          name: '父子分块',
          config: {
            parent_size: 1200,
            chunk_size: 400,
            chunk_overlap: 40,
            separator: '\n\n',
          },
        }
      : {
          type: 'split',
          name: '通用分块',
          config: { chunk_size: 500, chunk_overlap: 50, separator: '\n\n' },
        };
  const out: PipelineStage[] = [
    { type: 'extract', name: '提取文本', config: {} },
    {
      type: 'clean',
      name: '清洗',
      config: { strip: true, collapse_whitespace: true },
    },
    split,
  ];
  if (method === 'vector' || method === 'hybrid') {
    out.push({ type: 'embed', name: '向量嵌入', config: { dim: 256 } });
  }
  if (method === 'knowledge_graph') {
    out.push({
      type: 'build_graph',
      name: '语义知识图谱',
      config: { max_triples_per_chunk: 8 },
    });
  }
  out.push({ type: 'index', name: '建立索引', config: {} });
  return out;
}

const nodes = computed(() => {
  const list: any[] = [
    {
      id: 's0',
      type: 'datasource',
      position: { x: 0, y: 80 },
      data: { name: '数据源' },
    },
  ];
  stages.value.forEach((s, i) => {
    list.push({
      id: `s${i + 1}`,
      type: s.type,
      position: { x: (i + 1) * 210, y: 80 },
      data: s,
    });
  });
  return list;
});

const edges = computed(() => {
  const list: any[] = [];
  for (let i = 0; i < stages.value.length + 1; i += 1) {
    list.push({
      id: `e${i}`,
      source: `s${i}`,
      target: `s${i + 1}`,
      animated: true,
    });
  }
  return list;
});

const selectedStage = computed<null | PipelineStage>(() =>
  selectedIndex.value >= 0 ? (stages.value[selectedIndex.value] ?? null) : null,
);

function onNodeClick(e: any) {
  const id: string = e.node?.id ?? '';
  selectedIndex.value = id === 's0' ? -1 : Number(id.slice(1)) - 1;
}

function credentialType(id: string): string {
  return credentials.value.find((c) => c.id === id)?.data?.type ?? '';
}

function onStrategyMethodChange() {
  stages.value = buildStages(chunkStrategy.value, indexMethod.value);
  selectedIndex.value = -1;
  if (indexMethod.value === 'knowledge_graph' && kgCredentialId.value) {
    void loadModels(kgCredentialId.value);
  }
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
  const [k, cr] = await Promise.all([
    knowledgeApi.getKnowledgeBase(kbId),
    credentialApi.listCredentials(),
  ]);
  kb.value = k;
  stages.value = (k.pipeline ?? []).map((s) => ({
    ...s,
    config: { ...s.config },
  }));
  chunkStrategy.value = k.chunk_strategy;
  indexMethod.value = k.index_method;
  kgCredentialId.value = k.kg_credential_id ?? '';
  kgModel.value = k.kg_model ?? '';
  credentials.value = cr.credentials ?? [];
  if (kgCredentialId.value) void loadModels(kgCredentialId.value);
}

async function save() {
  saving.value = true;
  try {
    await knowledgeApi.updateKnowledgeBase(kbId, {
      chunk_strategy: chunkStrategy.value,
      index_method: indexMethod.value,
      kg_credential_id: kgCredentialId.value,
      kg_model: kgModel.value,
      kg_type:
        indexMethod.value === 'knowledge_graph'
          ? credentialType(kgCredentialId.value)
          : '',
      pipeline: stages.value,
    });
    ElMessage.success('流水线已保存');
  } finally {
    saving.value = false;
  }
}

async function saveAndReindex() {
  await save();
  reindexing.value = true;
  try {
    const res = await knowledgeApi.reindexKnowledgeBase(kbId);
    ElMessage.success(`已重建索引（${res.reindexed} 篇文档）`);
  } finally {
    reindexing.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="pl-editor">
    <div class="pl-toolbar">
      <ElButton text @click="router.push('/agentscope/knowledge')">
        <IconifyIcon icon="lucide:arrow-left" />
      </ElButton>
      <strong>{{ kb?.name || '知识流水线编排' }}</strong>
      <span class="pl-toolbar__label">分块策略</span>
      <ElSelect
        v-model="chunkStrategy"
        size="small"
        style="width: 130px"
        @change="onStrategyMethodChange"
      >
        <ElOption label="通用分块" value="general" />
        <ElOption label="父子分块" value="parent_child" />
      </ElSelect>
      <span class="pl-toolbar__label">索引方式</span>
      <ElSelect
        v-model="indexMethod"
        size="small"
        style="width: 150px"
        @change="onStrategyMethodChange"
      >
        <ElOption label="关键词检索" value="keyword" />
        <ElOption label="向量检索" value="vector" />
        <ElOption label="语义知识图谱" value="knowledge_graph" />
        <ElOption label="混合检索" value="hybrid" />
      </ElSelect>
      <template v-if="indexMethod === 'knowledge_graph'">
        <ElSelect
          v-model="kgCredentialId"
          size="small"
          placeholder="抽取凭证"
          style="width: 150px"
          @change="(v: string) => loadModels(v)"
        >
          <ElOption
            v-for="c in credentials"
            :key="c.id"
            :label="`${c.data?.name || c.id} (${c.data?.type})`"
            :value="c.id"
          />
        </ElSelect>
        <ElSelect
          v-model="kgModel"
          size="small"
          filterable
          allow-create
          default-first-option
          placeholder="抽取模型"
          style="width: 150px"
        >
          <ElOption
            v-for="m in models"
            :key="m.model"
            :label="m.model"
            :value="m.model"
          />
        </ElSelect>
      </template>
      <div style="flex: 1"></div>
      <ElButton :loading="saving" @click="save">
        <IconifyIcon icon="lucide:save" style="margin-right: 4px" />
        保存
      </ElButton>
      <ElButton type="primary" :loading="reindexing" @click="saveAndReindex">
        <IconifyIcon icon="lucide:refresh-cw" style="margin-right: 4px" />
        保存并重建索引
      </ElButton>
    </div>

    <div class="pl-main">
      <div class="pl-canvas">
        <VueFlow
          :node-types="nodeTypes"
          :nodes="nodes"
          :edges="edges"
          :default-viewport="{ x: 40, y: 20, zoom: 0.9 }"
          @node-click="onNodeClick"
        >
          <Background :gap="16" />
          <Controls />
        </VueFlow>
      </div>

      <div class="pl-config">
        <ElScrollbar>
          <div style="padding: 16px">
            <!-- datasource (virtual) -->
            <template v-if="selectedIndex === -1">
              <h4>数据源</h4>
              <p class="pl-hint">
                知识库的文档来源。支持文本粘贴、文件上传与 URL
                抓取（在知识库管理页添加文档，或在工作流中用「知识写入」节点写入）。
              </p>
            </template>

            <template v-else-if="selectedStage">
              <h4>{{ selectedStage.name }}</h4>

              <!-- clean -->
              <ElForm
                v-if="selectedStage.type === 'clean'"
                label-position="top"
              >
                <ElFormItem label="去除首尾空白">
                  <ElSwitch v-model="selectedStage.config.strip" />
                </ElFormItem>
                <ElFormItem label="合并连续空白">
                  <ElSwitch
                    v-model="selectedStage.config.collapse_whitespace"
                  />
                </ElFormItem>
              </ElForm>

              <!-- general split -->
              <ElForm
                v-else-if="selectedStage.type === 'split'"
                label-position="top"
              >
                <ElFormItem label="分块大小">
                  <ElInputNumber
                    v-model="selectedStage.config.chunk_size"
                    :min="50"
                    :max="4000"
                  />
                </ElFormItem>
                <ElFormItem label="分块重叠">
                  <ElInputNumber
                    v-model="selectedStage.config.chunk_overlap"
                    :min="0"
                    :max="1000"
                  />
                </ElFormItem>
                <ElFormItem label="分隔符">
                  <ElInput v-model="selectedStage.config.separator" />
                </ElFormItem>
              </ElForm>

              <!-- parent-child split -->
              <ElForm
                v-else-if="selectedStage.type === 'split_parent_child'"
                label-position="top"
              >
                <ElFormItem label="父块大小">
                  <ElInputNumber
                    v-model="selectedStage.config.parent_size"
                    :min="200"
                    :max="8000"
                  />
                </ElFormItem>
                <ElFormItem label="子块大小">
                  <ElInputNumber
                    v-model="selectedStage.config.chunk_size"
                    :min="50"
                    :max="4000"
                  />
                </ElFormItem>
                <ElFormItem label="子块重叠">
                  <ElInputNumber
                    v-model="selectedStage.config.chunk_overlap"
                    :min="0"
                    :max="1000"
                  />
                </ElFormItem>
                <ElFormItem label="分隔符">
                  <ElInput v-model="selectedStage.config.separator" />
                </ElFormItem>
              </ElForm>

              <!-- embed -->
              <ElForm
                v-else-if="selectedStage.type === 'embed'"
                label-position="top"
              >
                <ElFormItem label="向量维度">
                  <ElInputNumber
                    v-model="selectedStage.config.dim"
                    :min="32"
                    :max="2048"
                    :step="32"
                  />
                </ElFormItem>
              </ElForm>

              <!-- build_graph -->
              <ElForm
                v-else-if="selectedStage.type === 'build_graph'"
                label-position="top"
              >
                <ElFormItem label="每块最大三元组数">
                  <ElInputNumber
                    v-model="selectedStage.config.max_triples_per_chunk"
                    :min="1"
                    :max="50"
                  />
                </ElFormItem>
                <p class="pl-hint">
                  使用上方「抽取凭证 / 抽取模型」调用 LLM 从每个分块中抽取
                  (主语,谓语,宾语) 三元组，构建语义知识图谱。
                </p>
              </ElForm>

              <!-- extract / index (info only) -->
              <p v-else class="pl-hint">
                <template v-if="selectedStage.type === 'extract'">
                  从原始文档中提取纯文本内容，作为后续清洗与分块的输入。
                </template>
                <template v-else-if="selectedStage.type === 'index'">
                  将处理后的分块写入检索索引（关键词 / 向量 / 图谱），完成摄取。
                </template>
                <template v-else>该节点无可配置项。</template>
              </p>
            </template>

            <ElEmpty v-else description="在画布中选择一个节点进行配置" />
          </div>
        </ElScrollbar>
      </div>
    </div>
  </div>
</template>

<style scoped>
.pl-editor {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 90px);
}

.pl-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  padding: 8px 12px;
  background: var(--el-bg-color);
  border-bottom: 1px solid var(--el-border-color-light);
}

.pl-toolbar__label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.pl-main {
  display: flex;
  flex: 1;
  min-height: 0;
}

.pl-canvas {
  flex: 1;
  min-width: 0;
  height: 100%;
}

.pl-config {
  width: 320px;
  background: var(--el-bg-color);
  border-left: 1px solid var(--el-border-color-light);
}

.pl-hint {
  font-size: 12px;
  line-height: 1.7;
  color: var(--el-text-color-secondary);
}
</style>
