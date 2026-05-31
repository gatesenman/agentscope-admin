<script lang="ts" setup>
import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Handle, Position } from '@vue-flow/core';

const props = defineProps<{
  data: Record<string, any>;
  id: string;
  selected?: boolean;
  type: string;
}>();

const META: Record<string, { color: string; icon: string; label: string }> = {
  // Entry
  start: { color: '#10b981', icon: 'lucide:play', label: '开始' },
  'trigger-webhook': {
    color: '#22c55e',
    icon: 'lucide:webhook',
    label: 'Webhook 触发',
  },
  'trigger-schedule': {
    color: '#22c55e',
    icon: 'lucide:alarm-clock',
    label: '定时触发',
  },
  // AI
  llm: { color: '#6366f1', icon: 'lucide:sparkles', label: 'LLM' },
  agent: { color: '#8b5cf6', icon: 'lucide:bot', label: '智能体' },
  'question-classifier': {
    color: '#6366f1',
    icon: 'lucide:list-tree',
    label: '问题分类器',
  },
  'parameter-extractor': {
    color: '#6366f1',
    icon: 'lucide:braces',
    label: '参数提取',
  },
  // Data / Knowledge
  knowledge: { color: '#0ea5e9', icon: 'lucide:book-open', label: '知识检索' },
  'knowledge-index': {
    color: '#0ea5e9',
    icon: 'lucide:database',
    label: '知识写入',
  },
  datasource: {
    color: '#0ea5e9',
    icon: 'lucide:folder-input',
    label: '数据源',
  },
  'document-extractor': {
    color: '#0ea5e9',
    icon: 'lucide:file-text',
    label: '文档提取',
  },
  ontology: { color: '#0d9488', icon: 'lucide:share-2', label: '本体操作' },
  // Logic
  condition: { color: '#f59e0b', icon: 'lucide:git-branch', label: '条件分支' },
  code: { color: '#f97316', icon: 'lucide:code', label: '代码执行' },
  template: { color: '#64748b', icon: 'lucide:file-code', label: '模板转换' },
  'http-request': {
    color: '#0891b2',
    icon: 'lucide:globe',
    label: 'HTTP 请求',
  },
  tool: { color: '#f59e0b', icon: 'lucide:wrench', label: '工具' },
  'list-operator': {
    color: '#84cc16',
    icon: 'lucide:list-filter',
    label: '列表操作',
  },
  // Flow
  iteration: { color: '#ec4899', icon: 'lucide:repeat', label: '迭代' },
  loop: { color: '#ec4899', icon: 'lucide:rotate-cw', label: '循环' },
  'human-input': {
    color: '#eab308',
    icon: 'lucide:user-check',
    label: '人工输入',
  },
  // Variables
  'variable-aggregator': {
    color: '#14b8a6',
    icon: 'lucide:combine',
    label: '变量聚合',
  },
  assigner: { color: '#14b8a6', icon: 'lucide:variable', label: '变量赋值' },
  // Output
  answer: { color: '#ef4444', icon: 'lucide:message-square', label: '回复' },
  end: { color: '#ef4444', icon: 'lucide:flag', label: '结束' },
};

const FALLBACK = { color: '#64748b', icon: 'lucide:box', label: '节点' };
const meta = computed(() => META[props.type] ?? FALLBACK);
const isStart = computed(
  () =>
    props.type === 'start' ||
    props.type === 'trigger-webhook' ||
    props.type === 'trigger-schedule',
);
const isEnd = computed(() => props.type === 'answer' || props.type === 'end');
const isCondition = computed(() => props.type === 'condition');
const isClassifier = computed(() => props.type === 'question-classifier');
const classes = computed<{ id: string; name: string }[]>(
  () => props.data?.classes ?? [],
);
</script>

<template>
  <div
    class="flow-node"
    :class="{ selected }"
    :style="{ borderColor: selected ? meta.color : 'transparent' }"
  >
    <Handle v-if="!isStart" type="target" :position="Position.Left" />
    <div class="flow-node__bar" :style="{ background: meta.color }"></div>
    <div class="flow-node__body">
      <div class="flow-node__title">
        <IconifyIcon
          class="flow-node__icon"
          :icon="meta.icon"
          :style="{ color: meta.color }"
        />
        <span>{{ data.title || meta.label }}</span>
      </div>
      <div class="flow-node__type">{{ meta.label }}</div>
    </div>

    <!-- Condition exposes two labelled source handles. -->
    <template v-if="isCondition">
      <Handle
        id="true"
        type="source"
        :position="Position.Right"
        :style="{ top: '35%' }"
      />
      <span class="flow-node__handle-label" style="top: 28%">true</span>
      <Handle
        id="false"
        type="source"
        :position="Position.Right"
        :style="{ top: '70%' }"
      />
      <span class="flow-node__handle-label" style="top: 63%">false</span>
    </template>
    <!-- Classifier exposes one labelled source handle per class. -->
    <template v-else-if="isClassifier && classes.length > 0">
      <template v-for="(c, i) in classes" :key="c.id || i">
        <Handle
          :id="c.id"
          type="source"
          :position="Position.Right"
          :style="{ top: `${((i + 1) / (classes.length + 1)) * 100}%` }"
        />
        <span
          class="flow-node__handle-label"
          :style="{ top: `${((i + 1) / (classes.length + 1)) * 100 - 7}%` }"
        >
          {{ c.name || c.id }}
        </span>
      </template>
    </template>
    <Handle v-else-if="!isEnd" type="source" :position="Position.Right" />
  </div>
</template>

<style scoped>
.flow-node {
  position: relative;
  display: flex;
  min-width: 160px;
  overflow: hidden;
  background: var(--el-bg-color, #fff);
  border: 2px solid transparent;
  border-radius: 10px;
  box-shadow: 0 2px 10px rgb(0 0 0 / 12%);
}

.flow-node.selected {
  box-shadow: 0 4px 16px rgb(0 0 0 / 25%);
}

.flow-node__bar {
  width: 6px;
}

.flow-node__body {
  padding: 10px 14px;
}

.flow-node__title {
  display: flex;
  gap: 6px;
  align-items: center;
  font-size: 14px;
  font-weight: 600;
}

.flow-node__icon {
  font-size: 16px;
}

.flow-node__type {
  margin-top: 2px;
  font-size: 11px;
  color: var(--el-text-color-secondary, #909399);
}

.flow-node__handle-label {
  position: absolute;
  right: -34px;
  font-size: 10px;
  color: var(--el-text-color-secondary, #909399);
}
</style>
