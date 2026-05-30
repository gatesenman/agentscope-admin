<script lang="ts" setup>
import type { JsonSchema } from '#/api/agentscope';

import { computed } from 'vue';

import {
  ElCard,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElOption,
  ElSelect,
  ElSwitch,
} from 'element-plus';

interface Props {
  /** JSON schema describing the object to edit. */
  schema: JsonSchema;
  /** The reactive model object bound to this schema. */
  modelValue: Record<string, any>;
  /** Nesting depth, used to indent nested object cards. */
  depth?: number;
}

const props = withDefaults(defineProps<Props>(), { depth: 0 });
const emit = defineEmits<{ 'update:modelValue': [Record<string, any>] }>();

const model = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
});

const fields = computed(() => {
  const properties = props.schema.properties ?? {};
  const required = new Set(props.schema.required);
  return Object.entries(properties).map(([key, sub]) => ({
    key,
    sub: sub as JsonSchema,
    required: required.has(key),
  }));
});

function fieldType(sub: JsonSchema): string {
  if (sub.enum) return 'enum';
  if (sub.type === 'object' && sub.properties) return 'object';
  if (sub.type === 'boolean') return 'boolean';
  if (sub.type === 'integer' || sub.type === 'number') return 'number';
  if (sub.format === 'textarea') return 'textarea';
  if (sub.type === 'array' || sub.type === 'object') return 'json';
  return 'string';
}

function ensureObject(key: string): Record<string, any> {
  if (!model.value[key] || typeof model.value[key] !== 'object') {
    model.value[key] = {};
  }
  return model.value[key];
}

function jsonText(key: string): string {
  const val = model.value[key];
  return val === undefined ? '' : JSON.stringify(val, null, 2);
}

function setJson(key: string, text: string) {
  try {
    model.value[key] = text ? JSON.parse(text) : null;
  } catch {
    // keep previous value while the user is typing invalid JSON
  }
}
</script>

<template>
  <div :style="{ paddingLeft: depth > 0 ? '0' : '0' }">
    <template v-for="field in fields" :key="field.key">
      <!-- Nested object: render a sub-card with a recursive SchemaForm -->
      <ElCard
        v-if="fieldType(field.sub) === 'object'"
        class="mb-4"
        shadow="never"
      >
        <template #header>
          <span class="font-medium">
            {{ field.sub.title || field.key }}
          </span>
          <span
            v-if="field.sub.description"
            class="text-foreground/50 ml-2 text-xs"
          >
            {{ field.sub.description }}
          </span>
        </template>
        <SchemaForm
          :schema="field.sub"
          :model-value="ensureObject(field.key)"
          :depth="depth + 1"
        />
      </ElCard>

      <ElFormItem
        v-else
        :label="field.sub.title || field.key"
        :required="field.required"
      >
        <template v-if="field.sub.description" #label>
          <span>{{ field.sub.title || field.key }}</span>
        </template>

        <ElSelect
          v-if="fieldType(field.sub) === 'enum'"
          v-model="model[field.key]"
          class="w-full"
          clearable
        >
          <ElOption
            v-for="opt in field.sub.enum"
            :key="String(opt)"
            :label="String(opt)"
            :value="opt"
          />
        </ElSelect>

        <ElSwitch
          v-else-if="fieldType(field.sub) === 'boolean'"
          v-model="model[field.key]"
        />

        <ElInputNumber
          v-else-if="fieldType(field.sub) === 'number'"
          v-model="model[field.key]"
          :max="field.sub.maximum"
          :min="field.sub.minimum"
          class="w-full"
          controls-position="right"
        />

        <ElInput
          v-else-if="fieldType(field.sub) === 'textarea'"
          v-model="model[field.key]"
          :autosize="{ minRows: 3, maxRows: 8 }"
          type="textarea"
        />

        <ElInput
          v-else-if="fieldType(field.sub) === 'json'"
          :autosize="{ minRows: 2, maxRows: 8 }"
          :model-value="jsonText(field.key)"
          placeholder="JSON"
          type="textarea"
          @update:model-value="(v: string) => setJson(field.key, v)"
        />

        <ElInput v-else v-model="model[field.key]" clearable />
      </ElFormItem>
    </template>
  </div>
</template>
