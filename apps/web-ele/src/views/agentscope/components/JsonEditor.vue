<script setup lang="ts">
import { computed, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { ElButton } from 'element-plus';

import CodeEditor from './CodeEditor.vue';

const props = withDefaults(
  defineProps<{
    minHeight?: number;
    modelValue?: string;
  }>(),
  { minHeight: 140, modelValue: '' },
);

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void;
}>();

const inner = computed({
  get: () => props.modelValue ?? '',
  set: (v: string) => emit('update:modelValue', v),
});

const error = ref('');

function validate(val: string) {
  if (!val || val.trim() === '') {
    error.value = '';
    return;
  }
  try {
    JSON.parse(val);
    error.value = '';
  } catch (error_: any) {
    error.value = error_?.message ?? 'JSON 格式错误';
  }
}

watch(() => props.modelValue, validate, { immediate: true });

function format() {
  try {
    inner.value = JSON.stringify(JSON.parse(inner.value || '{}'), null, 2);
    error.value = '';
  } catch (error_: any) {
    error.value = error_?.message ?? 'JSON 格式错误';
  }
}
</script>

<template>
  <div class="json-editor">
    <div class="json-editor__toolbar">
      <span
        class="json-editor__status"
        :class="{ 'is-error': error }"
        :title="error"
      >
        <IconifyIcon
          :icon="error ? 'lucide:circle-alert' : 'lucide:circle-check'"
        />
        {{ error ? 'JSON 无效' : 'JSON 有效' }}
      </span>
      <ElButton size="small" text @click="format">
        <IconifyIcon icon="lucide:wand-sparkles" />
        格式化
      </ElButton>
    </div>
    <CodeEditor v-model="inner" language="json" :min-height="minHeight" />
  </div>
</template>

<style scoped>
.json-editor__toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: flex-end;
  margin-bottom: 4px;
}

.json-editor__status {
  display: flex;
  gap: 3px;
  align-items: center;
  margin-right: auto;
  font-size: 12px;
  color: var(--el-color-success);
}

.json-editor__status.is-error {
  color: var(--el-color-danger);
}
</style>
