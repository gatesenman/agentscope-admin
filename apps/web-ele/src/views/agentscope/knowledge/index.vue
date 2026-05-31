<script lang="ts" setup>
import type {
  ChunkStrategy,
  IndexMethod,
  KnowledgeBase,
  KnowledgeBaseListItem,
  KnowledgeDocument,
  KnowledgeTriple,
  PipelineStage,
  RetrievedChunk,
} from '#/api/agentscope/knowledge';
import type { CredentialRecord, ModelCard } from '#/api/agentscope/types';

import { computed, onMounted, reactive, ref, toRaw } from 'vue';
import { useRouter } from 'vue-router';

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
  ElInputNumber,
  ElMessage,
  ElOption,
  ElPopconfirm,
  ElSelect,
  ElTable,
  ElTableColumn,
  ElTabPane,
  ElTabs,
  ElTag,
} from 'element-plus';

import { credentialApi, knowledgeApi, modelApi } from '#/api/agentscope';
import { $t } from '#/locales';

const chunkStrategies: { label: string; value: ChunkStrategy }[] = [
  { value: 'general', label: 'strategyGeneral' },
  { value: 'parent_child', label: 'strategyParentChild' },
];

const indexMethods: { label: string; value: IndexMethod }[] = [
  { value: 'keyword', label: 'methodKeyword' },
  { value: 'vector', label: 'methodVector' },
  { value: 'knowledge_graph', label: 'methodGraph' },
  { value: 'hybrid', label: 'methodHybrid' },
];

// Visual orchestration: lucide icon per pipeline stage type (no emoji).
const STAGE_ICON: Record<string, string> = {
  extract: 'lucide:file-input',
  clean: 'lucide:eraser',
  split: 'lucide:scissors',
  split_parent_child: 'lucide:list-tree',
  embed: 'lucide:boxes',
  build_graph: 'lucide:share-2',
  index: 'lucide:database',
};

function methodLabel(m: string): string {
  const found = indexMethods.find((i) => i.value === m);
  return found ? $t(`agentscope.knowledge.${found.label}`) : m;
}

function needsKg(method: string): boolean {
  return method === 'knowledge_graph';
}

/** Mirror of the backend `build_pipeline` so the create dialog can preview. */
function buildPreview(
  strategy: ChunkStrategy,
  method: IndexMethod,
): PipelineStage[] {
  const split: PipelineStage =
    strategy === 'parent_child'
      ? {
          type: 'split_parent_child',
          name: $t('agentscope.knowledge.stageSplitParentChild'),
          config: {},
        }
      : {
          type: 'split',
          name: $t('agentscope.knowledge.stageSplit'),
          config: {},
        };
  const indexers: PipelineStage[] = [];
  if (method === 'vector' || method === 'hybrid') {
    indexers.push({
      type: 'embed',
      name: $t('agentscope.knowledge.stageEmbed'),
      config: {},
    });
  }
  if (method === 'knowledge_graph') {
    indexers.push({
      type: 'build_graph',
      name: $t('agentscope.knowledge.stageBuildGraph'),
      config: {},
    });
  }
  return [
    {
      type: 'extract',
      name: $t('agentscope.knowledge.stageExtract'),
      config: {},
    },
    { type: 'clean', name: $t('agentscope.knowledge.stageClean'), config: {} },
    split,
    ...indexers,
    { type: 'index', name: $t('agentscope.knowledge.stageIndex'), config: {} },
  ];
}

const router = useRouter();
const loading = ref(false);
const items = ref<KnowledgeBaseListItem[]>([]);
const credentials = ref<CredentialRecord[]>([]);

// ---- create dialog ----
const createDialog = ref(false);
const saving = ref(false);
const form = reactive({
  name: '',
  description: '',
  icon: 'lucide:book-open',
  chunk_strategy: 'general' as ChunkStrategy,
  index_method: 'keyword' as IndexMethod,
  kg_credential_id: '',
  kg_model: '',
});
const createKgModels = ref<ModelCard[]>([]);

const previewPipeline = computed(() =>
  buildPreview(form.chunk_strategy, form.index_method),
);

// ---- manage drawer ----
const drawer = ref(false);
const activeTab = ref('docs');
const current = ref<KnowledgeBase | null>(null);
const documents = ref<KnowledgeDocument[]>([]);
const docForm = reactive({ name: '', content: '' });
const addingDoc = ref(false);

