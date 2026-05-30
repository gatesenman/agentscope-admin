<script lang="ts" setup>
import type {
  AgentRecord,
  AgentSchemaResponse,
  JsonSchema,
  ObjectType,
  Ontology,
} from '#/api/agentscope';

import { computed, onMounted, reactive, ref } from 'vue';

import { Page } from '@vben/common-ui';

import {
  ElButton,
  ElCard,
  ElDrawer,
  ElForm,
  ElFormItem,
  ElMessage,
  ElMessageBox,
  ElOption,
  ElPopconfirm,
  ElSelect,
  ElSwitch,
  ElTable,
  ElTableColumn,
  ElTabPane,
  ElTabs,
} from 'element-plus';

import { agentApi, ontologyApi } from '#/api/agentscope';
import SchemaForm from '#/components/agentscope/SchemaForm.vue';
import { $t } from '#/locales';

const loading = ref(false);
const agents = ref<AgentRecord[]>([]);
const schema = ref<AgentSchemaResponse>();
const ontologies = ref<Ontology[]>([]);

const drawerVisible = ref(false);
const saving = ref(false);
const editingId = ref<null | string>(null);
const activeTab = ref('identity');

const form = reactive<Record<string, any>>({
  name: '',
  system_prompt: '',
  context_config: {},
  react_config: {},
});

const binding = reactive({
  ontology_id: '',
  enabled: true,
  allowed_object_types: [] as string[],
  allowed_actions: [] as string[],
});
const bindingObjectTypes = ref<ObjectType[]>([]);

const identitySchema = computed<JsonSchema>(
  () => schema.value?.identity ?? { properties: {} },
);

function buildDefaults(s?: JsonSchema): Record<string, any> {
  const out: Record<string, any> = {};
  for (const [key, sub] of Object.entries(s?.properties ?? {})) {
    const node = sub as JsonSchema;
    out[key] =
      node.type === 'object' && node.properties
        ? buildDefaults(node)
        : (node.default ?? (node.type === 'boolean' ? false : ''));
  }
  return out;
}

async function loadAgents() {
  loading.value = true;
  try {
    const res = await agentApi.listAgents();
    agents.value = res.agents ?? [];
  } finally {
    loading.value = false;
  }
}

async function loadMeta() {
  schema.value = await agentApi.getAgentSchema();
  const res = await ontologyApi.listOntologies();
  ontologies.value = res.items ?? [];
}

function resetForm() {
  const identityDefaults = buildDefaults(schema.value?.identity);
  form.name = identityDefaults.name ?? '';
  form.system_prompt = identityDefaults.system_prompt ?? '';
  form.context_config = buildDefaults(schema.value?.context_config);
  form.react_config = buildDefaults(schema.value?.react_config);
  binding.ontology_id = '';
  binding.enabled = true;
  binding.allowed_object_types = [];
  binding.allowed_actions = [];
  bindingObjectTypes.value = [];
}

function openCreate() {
  editingId.value = null;
  activeTab.value = 'identity';
  resetForm();
  drawerVisible.value = true;
}

function openEdit(row: AgentRecord) {
  editingId.value = row.id;
  activeTab.value = 'identity';
  form.name = row.data.name;
  form.system_prompt = row.data.system_prompt;
  form.context_config = { ...row.data.context_config };
  form.react_config = { ...row.data.react_config };
  binding.ontology_id = '';
  binding.allowed_object_types = [];
  binding.allowed_actions = [];
  drawerVisible.value = true;
  void ontologyApi.getBinding(row.id).then((b) => {
    if (b) {
      binding.ontology_id = b.ontology_id;
      binding.enabled = b.enabled;
      binding.allowed_object_types = b.allowed_object_types ?? [];
      binding.allowed_actions = b.allowed_actions ?? [];
      void onOntologyChange(b.ontology_id);
    }
  });
}

async function onOntologyChange(id: string) {
  if (!id) {
    bindingObjectTypes.value = [];
    return;
  }
  const res = await ontologyApi.listObjectTypes(id);
  bindingObjectTypes.value = res.items ?? [];
}

