<script setup lang="ts">
import { computed, nextTick, ref } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  ElButton,
  ElEmpty,
  ElInput,
  ElPopover,
  ElScrollbar,
} from 'element-plus';

interface VarGroup {
  /** Available field names under this node, e.g. ['text', 'output']. */
  fields: string[];
  /** Source node id / title. */
  node: string;
}

const props = withDefaults(
  defineProps<{
    modelValue?: string;
    placeholder?: string;
    rows?: number;
    type?: 'text' | 'textarea';
    /** Upstream variables available for reference. */
    variables?: VarGroup[];
  }>(),
  {
    modelValue: '',
    placeholder: '',
    rows: 2,
    type: 'text',
    variables: () => [],
  },
);

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void;
}>();

const inputRef = ref<any>();
const popoverVisible = ref(false);

const inner = computed({
  get: () => props.modelValue ?? '',
  set: (v: string) => emit('update:modelValue', v),
});

const hasVars = computed(() =>
  props.variables.some((g) => g.fields.length > 0),
);

function nativeEl(): HTMLInputElement | HTMLTextAreaElement | undefined {
  const comp = inputRef.value;
  if (!comp) return undefined;
  return props.type === 'textarea' ? comp.textarea : comp.input;
}

async function insertVar(expr: string) {
  const token = `{{${expr}}}`;
  const el = nativeEl();
  const current = inner.value;
  if (el && typeof el.selectionStart === 'number') {
    const start = el.selectionStart;
    const end = el.selectionEnd ?? start;
    inner.value = current.slice(0, start) + token + current.slice(end);
    await nextTick();
    const pos = start + token.length;
    el.focus();
    el.setSelectionRange(pos, pos);
  } else {
    inner.value = current + token;
  }
  popoverVisible.value = false;
}
</script>

<template>
  <div class="var-input">
    <ElInput
      ref="inputRef"
      v-model="inner"
      :type="type"
      :rows="rows"
      :placeholder="placeholder"
    />
    <ElPopover
      v-model:visible="popoverVisible"
      :width="280"
      placement="bottom-end"
      trigger="click"
    >
      <template #reference>
        <ElButton class="var-btn" size="small" text>
          <IconifyIcon icon="lucide:braces" />
          <span>变量</span>
        </ElButton>
      </template>
      <ElScrollbar max-height="280px">
        <ElEmpty
          v-if="!hasVars"
          :image-size="48"
          description="上游暂无可引用变量"
        />
        <template v-else>
          <div
            v-for="g in variables"
            :key="g.node || 'builtin'"
            class="var-group"
          >
            <div v-if="g.fields.length > 0" class="var-group__title">
              {{ g.node || '内置变量' }}
            </div>
            <div
              v-for="f in g.fields"
              :key="`${g.node}.${f}`"
              class="var-item"
              @click="insertVar(g.node ? `${g.node}.${f}` : f)"
            >
              <IconifyIcon icon="lucide:braces" class="var-item__icon" />
              <span class="var-item__expr">{{
                g.node ? `${g.node}.${f}` : f
              }}</span>
            </div>
          </div>
        </template>
      </ElScrollbar>
    </ElPopover>
  </div>
</template>

<style scoped>
.var-input {
  position: relative;
}

.var-btn {
  position: absolute;
  top: 2px;
  right: 4px;
  z-index: 2;
  gap: 2px;
  height: 22px;
  padding: 0 6px;
  color: var(--el-color-primary);
}

.var-group__title {
  padding: 4px 8px 2px;
  font-size: 11px;
  font-weight: 600;
  color: var(--el-text-color-secondary);
}

.var-item {
  display: flex;
  gap: 6px;
  align-items: center;
  padding: 4px 8px;
  font-family: ui-monospace, monospace;
  font-size: 12px;
  cursor: pointer;
  border-radius: 4px;
}

.var-item:hover {
  background: var(--el-fill-color-light);
}

.var-item__icon {
  color: var(--el-color-primary);
}

.var-item__expr {
  color: var(--el-text-color-primary);
}
</style>