// method editing inside the drawer
const editMethod = reactive({
  chunk_strategy: 'general' as ChunkStrategy,
  index_method: 'keyword' as IndexMethod,
  kg_credential_id: '',
  kg_model: '',
});
const editKgModels = ref<ModelCard[]>([]);
const splitConfig = reactive({ chunk_size: 500, chunk_overlap: 50 });
const reindexing = ref(false);

// triples
const triples = ref<KnowledgeTriple[]>([]);

// retrieval test
const queryText = ref('');
const retrieving = ref(false);
const retrieveMethod = ref<string>('');
const hits = ref<RetrievedChunk[]>([]);

const splitStageIndex = computed(() =>
  (current.value?.pipeline ?? []).findIndex(
    (s) => s.type === 'split' || s.type === 'split_parent_child',
  ),
);

function credentialType(id: string): string {
  return credentials.value.find((c) => c.id === id)?.data?.type ?? '';
}

async function fetchModels(credentialId: string): Promise<ModelCard[]> {
  const type = credentialType(credentialId);
  if (!type) return [];
  try {
    const res = await modelApi.listModels(type);
    return res.models ?? [];
  } catch {
    // provider may not support listing; manual entry still allowed
    return [];
  }
}

async function onCreateCredentialChange(credentialId: string) {
  form.kg_model = '';
  createKgModels.value = await fetchModels(credentialId);
}

async function onEditCredentialChange(credentialId: string) {
  editMethod.kg_model = '';
  editKgModels.value = await fetchModels(credentialId);
}