async function save() {
  if (!form.name) {
    ElMessage.warning($t('agentscope.agent.name'));
    return;
  }
  saving.value = true;
  try {
    const payload = {
      name: form.name,
      system_prompt: form.system_prompt,
      context_config: form.context_config,
      react_config: form.react_config,
    };
    let agentId = editingId.value;
    if (editingId.value) {
      await agentApi.updateAgent(editingId.value, payload);
      ElMessage.success($t('agentscope.agent.updateSuccess'));
    } else {
      const res = await agentApi.createAgent(payload);
      agentId = res.agent_id;
      ElMessage.success($t('agentscope.agent.createSuccess'));
    }
    if (agentId && binding.ontology_id) {
      await ontologyApi.putBinding(agentId, {
        ontology_id: binding.ontology_id,
        enabled: binding.enabled,
        allowed_object_types: binding.allowed_object_types,
        allowed_actions: binding.allowed_actions,
      });
    }
    drawerVisible.value = false;
    await loadAgents();
  } finally {
    saving.value = false;
  }
}

async function remove(row: AgentRecord) {
  await agentApi.deleteAgent(row.id);
  ElMessage.success($t('agentscope.common.delete'));
  await loadAgents();
}

function objectTypeOptions() {
  return bindingObjectTypes.value.map((t) => ({
    label: `${t.display_name} (${t.api_name})`,
    value: t.api_name,
  }));
}

onMounted(async () => {
  await loadMeta();
  resetForm();
  await loadAgents();
});

// Silence unused import in some builds.
void ElMessageBox;
</script>

<template>
  <Page :title="$t('agentscope.menu.agents')">
    <template #extra>
      <ElButton type="primary" @click="openCreate">
        {{ $t('agentscope.agent.newAgent') }}
      </ElButton>
    </template>

    <ElCard shadow="never">
      <ElTable v-loading="loading" :data="agents" stripe>
        <ElTableColumn :label="$t('agentscope.agent.name')" prop="data.name" />
        <ElTableColumn
          :label="$t('agentscope.agent.systemPrompt')"
          prop="data.system_prompt"
          show-overflow-tooltip
        />
        <ElTableColumn
          :label="$t('agentscope.common.updatedAt')"
          prop="updated_at"
          width="200"
        />
        <ElTableColumn
          :label="$t('agentscope.common.actions')"
          fixed="right"
          width="160"
        >
          <template #default="{ row }">
            <ElButton link type="primary" @click="openEdit(row)">
              {{ $t('agentscope.common.edit') }}
            </ElButton>
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

    <ElDrawer
      v-model="drawerVisible"
      :title="
        editingId
          ? $t('agentscope.agent.editAgent')
          : $t('agentscope.agent.newAgent')
      "
      size="640px"
    >
      <ElForm label-position="top">
        <ElTabs v-model="activeTab">
          <ElTabPane :label="$t('agentscope.agent.identity')" name="identity">
            <SchemaForm v-model="form" :schema="identitySchema" />
          </ElTabPane>
          <ElTabPane
            :label="$t('agentscope.agent.contextConfig')"
            name="context"
          >
            <SchemaForm
              v-if="schema"
              v-model="form.context_config"
              :schema="schema.context_config"
            />
          </ElTabPane>
          <ElTabPane :label="$t('agentscope.agent.reactConfig')" name="react">
            <SchemaForm
              v-if="schema"
              v-model="form.react_config"
              :schema="schema.react_config"
            />
          </ElTabPane>
          <ElTabPane
            :label="$t('agentscope.agent.ontologyBinding')"
            name="ontology"
          >
            <ElFormItem :label="$t('agentscope.agent.bindOntology')">
              <ElSelect
                v-model="binding.ontology_id"
                class="w-full"
                clearable
                @change="onOntologyChange"
              >
                <ElOption
                  v-for="o in ontologies"
                  :key="o.id"
                  :label="o.display_name"
                  :value="o.id"
                />
              </ElSelect>
            </ElFormItem>
            <ElFormItem :label="$t('agentscope.agent.allowedObjectTypes')">
              <ElSelect
                v-model="binding.allowed_object_types"
                class="w-full"
                multiple
              >
                <ElOption
                  v-for="opt in objectTypeOptions()"
                  :key="opt.value"
                  :label="opt.label"
                  :value="opt.value"
                />
              </ElSelect>
            </ElFormItem>
            <ElFormItem :label="$t('agentscope.common.status')">
              <ElSwitch v-model="binding.enabled" />
            </ElFormItem>
          </ElTabPane>
        </ElTabs>
      </ElForm>

      <template #footer>
        <ElButton @click="drawerVisible = false">
          {{ $t('agentscope.common.cancel') }}
        </ElButton>
        <ElButton :loading="saving" type="primary" @click="save">
          {{ $t('agentscope.common.save') }}
        </ElButton>
      </template>
    </ElDrawer>
  </Page>
</template>
