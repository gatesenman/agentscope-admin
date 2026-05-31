<script lang="ts" setup>
import type {
  KnowledgeBase,
  KnowledgeBaseListItem,
  KnowledgeDocument,
  RetrievedChunk,
} from '#/api/agentscope/knowledge';

import { computed, onMounted, reactive, ref, toRaw } from 'vue';

import { Page } from '@vben/common-ui';

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
  ElPopconfirm,
  ElTable,
  ElTableColumn,
  ElTabPane,
  ElTabs,
  ElTag,
} from 'element-plus';

import { knowledgeApi } from '#/api/agentscope';
import { $t } from '#/locales';

const loading = ref(false);
const items = ref<KnowledgeBaseListItem[]>([]);

const createDialog = ref(false);
const saving = ref(false);
const form = reactive({ name: '', description: '', icon: '📚' });

const drawer = ref(false);
const activeTab = ref('docs');
const current = ref<KnowledgeBase | null>(null);
const documents = ref<KnowledgeDocument[]>([]);
const docForm = reactive({ name: '', content: '' });
const addingDoc = ref(false);

// Retrieval test state.
const queryText = ref('');
const retrieving = ref(false);
const hits = ref<RetrievedChunk[]>([]);

// Pipeline config (split stage) bound for editing.
const splitConfig = reactive({ chunk_size: 500, chunk_overlap: 50 });
const savingPipeline = ref(false);

const splitStageIndex = computed(() =>
  (current.value?.pipeline ?? []).findIndex((s) => s.type === 'split'),
);

async function load() {
  loading.value = true;
  try {
    const res = await knowledgeApi.listKnowledgeBases();
    items.value = res.items ?? [];
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  form.name = '';
  form.description = '';
  form.icon = '📚';
  createDialog.value = true;
}

async function create() {
  if (!form.name) {
    ElMessage.warning($t('agentscope.common.name'));
    return;
  }
  saving.value = true;
  try {
    await knowledgeApi.createKnowledgeBase({ ...form });
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
  const split = kb.pipeline.find((s) => s.type === 'split');
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

async function savePipeline() {
  if (!current.value || splitStageIndex.value < 0) return;
  const pipeline = structuredClone(toRaw(current.value.pipeline));
  const splitStage = pipeline[splitStageIndex.value];
  if (!splitStage) return;
  splitStage.config.chunk_size = splitConfig.chunk_size;
  splitStage.config.chunk_overlap = splitConfig.chunk_overlap;
  savingPipeline.value = true;
  try {
    const updated = await knowledgeApi.updateKnowledgeBase(current.value.id, {
      pipeline,
    });
    current.value = updated;
    ElMessage.success($t('agentscope.knowledge.pipelineSaved'));
  } finally {
    savingPipeline.value = false;
  }
}

async function runRetrieve() {
  if (!current.value || !queryText.value) return;
  retrieving.value = true;
  try {
    const res = await knowledgeApi.retrieve(current.value.id, queryText.value);
    hits.value = res.items ?? [];
  } finally {
    retrieving.value = false;
  }
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
        <ElTableColumn :label="$t('agentscope.common.name')" min-width="200">
          <template #default="{ row }">
            <span style="margin-right: 6px">{{ row.kb.icon }}</span>
            <strong>{{ row.kb.name }}</strong>
            <div style="font-size: 12px; color: var(--el-text-color-secondary)">
              {{ row.kb.description }}
            </div>
          </template>
        </ElTableColumn>
        <ElTableColumn :label="$t('agentscope.knowledge.docs')" width="100">
          <template #default="{ row }">
            <ElTag type="info">{{ row.doc_count }}</ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn :label="$t('agentscope.knowledge.chunks')" width="100">
          <template #default="{ row }">
            <ElTag>{{ row.chunk_count }}</ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn label="Top-K" width="90" prop="kb.top_k" />
        <ElTableColumn :label="$t('agentscope.common.actions')" width="200">
          <template #default="{ row }">
            <ElButton link type="primary" @click="openManage(row.kb)">
              {{ $t('agentscope.knowledge.manage') }}
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
      width="480px"
    >
      <ElForm label-width="80px">
        <ElFormItem :label="$t('agentscope.knowledge.icon')">
          <ElInput v-model="form.icon" style="width: 80px" />
        </ElFormItem>
        <ElFormItem :label="$t('agentscope.common.name')">
          <ElInput v-model="form.name" />
        </ElFormItem>
        <ElFormItem :label="$t('agentscope.common.description')">
          <ElInput v-model="form.description" type="textarea" :rows="2" />
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
      size="640px"
      destroy-on-close
    >
      <ElTabs v-model="activeTab">
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

        <!-- Pipeline -->
        <ElTabPane :label="$t('agentscope.knowledge.pipeline')" name="pipeline">
          <p style="color: var(--el-text-color-secondary)">
            {{ $t('agentscope.knowledge.pipelineHint') }}
          </p>
          <div style="display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0">
            <ElTag
              v-for="stage in current?.pipeline ?? []"
              :key="stage.type"
              size="large"
            >
              {{ stage.name }}
            </ElTag>
          </div>
          <ElForm label-width="120px">
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
            <ElButton
              type="primary"
              :loading="savingPipeline"
              @click="savePipeline"
            >
              {{ $t('agentscope.knowledge.savePipeline') }}
            </ElButton>
            <span
              style="
                margin-left: 12px;
                font-size: 12px;
                color: var(--el-text-color-secondary);
              "
            >
              {{ $t('agentscope.knowledge.reindexHint') }}
            </span>
          </ElForm>
        </ElTabPane>

        <!-- Retrieval test -->
        <ElTabPane :label="$t('agentscope.knowledge.retrieve')" name="retrieve">
          <div style="display: flex; gap: 8px">
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
              <div style="margin-bottom: 6px">
                <ElTag type="success" size="small">
                  score {{ hit.score }}
                </ElTag>
              </div>
              <div style="font-size: 13px; white-space: pre-wrap">
                {{ hit.content }}
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
