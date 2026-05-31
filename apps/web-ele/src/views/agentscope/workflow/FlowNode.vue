<script lang="ts" setup>
import { computed } from 'vue';

import { Handle, Position } from '@vue-flow/core';

const props = defineProps<{
  data: Record<string, any>;
  id: string;
  selected?: boolean;
  type: string;
}>();

const META: Record<string, { color: string; icon: string; label: string }> = {
  start: { color: '#10b981', icon: '🚀', label: '开始' },
  llm: { color: '#6366f1', icon: '🤖', label: 'LLM' },
  agent: { color: '#8b5cf6', icon: '🧠', label: '智能体' },
  knowledge: { color: '#0ea5e9', icon: '📚', label: '知识检索' },
  condition: { color: '#f59e0b', icon: '🔀', label: '条件分支' },
  template: { color: '#64748b', icon: '📝', label: '模板' },
  answer: { color: '#ef4444', icon: '💬', label: '回复' },
  end: { color: '#ef4444', icon: '🏁', label: '结束' },
};

const FALLBACK = { color: '#64748b', icon: '📦', label: '节点' };
const meta = computed(() => META[props.type] ?? FALLBACK);
const isStart = computed(() => props.type === 'start');
const isEnd = computed(() => props.type === 'answer' || props.type === 'end');
const isCondition = computed(() => props.type === 'condition');
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
        <span class="flow-node__icon">{{ data.icon || meta.icon }}</span>
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
