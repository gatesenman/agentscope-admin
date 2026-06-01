<script setup lang="ts">
import { ref } from 'vue';

import { IconifyIcon } from '@vben/icons';

const props = withDefaults(
  defineProps<{
    defaultCollapsed?: boolean;
    icon?: string;
    title: string;
  }>(),
  { icon: 'lucide:settings-2', defaultCollapsed: false },
);

const open = ref(!props.defaultCollapsed);
</script>

<template>
  <div class="panel-section">
    <div class="panel-section__head" @click="open = !open">
      <IconifyIcon :icon="icon" class="panel-section__icon" />
      <span class="panel-section__title">{{ title }}</span>
      <IconifyIcon
        class="panel-section__chevron"
        :icon="open ? 'lucide:chevron-down' : 'lucide:chevron-right'"
      />
    </div>
    <div v-show="open" class="panel-section__body">
      <slot></slot>
    </div>
  </div>
</template>

<style scoped>
.panel-section {
  margin-bottom: 10px;
  overflow: hidden;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
}

.panel-section__head {
  display: flex;
  gap: 6px;
  align-items: center;
  padding: 8px 10px;
  cursor: pointer;
  user-select: none;
  background: var(--el-fill-color-light);
}

.panel-section__head:hover {
  background: var(--el-fill-color);
}

.panel-section__icon {
  color: var(--el-color-primary);
}

.panel-section__title {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.panel-section__chevron {
  margin-left: auto;
  color: var(--el-text-color-secondary);
}

.panel-section__body {
  padding: 12px 10px 4px;
}
</style>
