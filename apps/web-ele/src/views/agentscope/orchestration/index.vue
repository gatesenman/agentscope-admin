<script lang="ts" setup>
import type {
  Orchestration,
  OrchestrationMember,
  OrchestrationRunEvent,
} from '#/api/agentscope/orchestration';
import type { CredentialRecord, ModelCard } from '#/api/agentscope/types';

import { computed, onMounted, reactive, ref, toRaw } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  ElButton,
  ElCard,
  ElEmpty,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElMessage,
  ElOption,
  ElPopconfirm,
  ElScrollbar,
  ElSelect,
  ElTag,
} from 'element-plus';

import { credentialApi, modelApi, orchestrationApi } from '#/api/agentscope';

// Pattern catalogue with lucide icons + one-line descriptions (no emoji).
interface PatternMeta {
  desc: string;
  icon: string;
  label: string;
  value: string;
}
const DEFAULT_PATTERN: PatternMeta = {
  value: 'sequential',
  label: '顺序流水线',
  icon: 'lucide:list-ordered',
  desc: '成员依次执行，后者在前者输出基础上精炼。',
};
const PATTERNS: PatternMeta[] = [
  DEFAULT_PATTERN,
  {
    value: 'parallel',
    label: '并行执行',
    icon: 'lucide:columns-3',
    desc: '所有成员同时处理同一任务，输出汇总展示。',
  },
  {
    value: 'aggregation',
    label: '并行聚合',
    icon: 'lucide:combine',
    desc: '并行扇出后，由聚合器 LLM 综合成一个最终答案。',
  },
  {
    value: 'router',
    label: '路由分发',
    icon: 'lucide:split',
    desc: '由路由器 LLM 选择最合适的单个成员处理任务。',
  },
  {
    value: 'supervisor',
    label: '主管-工人',
    icon: 'lucide:users',
    desc: '主管 LLM 多轮委派下属，直至给出最终答案。',
  },
  {
    value: 'handoff',
    label: '交接 (Swarm)',
    icon: 'lucide:arrow-left-right',
    desc: '成员之间互相交接控制权，直到任务完成。',
  },
];

const ROLE_OPTIONS = [
  'researcher',
  'writer',
  'analyst',
  'planner',
  'reviewer',
  'coder',
  'critic',
  'worker',
];

function patternMeta(value: string) {
  return PATTERNS.find((p) => p.value === value) ?? DEFAULT_PATTERN;
}

function usesCoordinator(pattern: string): boolean {
  return ['aggregation', 'router', 'supervisor'].includes(pattern);
}

const list = ref<Orchestration[]>([]);
const current = ref<null | Orchestration>(null);
const credentials = ref<CredentialRecord[]>([]);
const modelsByType = reactive<Record<string, ModelCard[]>>({});
const saving = ref(false);

// run state
const query = ref('');
const running = ref(false);
const transcript = ref<
  { role: string; running: boolean; speaker: string; text: string }[]
>([]);
const finalOutput = ref('');

function credentialType(id: string): string {
  return credentials.value.find((c) => c.id === id)?.data?.type ?? '';
}

function modelsForCredential(id: string): ModelCard[] {
  return modelsByType[credentialType(id)] ?? [];
}

async function loadModelsForType(type: string) {
  if (!type || modelsByType[type]) return;
  try {
    const res = await modelApi.listModels(type);
    modelsByType[type] = res.models ?? [];
  } catch {
    modelsByType[type] = [];
  }
}

async function load() {
  const [orch, cr] = await Promise.all([
    orchestrationApi.listOrchestrations(),
    credentialApi.listCredentials(),
  ]);
  list.value = orch.items ?? [];
  credentials.value = cr.credentials ?? [];
  await Promise.all(
    [...new Set(credentials.value.map((c) => c.data?.type))]
      .filter(Boolean)
      .map((t) => loadModelsForType(t as string)),
  );
  const first = list.value[0];
  if (first && !current.value) select(first);
}

function select(orch: Orchestration) {
  current.value = structuredClone(toRaw(orch));
  transcript.value = [];
  finalOutput.value = '';
}

const defaultCredentialId = computed(() => credentials.value[0]?.id ?? '');

function blankMember(idx: number): OrchestrationMember {
  const cid = defaultCredentialId.value;
  const ms = modelsForCredential(cid);
  return {
    id: `m${Date.now()}${idx}`,
    name: `成员 ${idx}`,
    role: 'worker',
    instruction: '',
    credential_id: cid,
    type: credentialType(cid),
    model: ms[0]?.name ?? '',
    parameters: {},
  };
}

