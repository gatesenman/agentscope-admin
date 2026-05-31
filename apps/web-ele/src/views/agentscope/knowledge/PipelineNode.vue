<script lang="ts" setup>
import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Handle, Position } from '@vue-flow/core';

const props = defineProps<{
  data: any;
  id: string;
  selected?: boolean;
  type: string;
}>();

// Dify Knowledge Pipeline stage catalogue with lucide icons.
const META: Record<string, { color: string; icon: string; label: string }> = {
  datasource: {
    color: '#0ea5e9',
    icon: 'lucide:folder-input',
    label: '数据源',
  },
  extract: { color: '#0ea5e9', icon: 'lucide:file-text', label: '文档提取' },
  clean: { color: '#f59e0b', icon: 'lucide:eraser', label: '文本清洗' },
  split: { color: '#84cc16', icon: 'lucide:scissors', label: '通用分块' },
  split_parent_child: {
    color: '#84cc16',
    icon: 'lucide:list-tree',
    label: '父子分块',
  },
  qa: { color: '#84cc16', icon: 'lucide:messages-square', label: 'QA 分块' },
  embed: { color: '#6366f1', icon: 'lucide:binary', label: '向量嵌入' },
  build_graph: {
    color: '#0d9488',
    icon: 'lucide:share-2',
    label: '知识图谱',
  },
  index: { color: '#10b981', icon: 'lucide:database', label: '建立索引' },
};

const FALLBACK = { color: '#64748b', icon: 'lucide:box', label: '节点' };
const meta = computed(() => META[props.type] ?? FALLBACK);
const isFirst = computed(() => props.type === 'datasource');
const isLast = computed(() => props.type === 'index');
</script>

<template>
  <div
    class="pl-node"
    :class="{ selected }"
    :style="{ borderColor: selected ? meta.color : 'transparent' }"
  >
    <Handle v-if="!isFirst" type="target" :position="Position.Left" />
    <div class="pl-node__bar" :style="{ background: meta.color }"></div>
    <div class="pl-node__body">
      <div class="pl-node__title">
        <IconifyIcon
          class="pl-node__icon"
          :icon="meta.icon"
          :style="{ color: meta.color }"
        />
        <span>{{ data.name || meta.label }}</span>
      </div>
      <div class="pl-node__type">{{ meta.label }}</div>
    </div>
    <Handle v-if="!isLast" type="source" :position="Position.Right" />
  </div>
</template>

<style scoped>
.pl-node {
  position: relative;
  display: flex;
  width: 168px;
  overflow: hidden;
  background: var(--el-bg-color);
  border: 2px solid transparent;
  border-radius: 10px;
  box-shadow: 0 1px 4px rgb(0 0 0 / 12%);
}

.pl-node.selected {
  box-shadow: 0 2px 10px rgb(0 0 0 / 20%);
}

.pl-node__bar {
  width: 4px;
}

.pl-node__body {
  flex: 1;
  padding: 8px 10px;
}

.pl-node__title {
  display: flex;
  gap: 6px;
  align-items: center;
  font-size: 13px;
  font-weight: 600;
}

.pl-node__icon {
  font-size: 16px;
}

.pl-node__type {
  margin-top: 2px;
  font-size: 11px;
  color: var(--el-text-color-secondary);
}
</style>
