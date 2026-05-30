<script lang="ts" setup>
import type {
  CredentialRecord,
  CredentialSchema,
  JsonSchema,
} from '#/api/agentscope';

import { computed, onMounted, reactive, ref } from 'vue';

import { Page } from '@vben/common-ui';

import {
  ElButton,
  ElCard,
  ElDialog,
  ElForm,
  ElFormItem,
  ElMessage,
  ElOption,
  ElPopconfirm,
  ElSelect,
  ElTable,
  ElTableColumn,
} from 'element-plus';

import { credentialApi } from '#/api/agentscope';
import SchemaForm from '#/components/agentscope/SchemaForm.vue';
import { $t } from '#/locales';

const loading = ref(false);
const credentials = ref<CredentialRecord[]>([]);
const schemas = ref<CredentialSchema[]>([]);

const dialog = ref(false);
const saving = ref(false);
const selectedType = ref('');
const form = reactive<Record<string, any>>({});

const selectedSchema = computed(() =>
  schemas.value.find((s) => typeConst(s) === selectedType.value),
);

/** Schema with `id` and `type` stripped, for form rendering. */
const formSchema = computed<JsonSchema>(() => {
  const s = selectedSchema.value;
  if (!s) return { properties: {} };
  const properties: Record<string, JsonSchema> = {};
  for (const [k, v] of Object.entries(s.properties ?? {})) {
    if (k !== 'id' && k !== 'type') properties[k] = v as JsonSchema;
  }
  return { properties, required: s.required };
});

function typeConst(s: CredentialSchema): string {
  const t = (s.properties?.type ?? {}) as JsonSchema;
  return t.const ?? t.default ?? '';
}

async function load() {
  loading.value = true;
  try {
    const [credRes, schemaRes] = await Promise.all([
      credentialApi.listCredentials(),
      credentialApi.listCredentialSchemas(),
    ]);
    credentials.value = credRes.credentials ?? [];
    schemas.value = schemaRes.schemas ?? [];
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  selectedType.value = schemas.value[0] ? typeConst(schemas.value[0]) : '';
  Object.keys(form).forEach((k) => delete form[k]);
  dialog.value = true;
}

async function save() {
  if (!selectedType.value) return;
  saving.value = true;
  try {
    await credentialApi.createCredential({
      type: selectedType.value,
      ...form,
    });
    ElMessage.success($t('agentscope.common.create'));
    dialog.value = false;
    await load();
  } finally {
    saving.value = false;
  }
}

async function remove(row: CredentialRecord) {
  await credentialApi.deleteCredential(row.id);
  await load();
}

function providerLabel(row: CredentialRecord) {
  const t = row.data?.type ?? '';
  return schemas.value.find((s) => typeConst(s) === t)?.title ?? t;
}

onMounted(load);
</script>

<template>
  <Page :title="$t('agentscope.menu.credentials')">
    <template #extra>
      <ElButton type="primary" @click="openCreate">
        {{ $t('agentscope.credential.newCredential') }}
      </ElButton>
    </template>

    <ElCard shadow="never">
      <ElTable v-loading="loading" :data="credentials" stripe>
        <ElTableColumn :label="$t('agentscope.common.name')">
          <template #default="{ row }">
            {{ row.data?.name || row.id }}
          </template>
        </ElTableColumn>
        <ElTableColumn :label="$t('agentscope.credential.provider')">
          <template #default="{ row }">{{ providerLabel(row) }}</template>
        </ElTableColumn>
        <ElTableColumn
          :label="$t('agentscope.common.updatedAt')"
          prop="updated_at"
          width="200"
        />
        <ElTableColumn :label="$t('agentscope.common.actions')" width="100">
          <template #default="{ row }">
            <ElPopconfirm
              :title="$t('agentscope.common.deleteConfirm')"
              @confirm="remove(row)"
            >
              <template #reference>
                <ElButton link type="danger">
                  {{ $t('agentscope.common.delete') }}
                </ElButton>
              </template>
            </ElPopconfirm>
          </template>
        </ElTableColumn>
      </ElTable>
    </ElCard>

    <ElDialog
      v-model="dialog"
      :title="$t('agentscope.credential.newCredential')"
      width="520px"
    >
      <ElForm label-position="top">
        <ElFormItem :label="$t('agentscope.credential.provider')">
          <ElSelect v-model="selectedType" class="w-full">
            <ElOption
              v-for="s in schemas"
              :key="typeConst(s)"
              :label="s.title"
              :value="typeConst(s)"
            />
          </ElSelect>
        </ElFormItem>
        <SchemaForm v-model="form" :schema="formSchema" />
      </ElForm>
      <template #footer>
        <ElButton @click="dialog = false">
          {{ $t('agentscope.common.cancel') }}
        </ElButton>
        <ElButton :loading="saving" type="primary" @click="save">
          {{ $t('agentscope.common.save') }}
        </ElButton>
      </template>
    </ElDialog>
  </Page>
</template>