async function createNew() {
  const cid = defaultCredentialId.value;
  const model = modelsForCredential(cid)[0]?.name ?? '';
  const coordinator = {
    credential_id: cid,
    type: credentialType(cid),
    model,
    parameters: {},
    instruction: '',
  };
  const created = await orchestrationApi.createOrchestration({
    name: '新建编排',
    pattern: 'sequential',
    config: {
      members: [
        {
          id: 'm1',
          name: '研究员',
          role: 'researcher',
          instruction: '针对用户问题进行分析，给出关键事实与要点。',
          credential_id: cid,
          type: credentialType(cid),
          model,
          parameters: {},
        },
        {
          id: 'm2',
          name: '撰写者',
          role: 'writer',
          instruction: '基于上一步的要点，撰写清晰、专业的最终回答。',
          credential_id: cid,
          type: credentialType(cid),
          model,
          parameters: {},
        },
      ],
      coordinator,
      max_rounds: 4,
    },
  });
  list.value.unshift(created);
  select(created);
}

function addMember() {
  if (!current.value) return;
  current.value.config.members.push(
    blankMember(current.value.config.members.length + 1),
  );
}

function removeMember(idx: number) {
  current.value?.config.members.splice(idx, 1);
}

function onMemberCredentialChange(member: OrchestrationMember) {
  member.type = credentialType(member.credential_id);
  void loadModelsForType(member.type);
  member.model = modelsForCredential(member.credential_id)[0]?.name ?? '';
}

function onCoordinatorCredentialChange() {
  if (!current.value) return;
  const co = current.value.config.coordinator;
  co.type = credentialType(co.credential_id);
  void loadModelsForType(co.type);
  co.model = modelsForCredential(co.credential_id)[0]?.name ?? '';
}

async function save() {
  if (!current.value) return;
  saving.value = true;
  try {
    const updated = await orchestrationApi.updateOrchestration(
      current.value.id,
      {
        name: current.value.name,
        description: current.value.description,
        pattern: current.value.pattern,
        config: current.value.config,
      },
    );
    const i = list.value.findIndex((o) => o.id === updated.id);
    if (i !== -1) list.value[i] = updated;
    ElMessage.success('已保存');
  } finally {
    saving.value = false;
  }
}

async function remove(orch: Orchestration) {
  await orchestrationApi.deleteOrchestration(orch.id);
  list.value = list.value.filter((o) => o.id !== orch.id);
  if (current.value?.id === orch.id) current.value = null;
}

function onEvent(event: OrchestrationRunEvent) {
  switch (event.type) {
    case 'error': {
      ElMessage.error(event.message ?? '运行失败');
      break;
    }
    case 'finished': {
      finalOutput.value = event.output ?? '';
      break;
    }
    case 'member_finished': {
      const entry = transcript.value
        .toReversed()
        .find((t) => t.speaker === event.member && t.running);
      if (entry) {
        entry.text = event.text ?? '';
        entry.running = false;
      }
      break;
    }
    case 'member_started': {
      transcript.value.push({
        speaker: event.member ?? '',
        role: event.role ?? '',
        text: '',
        running: true,
      });
      break;
    }
    // no default
  }
}

async function run() {
  if (!current.value || !query.value.trim()) {
    ElMessage.warning('请先输入运行内容');
    return;
  }
  await save();
  running.value = true;
  transcript.value = [];
  finalOutput.value = '';
  try {
    await orchestrationApi.runOrchestration({
      id: current.value.id,
      query: query.value.trim(),
      onEvent,
    });
  } catch (error: any) {
    ElMessage.error(error?.message ?? '运行失败');
  } finally {
    running.value = false;
    transcript.value.forEach((t) => (t.running = false));
  }
}

onMounted(load);
</script>