async function load() {
  loading.value = true;
  try {
    const [res, cr] = await Promise.all([
      knowledgeApi.listKnowledgeBases(),
      credentialApi.listCredentials(),
    ]);
    items.value = res.items ?? [];
    credentials.value = cr.credentials ?? [];
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  form.name = '';
  form.description = '';
  form.icon = 'lucide:book-open';
  form.chunk_strategy = 'general';
  form.index_method = 'keyword';
  form.kg_credential_id = credentials.value[0]?.id ?? '';
  form.kg_model = '';
  createKgModels.value = [];
  if (form.kg_credential_id) {
    void onCreateCredentialChange(form.kg_credential_id);
  }
  createDialog.value = true;
}

async function create() {
  if (!form.name) {
    ElMessage.warning($t('agentscope.common.name'));
    return;
  }
  saving.value = true;
  try {
    await knowledgeApi.createKnowledgeBase({
      ...form,
      kg_type: needsKg(form.index_method)
        ? credentialType(form.kg_credential_id)
        : '',
    });
    ElMessage.success($t('agentscope.common.saveSuccess'));
    createDialog.value = false;
    await load();
  } finally {
    saving.value = false;
  }
}

async function remove(kb: KnowledgeBase) {
  await knowledgeApi.deleteKnowledgeBase(kb.id);
  ElMessage.success($t('agentscope.common.deleteSuccess'));
  await load();
}

async function openManage(kb: KnowledgeBase) {
  current.value = kb;
  activeTab.value = 'docs';
  hits.value = [];
  queryText.value = '';
  retrieveMethod.value = '';
  triples.value = [];
  editMethod.chunk_strategy = kb.chunk_strategy ?? 'general';
  editMethod.index_method = kb.index_method ?? 'keyword';
  editMethod.kg_credential_id = kb.kg_credential_id ?? '';
  editMethod.kg_model = kb.kg_model ?? '';
  editKgModels.value = [];
  if (editMethod.kg_credential_id) {
    void onEditCredentialChange(editMethod.kg_credential_id);
  }
  const split = kb.pipeline.find(
    (s) => s.type === 'split' || s.type === 'split_parent_child',
  );
  splitConfig.chunk_size = split?.config?.chunk_size ?? 500;
  splitConfig.chunk_overlap = split?.config?.chunk_overlap ?? 50;
  await loadDocuments();
  drawer.value = true;
}

async function loadDocuments() {
  if (!current.value) return;
  const res = await knowledgeApi.listDocuments(current.value.id);
  documents.value = res.items ?? [];
}

async function loadTriples() {
  if (!current.value) return;
  const res = await knowledgeApi.listTriples(current.value.id);
  triples.value = res.items ?? [];
}

async function addDocument() {
  if (!current.value || !docForm.content) {
    ElMessage.warning($t('agentscope.knowledge.contentRequired'));
    return;
  }
  addingDoc.value = true;
  try {
    await knowledgeApi.addDocument(current.value.id, {
      name: docForm.name || 'untitled',
      content: docForm.content,
    });
    docForm.name = '';
    docForm.content = '';
    ElMessage.success($t('agentscope.knowledge.indexed'));
    await loadDocuments();
    await load();
  } finally {
    addingDoc.value = false;
  }
}

async function reindex(doc: KnowledgeDocument) {
  if (!current.value) return;
  await knowledgeApi.reindexDocument(current.value.id, doc.id);
  await loadDocuments();
}

async function removeDoc(doc: KnowledgeDocument) {
  if (!current.value) return;
  await knowledgeApi.deleteDocument(current.value.id, doc.id);
  await loadDocuments();
  await load();
}

/** Persist the build method + split config, then rebuild every document. */
async function applyMethod() {
  if (!current.value) return;
  reindexing.value = true;
  try {
    const pipeline = structuredClone(toRaw(current.value.pipeline));
    const idx = splitStageIndex.value;
    if (idx >= 0 && pipeline[idx]) {
      pipeline[idx].config.chunk_size = splitConfig.chunk_size;
      pipeline[idx].config.chunk_overlap = splitConfig.chunk_overlap;
    }
    const methodChanged =
      editMethod.chunk_strategy !== current.value.chunk_strategy ||
      editMethod.index_method !== current.value.index_method;
    const updated = await knowledgeApi.updateKnowledgeBase(current.value.id, {
      chunk_strategy: editMethod.chunk_strategy,
      index_method: editMethod.index_method,
      kg_credential_id: editMethod.kg_credential_id,
      kg_model: editMethod.kg_model,
      kg_type: needsKg(editMethod.index_method)
        ? credentialType(editMethod.kg_credential_id)
        : '',
      // Keep the edited split config only when the method (and thus the
      // generated pipeline) did not change; otherwise let the backend
      // regenerate the pipeline from the new method.
      ...(methodChanged ? {} : { pipeline }),
    });
    current.value = updated;
    editMethod.chunk_strategy = updated.chunk_strategy;
    editMethod.index_method = updated.index_method;
    await knowledgeApi.reindexKnowledgeBase(current.value.id);
    ElMessage.success($t('agentscope.knowledge.reindexed'));
    await loadDocuments();
    await load();
  } finally {
    reindexing.value = false;
  }
}

async function runRetrieve() {
  if (!current.value || !queryText.value) return;
  retrieving.value = true;
  try {
    const res = await knowledgeApi.retrieve(
      current.value.id,
      queryText.value,
      undefined,
      retrieveMethod.value || undefined,
    );
    hits.value = res.items ?? [];
  } finally {
    retrieving.value = false;
  }
}

function onTabChange(name: number | string) {
  if (name === 'triples') void loadTriples();
}

onMounted(load);
</script>

<template>
  <Page :title="$t('agentscope.menu.knowledge')">
    <template #extra>
      <ElButton type="primary" @click="openCreate">
        {{ $t('agentscope.knowledge.newKb') }}
      </ElButton>
    </template>

    <ElCard shadow="never">
      <ElTable v-loading="loading" :data="items" stripe>
        <ElTableColumn :label="$t('agentscope.common.name')" min-width="220">
          <template #default="{ row }">
            <IconifyIcon
              v-if="row.kb.icon && row.kb.icon.includes(':')"
              :icon="row.kb.icon"
              style="margin-right: 6px; vertical-align: -2px"
            />
            <strong>{{ row.kb.name }}</strong>
            <div style="font-size: 12px; color: var(--el-text-color-secondary)">
              {{ row.kb.description }}
            </div>
          </template>
        </ElTableColumn>
        <ElTableColumn :label="$t('agentscope.knowledge.method')" width="200">
          <template #default="{ row }">
            <ElTag size="small" type="info">
              {{
                $t(
                  `agentscope.knowledge.${
                    chunkStrategies.find(
                      (s) => s.value === row.kb.chunk_strategy,
                    )?.label ?? 'strategyGeneral'
                  }`,
                )
              }}
            </ElTag>
            <ElTag size="small" style="margin-left: 4px">
              {{ methodLabel(row.kb.index_method) }}
            </ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn :label="$t('agentscope.knowledge.docs')" width="80">
          <template #default="{ row }">
            <ElTag type="info">{{ row.doc_count }}</ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn :label="$t('agentscope.knowledge.chunks')" width="80">
          <template #default="{ row }">
            <ElTag>{{ row.chunk_count }}</ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn label="Top-K" width="80" prop="kb.top_k" />
        <ElTableColumn :label="$t('agentscope.common.actions')" width="240">
          <template #default="{ row }">
            <ElButton link type="primary" @click="openManage(row.kb)">
              {{ $t('agentscope.knowledge.manage') }}
            </ElButton>
            <ElButton
              link
              type="primary"
              @click="
                router.push(`/agentscope/knowledge/${row.kb.id}/pipeline`)
              "
            >
              流水线编排
            </ElButton>
            <ElPopconfirm
              :title="$t('agentscope.common.confirmDelete')"
              @confirm="remove(row.kb)"
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
          <ElEmpty :description="$t('agentscope.knowledge.empty')" />
        </template>
      </ElTable>
    </ElCard>

    <!-- Create dialog -->
    <ElDialog
      v-model="createDialog"
      :title="$t('agentscope.knowledge.newKb')"
      width="640px"
    >
      <ElForm label-width="110px">
        <ElFormItem :label="$t('agentscope.knowledge.icon')">
          <ElInput
            v-model="form.icon"
            style="width: 200px"
            placeholder="lucide:book-open"
          />
        </ElFormItem>
        <ElFormItem :label="$t('agentscope.common.name')">
          <ElInput v-model="form.name" />
        </ElFormItem>
        <ElFormItem :label="$t('agentscope.common.description')">
          <ElInput v-model="form.description" type="textarea" :rows="2" />
        </ElFormItem>

        <p
          style="
            margin: 4px 0 12px;
            font-size: 12px;
            color: var(--el-text-color-secondary);
          "
        >
          {{ $t('agentscope.knowledge.createMethodHint') }}
        </p>

        <ElFormItem :label="$t('agentscope.knowledge.chunkStrategy')">
          <ElSelect v-model="form.chunk_strategy" style="width: 240px">
            <ElOption
              v-for="s in chunkStrategies"
              :key="s.value"
              :label="$t(`agentscope.knowledge.${s.label}`)"
              :value="s.value"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem :label="$t('agentscope.knowledge.indexMethod')">
          <ElSelect v-model="form.index_method" style="width: 240px">
            <ElOption
              v-for="m in indexMethods"
              :key="m.value"
              :label="$t(`agentscope.knowledge.${m.label}`)"
              :value="m.value"
            />
          </ElSelect>
        </ElFormItem>

        <template v-if="needsKg(form.index_method)">
          <ElFormItem :label="$t('agentscope.knowledge.kgCredential')">
            <ElSelect
              v-model="form.kg_credential_id"
              style="width: 240px"
              @change="onCreateCredentialChange"
            >
              <ElOption
                v-for="c in credentials"
                :key="c.id"
                :label="`${c.data?.name || c.id} · ${c.data?.type}`"
                :value="c.id"
              />
            </ElSelect>
          </ElFormItem>
          <ElFormItem :label="$t('agentscope.knowledge.kgModel')">
            <ElSelect
              v-model="form.kg_model"
              allow-create
              filterable
              style="width: 240px"
            >
              <ElOption
                v-for="m in createKgModels"
                :key="m.name"
                :label="m.name"
                :value="m.name"
              />
            </ElSelect>
          </ElFormItem>
        </template>

        <ElFormItem :label="$t('agentscope.knowledge.pipelinePreview')">
          <div class="pipeline-chain">
            <template v-for="(st, i) in previewPipeline" :key="st.type">
              <div class="pipeline-node">
                <IconifyIcon
                  :icon="STAGE_ICON[st.type] ?? 'lucide:circle'"
                  class="pipeline-node__icon"
                />
                <span>{{ st.name }}</span>
              </div>
              <IconifyIcon
                v-if="i < previewPipeline.length - 1"
                icon="lucide:chevron-right"
                class="pipeline-arrow"
              />
            </template>
          </div>
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="createDialog = false">
          {{ $t('agentscope.common.cancel') }}
        </ElButton>
        <ElButton type="primary" :loading="saving" @click="create">
          {{ $t('agentscope.common.confirm') }}
        </ElButton>
      </template>
    </ElDialog>

    <!-- Manage drawer -->
    <ElDrawer
      v-model="drawer"
      :title="current?.name"
      size="720px"
      destroy-on-close
    >
      <ElTabs v-model="activeTab" @tab-change="onTabChange">
        <!-- Documents -->
        <ElTabPane :label="$t('agentscope.knowledge.docs')" name="docs">
          <ElForm>
            <ElFormItem>
              <ElInput
                v-model="docForm.name"
                :placeholder="$t('agentscope.knowledge.docName')"
              />
            </ElFormItem>
            <ElFormItem>
              <ElInput
                v-model="docForm.content"
                type="textarea"
                :rows="5"
                :placeholder="$t('agentscope.knowledge.docContent')"
              />
            </ElFormItem>
            <ElButton type="primary" :loading="addingDoc" @click="addDocument">
              {{ $t('agentscope.knowledge.addDoc') }}
            </ElButton>
          </ElForm>
          <ElTable :data="documents" style="margin-top: 16px" stripe>
            <ElTableColumn :label="$t('agentscope.common.name')" prop="name" />
            <ElTableColumn :label="$t('agentscope.common.status')" width="100">
              <template #default="{ row }">
                <ElTag :type="row.status === 'indexed' ? 'success' : 'warning'">
                  {{ row.status }}
                </ElTag>
              </template>
            </ElTableColumn>
            <ElTableColumn
              :label="$t('agentscope.knowledge.chunks')"
              prop="chunk_count"
              width="70"
            />
            <ElTableColumn
              :label="$t('agentscope.knowledge.triple_count')"
              prop="triple_count"
              width="80"
            />
            <ElTableColumn :label="$t('agentscope.common.actions')" width="140">
              <template #default="{ row }">
                <ElButton link type="primary" @click="reindex(row)">
                  {{ $t('agentscope.knowledge.reindex') }}
                </ElButton>
                <ElButton link type="danger" @click="removeDoc(row)">
                  {{ $t('agentscope.common.delete') }}
                </ElButton>
              </template>
            </ElTableColumn>
          </ElTable>
        </ElTabPane>

        <!-- Method + Pipeline orchestration -->
        <ElTabPane :label="$t('agentscope.knowledge.pipeline')" name="pipeline">
          <p style="margin-top: 0; color: var(--el-text-color-secondary)">
            {{ $t('agentscope.knowledge.createMethodHint') }}
          </p>

          <!-- visual orchestration of the current pipeline -->
          <div class="pipeline-chain" style="margin: 16px 0">
            <template v-for="(st, i) in current?.pipeline ?? []" :key="st.type">
              <div class="pipeline-node">
                <IconifyIcon
                  :icon="STAGE_ICON[st.type] ?? 'lucide:circle'"
                  class="pipeline-node__icon"
                />
                <span>{{ st.name }}</span>
              </div>
              <IconifyIcon
                v-if="i < (current?.pipeline?.length ?? 0) - 1"
                icon="lucide:chevron-right"
                class="pipeline-arrow"
              />
            </template>
          </div>

          <ElForm label-width="120px">
            <ElFormItem :label="$t('agentscope.knowledge.chunkStrategy')">
              <ElSelect
                v-model="editMethod.chunk_strategy"
                style="width: 240px"
              >
                <ElOption
                  v-for="s in chunkStrategies"
                  :key="s.value"
                  :label="$t(`agentscope.knowledge.${s.label}`)"
                  :value="s.value"
                />
              </ElSelect>
            </ElFormItem>
            <ElFormItem :label="$t('agentscope.knowledge.indexMethod')">
              <ElSelect v-model="editMethod.index_method" style="width: 240px">
                <ElOption
                  v-for="m in indexMethods"
                  :key="m.value"
                  :label="$t(`agentscope.knowledge.${m.label}`)"
                  :value="m.value"
                />
              </ElSelect>
            </ElFormItem>
            <template v-if="needsKg(editMethod.index_method)">
              <ElFormItem :label="$t('agentscope.knowledge.kgCredential')">
                <ElSelect
                  v-model="editMethod.kg_credential_id"
                  style="width: 240px"
                  @change="onEditCredentialChange"
                >
                  <ElOption
                    v-for="c in credentials"
                    :key="c.id"
                    :label="`${c.data?.name || c.id} · ${c.data?.type}`"
                    :value="c.id"
                  />
                </ElSelect>
              </ElFormItem>
              <ElFormItem :label="$t('agentscope.knowledge.kgModel')">
                <ElSelect
                  v-model="editMethod.kg_model"
                  allow-create
                  filterable
                  style="width: 240px"
                >
                  <ElOption
                    v-for="m in editKgModels"
                    :key="m.name"
                    :label="m.name"
                    :value="m.name"
                  />
                </ElSelect>
              </ElFormItem>
            </template>
            <ElFormItem :label="$t('agentscope.knowledge.chunkSize')">
              <ElInputNumber
                v-model="splitConfig.chunk_size"
                :min="50"
                :max="2000"
              />
            </ElFormItem>
            <ElFormItem :label="$t('agentscope.knowledge.chunkOverlap')">
              <ElInputNumber
                v-model="splitConfig.chunk_overlap"
                :min="0"
                :max="500"
              />
            </ElFormItem>
            <ElButton type="primary" :loading="reindexing" @click="applyMethod">
              {{
                reindexing
                  ? $t('agentscope.knowledge.reindexing')
                  : $t('agentscope.knowledge.applyAndReindex')
              }}
            </ElButton>
          </ElForm>
        </ElTabPane>

        <!-- Triples (knowledge-graph) -->
        <ElTabPane :label="$t('agentscope.knowledge.triples')" name="triples">
          <ElTable :data="triples" stripe>
            <ElTableColumn
              :label="$t('agentscope.knowledge.subject')"
              prop="subject"
            />
            <ElTableColumn
              :label="$t('agentscope.knowledge.predicate')"
              prop="predicate"
            />
            <ElTableColumn
              :label="$t('agentscope.knowledge.object')"
              prop="object"
            />
            <template #empty>
              <ElEmpty :description="$t('agentscope.knowledge.noTriples')" />
            </template>
          </ElTable>
        </ElTabPane>

        <!-- Retrieval test -->
        <ElTabPane :label="$t('agentscope.knowledge.retrieve')" name="retrieve">
          <div style="display: flex; gap: 8px; align-items: center">
            <ElSelect
              v-model="retrieveMethod"
              style="width: 180px"
              :placeholder="$t('agentscope.knowledge.methodOverride')"
            >
              <ElOption
                :label="$t('agentscope.knowledge.useKbDefault')"
                value=""
              />
              <ElOption
                v-for="m in indexMethods"
                :key="m.value"
                :label="$t(`agentscope.knowledge.${m.label}`)"
                :value="m.value"
              />
            </ElSelect>
            <ElInput
              v-model="queryText"
              :placeholder="$t('agentscope.knowledge.queryPlaceholder')"
              @keyup.enter="runRetrieve"
            />
            <ElButton type="primary" :loading="retrieving" @click="runRetrieve">
              {{ $t('agentscope.knowledge.search') }}
            </ElButton>
          </div>
          <div style="margin-top: 16px">
            <ElCard
              v-for="hit in hits"
              :key="hit.id"
              shadow="never"
              style="margin-bottom: 10px"
            >
              <div
                style="
                  display: flex;
                  gap: 6px;
                  align-items: center;
                  margin-bottom: 6px;
                "
              >
                <ElTag type="success" size="small">
                  score {{ hit.score.toFixed(4) }}
                </ElTag>
                <ElTag size="small" type="info">#{{ hit.seq }}</ElTag>
              </div>
              <div style="font-size: 13px; white-space: pre-wrap">
                {{ hit.content }}
              </div>

              <div
                v-if="hit.context"
                style="
                  padding: 8px;
                  margin-top: 8px;
                  background: var(--el-fill-color-light);
                  border-radius: 6px;
                "
              >
                <div
                  style="
                    margin-bottom: 4px;
                    font-size: 12px;
                    color: var(--el-text-color-secondary);
                  "
                >
                  {{ $t('agentscope.knowledge.parentContext') }}
                </div>
                <div style="font-size: 12px; white-space: pre-wrap">
                  {{ hit.context }}
                </div>
              </div>

              <div
                v-if="hit.triples && hit.triples.length > 0"
                style="
                  display: flex;
                  flex-wrap: wrap;
                  gap: 6px;
                  margin-top: 8px;
                "
              >
                <ElTag
                  v-for="(t, ti) in hit.triples"
                  :key="ti"
                  size="small"
                  type="warning"
                >
                  {{ t.subject }} · {{ t.predicate }} · {{ t.object }}
                </ElTag>
              </div>
            </ElCard>
            <ElEmpty
              v-if="hits.length === 0"
              :description="$t('agentscope.knowledge.noHits')"
            />
          </div>
        </ElTabPane>
      </ElTabs>
    </ElDrawer>
  </Page>
</template>

<style scoped>
.pipeline-chain {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.pipeline-node {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  padding: 6px 12px;
  font-size: 13px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
}

.pipeline-node__icon {
  font-size: 16px;
  color: var(--el-color-primary);
}

.pipeline-arrow {
  font-size: 16px;
  color: var(--el-text-color-secondary);
}
</style>