<template>
  <Page title="多智能体编排">
    <div class="orch">
      <!-- left: orchestration list -->
      <ElCard class="orch__list" shadow="never">
        <template #header>
          <div class="orch__list-head">
            <span>编排列表</span>
            <ElButton type="primary" size="small" @click="createNew">
              <IconifyIcon icon="lucide:plus" />
              新建
            </ElButton>
          </div>
        </template>
        <ElScrollbar>
          <div
            v-for="o in list"
            :key="o.id"
            class="orch__item"
            :class="{ active: current?.id === o.id }"
            @click="select(o)"
          >
            <IconifyIcon
              class="orch__item-icon"
              :icon="patternMeta(o.pattern).icon"
            />
            <div class="orch__item-body">
              <div class="orch__item-name">{{ o.name || '未命名' }}</div>
              <ElTag size="small" type="info">
                {{ patternMeta(o.pattern).label }}
              </ElTag>
            </div>
            <ElPopconfirm title="确认删除该编排？" @confirm="remove(o)">
              <template #reference>
                <ElButton link type="danger" @click.stop>
                  <IconifyIcon icon="lucide:trash-2" />
                </ElButton>
              </template>
            </ElPopconfirm>
          </div>
          <ElEmpty v-if="list.length === 0" description="还没有编排" />
        </ElScrollbar>
      </ElCard>

      <!-- middle: config -->
      <ElCard v-if="current" class="orch__config" shadow="never">
        <ElScrollbar>
          <div class="orch__config-inner">
            <ElForm label-position="top">
              <ElFormItem label="名称">
                <ElInput v-model="current.name" />
              </ElFormItem>
              <ElFormItem label="协作模式">
                <ElSelect v-model="current.pattern" style="width: 100%">
                  <ElOption
                    v-for="p in PATTERNS"
                    :key="p.value"
                    :label="p.label"
                    :value="p.value"
                  >
                    <span>{{ p.label }}</span>
                    <span class="orch__opt-desc">{{ p.desc }}</span>
                  </ElOption>
                </ElSelect>
              </ElFormItem>
              <p class="orch__hint">
                <IconifyIcon :icon="patternMeta(current.pattern).icon" />
                {{ patternMeta(current.pattern).desc }}
              </p>

              <!-- coordinator (router / supervisor / aggregation) -->
              <template v-if="usesCoordinator(current.pattern)">
                <h4 class="orch__section">
                  协调器
                  <span class="orch__section-sub">
                    （{{
                      current.pattern === 'router'
                        ? '路由器'
                        : current.pattern === 'supervisor'
                          ? '主管'
                          : '聚合器'
                    }}）
                  </span>
                </h4>
                <div class="orch__row">
                  <ElSelect
                    v-model="current.config.coordinator.credential_id"
                    placeholder="凭证"
                    style="flex: 1"
                    @change="onCoordinatorCredentialChange"
                  >
                    <ElOption
                      v-for="c in credentials"
                      :key="c.id"
                      :label="c.data?.name || c.id"
                      :value="c.id"
                    />
                  </ElSelect>
                  <ElSelect
                    v-model="current.config.coordinator.model"
                    placeholder="模型"
                    filterable
                    allow-create
                    default-first-option
                    style="flex: 1"
                  >
                    <ElOption
                      v-for="m in modelsForCredential(
                        current.config.coordinator.credential_id,
                      )"
                      :key="m.name"
                      :label="m.name"
                      :value="m.name"
                    />
                  </ElSelect>
                </div>
                <ElInput
                  v-model="current.config.coordinator.instruction"
                  type="textarea"
                  :rows="2"
                  placeholder="协调器指令（可选，留空使用默认）"
                  style="margin-top: 8px"
                />
                <ElFormItem
                  v-if="current.pattern === 'supervisor'"
                  label="最大轮数"
                  style="margin-top: 8px"
                >
                  <ElInputNumber
                    v-model="current.config.max_rounds"
                    :min="1"
                    :max="12"
                  />
                </ElFormItem>
              </template>

              <ElFormItem
                v-else-if="current.pattern === 'handoff'"
                label="最大交接轮数"
              >
                <ElInputNumber
                  v-model="current.config.max_rounds"
                  :min="1"
                  :max="12"
                />
              </ElFormItem>
            </ElForm>

            <!-- members -->
            <div class="orch__members-head">
              <h4 class="orch__section">
                成员（{{ current.config.members.length }}）
              </h4>
              <ElButton size="small" @click="addMember">
                <IconifyIcon icon="lucide:plus" />
                添加成员
              </ElButton>
            </div>

            <div
              v-for="(m, i) in current.config.members"
              :key="m.id"
              class="orch__member"
            >
              <div class="orch__member-head">
                <ElInput
                  v-model="m.name"
                  size="small"
                  placeholder="成员名称"
                  style="width: 130px"
                />
                <ElSelect
                  v-model="m.role"
                  size="small"
                  filterable
                  allow-create
                  default-first-option
                  placeholder="角色"
                  style="width: 120px"
                >
                  <ElOption
                    v-for="r in ROLE_OPTIONS"
                    :key="r"
                    :label="r"
                    :value="r"
                  />
                </ElSelect>
                <div style="flex: 1"></div>
                <ElButton link type="danger" @click="removeMember(i)">
                  <IconifyIcon icon="lucide:trash-2" />
                </ElButton>
              </div>
              <div class="orch__row" style="margin-top: 6px">
                <ElSelect
                  v-model="m.credential_id"
                  size="small"
                  placeholder="凭证"
                  style="flex: 1"
                  @change="() => onMemberCredentialChange(m)"
                >
                  <ElOption
                    v-for="c in credentials"
                    :key="c.id"
                    :label="c.data?.name || c.id"
                    :value="c.id"
                  />
                </ElSelect>
                <ElSelect
                  v-model="m.model"
                  size="small"
                  filterable
                  allow-create
                  default-first-option
                  placeholder="模型"
                  style="flex: 1"
                >
                  <ElOption
                    v-for="mc in modelsForCredential(m.credential_id)"
                    :key="mc.name"
                    :label="mc.name"
                    :value="mc.name"
                  />
                </ElSelect>
              </div>
              <ElInput
                v-model="m.instruction"
                type="textarea"
                :rows="2"
                placeholder="该成员的系统指令 / 职责描述"
                style="margin-top: 6px"
              />
            </div>

            <div class="orch__actions">
              <ElButton type="primary" :loading="saving" @click="save">
                <IconifyIcon icon="lucide:save" style="margin-right: 4px" />
                保存
              </ElButton>
            </div>
          </div>
        </ElScrollbar>
      </ElCard>
      <ElCard v-else class="orch__config" shadow="never">
        <ElEmpty description="从左侧选择或新建一个编排" />
      </ElCard>

      <!-- right: run -->
      <ElCard class="orch__run" shadow="never">
        <template #header>运行调试</template>
        <div class="orch__run-input">
          <ElInput
            v-model="query"
            type="textarea"
            :rows="3"
            placeholder="输入任务 / 问题"
          />
          <ElButton
            type="primary"
            :loading="running"
            :disabled="!current"
            style="width: 100%; margin-top: 8px"
            @click="run"
          >
            <IconifyIcon icon="lucide:play" style="margin-right: 4px" />
            运行
          </ElButton>
        </div>
        <ElScrollbar class="orch__run-log">
          <div v-for="(t, i) in transcript" :key="i" class="orch__bubble">
            <div class="orch__bubble-head">
              <IconifyIcon icon="lucide:bot" />
              <strong>{{ t.speaker }}</strong>
              <ElTag size="small" type="info">{{ t.role }}</ElTag>
              <IconifyIcon
                v-if="t.running"
                icon="lucide:loader-circle"
                class="orch__spin"
              />
            </div>
            <div v-if="t.text" class="orch__bubble-text">{{ t.text }}</div>
          </div>
          <div v-if="finalOutput" class="orch__final">
            <div class="orch__final-head">
              <IconifyIcon icon="lucide:flag" />
              最终输出
            </div>
            <div class="orch__bubble-text">{{ finalOutput }}</div>
          </div>
          <ElEmpty
            v-if="transcript.length === 0 && !finalOutput"
            description="运行后在此查看每个成员的协作过程"
          />
        </ElScrollbar>
      </ElCard>
    </div>
  </Page>
</template>

<style scoped>
.orch {
  display: flex;
  gap: 12px;
  height: calc(100vh - 140px);
}

.orch__list {
  display: flex;
  flex-shrink: 0;
  flex-direction: column;
  width: 240px;
}

.orch__list-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.orch__item {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 8px;
  cursor: pointer;
  border-radius: 8px;
}

.orch__item:hover,
.orch__item.active {
  background: var(--el-fill-color-light);
}

.orch__item-icon {
  font-size: 18px;
  color: var(--el-color-primary);
}

.orch__item-body {
  flex: 1;
  min-width: 0;
}

.orch__item-name {
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
}

.orch__config {
  flex: 1;
  min-width: 0;
}

.orch__config-inner {
  padding: 4px 12px 12px;
}

.orch__opt-desc {
  margin-left: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.orch__hint {
  display: flex;
  gap: 6px;
  align-items: center;
  padding: 8px 10px;
  margin: 0 0 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  background: var(--el-fill-color-light);
  border-radius: 8px;
}

.orch__section {
  margin: 12px 0 8px;
  font-size: 14px;
}

.orch__section-sub {
  font-size: 12px;
  font-weight: 400;
  color: var(--el-text-color-secondary);
}

.orch__row {
  display: flex;
  gap: 8px;
}

.orch__members-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.orch__member {
  padding: 10px;
  margin-bottom: 10px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
}

.orch__member-head {
  display: flex;
  gap: 8px;
  align-items: center;
}

.orch__actions {
  margin-top: 12px;
}

.orch__run {
  display: flex;
  flex-shrink: 0;
  flex-direction: column;
  width: 360px;
}

.orch__run-log {
  flex: 1;
  margin-top: 12px;
}

.orch__bubble {
  padding: 8px 10px;
  margin-bottom: 8px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
}

.orch__bubble-head {
  display: flex;
  gap: 6px;
  align-items: center;
  font-size: 13px;
}

.orch__bubble-text {
  margin-top: 4px;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
}

.orch__final {
  padding: 10px;
  margin-top: 8px;
  border: 1px solid var(--el-color-primary-light-5);
  border-radius: 8px;
}

.orch__final-head {
  display: flex;
  gap: 6px;
  align-items: center;
  font-weight: 600;
  color: var(--el-color-primary);
}

.orch__spin {
  animation: orch-spin 1s linear infinite;
}

@keyframes orch-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
