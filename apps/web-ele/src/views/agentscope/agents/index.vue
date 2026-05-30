<script lang="ts" setup>
import type {
  AgentProfile,
  AgentRecord,
  AgentSchemaResponse,
  CredentialRecord,
  JsonSchema,
  ModelCard,
  ObjectType,
  Ontology,
} from '#/api/agentscope';

import { computed, onMounted, reactive, ref } from 'vue';

import { Page } from '@vben/common-ui';

import {
  ElButton,
  ElCard,
  ElDivider,
  ElDrawer,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
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

import {
  agentApi,
  agentProfileApi,
  credentialApi,
  modelApi,
  ontologyApi,
} from '#/api/agentscope';
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

const credentials = ref<CredentialRecord[]>([]);
const defaultModels = ref<ModelCard[]>([]);
const fallbackModels = ref<ModelCard[]>([]);
const profile = reactive({
  default_credential_id: '',
  default_model: '',
  parameters: {
    temperature: undefined as number | undefined,
    top_p: undefined as number | undefined,
    max_tokens: undefined as number | undefined,
  },
  fallback_credential_id: '',
  fallback_model: '',
  stream: true,
  permission_mode: 'default',
  description: '',
  tags: [] as string[],
});

const permissionModes = [
  'default',
  'accept_edits',
  'explore',
  'bypass',
  'dont_ask',
];

function credentialType(id: string): string {
  return credentials.value.find((c) => c.id === id)?.data?.type ?? '';
}

async function loadModelsFor(
  credentialId: string,
  target: 'default' | 'fallback',
) {
  const list = target === 'default' ? defaultModels : fallbackModels;
  list.value = [];
  const type = credentialType(credentialId);
  if (!type) return;
  try {
    const res = await modelApi.listModels(type);
    list.value = res.models ?? [];
  } catch {
    // provider may not support listing; manual entry still allowed
  }
}

function onDefaultCredentialChange(id: string) {
  profile.default_model = '';
  void loadModelsFor(id, 'default');
}

function onFallbackCredentialChange(id: string) {
  profile.fallback_model = '';
  void loadModelsFor(id, 'fallback');
}

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
  const [ont, creds] = await Promise.all([
    ontologyApi.listOntologies(),
    credentialApi.listCredentials(),
  ]);
  ontologies.value = ont.items ?? [];
  credentials.value = creds.credentials ?? [];
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
  profile.default_credential_id = '';
  profile.default_model = '';
  profile.parameters = {
    temperature: undefined,
    top_p: undefined,
    max_tokens: undefined,
  };
  profile.fallback_credential_id = '';
  profile.fallback_model = '';
  profile.stream = true;
  profile.permission_mode = 'default';
  profile.description = '';
  profile.tags = [];
  defaultModels.value = [];
  fallbackModels.value = [];
}

function applyProfile(p: AgentProfile) {
  profile.default_credential_id = p.default_credential_id ?? '';
  profile.default_model = p.default_model ?? '';
  profile.parameters = {
    temperature: p.parameters?.temperature,
    top_p: p.parameters?.top_p,
    max_tokens: p.parameters?.max_tokens,
  };
  profile.fallback_credential_id = p.fallback_credential_id ?? '';
  profile.fallback_model = p.fallback_model ?? '';
  profile.stream = p.stream ?? true;
  profile.permission_mode = p.permission_mode ?? 'default';
  profile.description = p.description ?? '';
  profile.tags = p.tags ?? [];
  if (profile.default_credential_id)
    void loadModelsFor(profile.default_credential_id, 'default');
  if (profile.fallback_credential_id)
    void loadModelsFor(profile.fallback_credential_id, 'fallback');
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
  void agentProfileApi.getProfile(row.id).then((p) => {
    if (p) applyProfile(p);
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
    if (agentId && profile.default_credential_id) {
      const params: Record<string, number> = {};
      if (profile.parameters.temperature !== undefined)
        params.temperature = profile.parameters.temperature;
      if (profile.parameters.top_p !== undefined)
        params.top_p = profile.parameters.top_p;
      if (profile.parameters.max_tokens !== undefined)
        params.max_tokens = profile.parameters.max_tokens;
      await agentProfileApi.putProfile(agentId, {
        default_provider: credentialType(profile.default_credential_id),
        default_credential_id: profile.default_credential_id,
        default_model: profile.default_model,
        parameters: params,
        fallback_provider: credentialType(profile.fallback_credential_id),
        fallback_credential_id: profile.fallback_credential_id || null,
        fallback_model: profile.fallback_model || null,
        stream: profile.stream,
        permission_mode: profile.permission_mode,
        description: profile.description,
        tags: profile.tags,
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
          <ElTabPane :label="$t('agentscope.agent.modelConfig')" name="model">
            <p class="text-foreground/50 mb-3 text-xs">
              {{ $t('agentscope.agent.modelHint') }}
            </p>
            <ElFormItem :label="$t('agentscope.agent.defaultCredential')">
              <ElSelect
                v-model="profile.default_credential_id"
                class="w-full"
                clearable
                @change="onDefaultCredentialChange"
              >
                <ElOption
                  v-for="c in credentials"
                  :key="c.id"
                  :label="`${c.data.type} · ${c.id.slice(0, 8)}`"
                  :value="c.id"
                />
              </ElSelect>
            </ElFormItem>
            <ElFormItem :label="$t('agentscope.agent.defaultModel')">
              <ElSelect
                v-model="profile.default_model"
                allow-create
                class="w-full"
                clearable
                filterable
                :disabled="!profile.default_credential_id"
              >
                <ElOption
                  v-for="m in defaultModels"
                  :key="m.name"
                  :label="m.label || m.name"
                  :value="m.name"
                />
              </ElSelect>
            </ElFormItem>
            <ElFormItem :label="$t('agentscope.agent.temperature')">
              <ElInputNumber
                v-model="profile.parameters.temperature"
                :max="2"
                :min="0"
                :step="0.1"
                class="w-full"
              />
            </ElFormItem>
            <ElFormItem :label="$t('agentscope.agent.topP')">
              <ElInputNumber
                v-model="profile.parameters.top_p"
                :max="1"
                :min="0"
                :step="0.05"
                class="w-full"
              />
            </ElFormItem>
            <ElFormItem :label="$t('agentscope.agent.maxTokens')">
              <ElInputNumber
                v-model="profile.parameters.max_tokens"
                :min="1"
                :step="256"
                class="w-full"
              />
            </ElFormItem>
            <ElFormItem :label="$t('agentscope.agent.stream')">
              <ElSwitch v-model="profile.stream" />
            </ElFormItem>
            <ElFormItem :label="$t('agentscope.agent.permissionMode')">
              <ElSelect v-model="profile.permission_mode" class="w-full">
                <ElOption
                  v-for="pm in permissionModes"
                  :key="pm"
                  :label="$t(`agentscope.agent.permission.${pm}`)"
                  :value="pm"
                />
              </ElSelect>
            </ElFormItem>
            <ElDivider>{{ $t('agentscope.agent.fallback') }}</ElDivider>
            <ElFormItem :label="$t('agentscope.agent.fallbackCredential')">
              <ElSelect
                v-model="profile.fallback_credential_id"
                class="w-full"
                clearable
                @change="onFallbackCredentialChange"
              >
                <ElOption
                  v-for="c in credentials"
                  :key="c.id"
                  :label="`${c.data.type} · ${c.id.slice(0, 8)}`"
                  :value="c.id"
                />
              </ElSelect>
            </ElFormItem>
            <ElFormItem :label="$t('agentscope.agent.fallbackModel')">
              <ElSelect
                v-model="profile.fallback_model"
                allow-create
                class="w-full"
                clearable
                filterable
                :disabled="!profile.fallback_credential_id"
              >
                <ElOption
                  v-for="m in fallbackModels"
                  :key="m.name"
                  :label="m.label || m.name"
                  :value="m.name"
                />
              </ElSelect>
            </ElFormItem>
            <ElDivider />
            <ElFormItem :label="$t('agentscope.common.description')">
              <ElInput
                v-model="profile.description"
                :rows="2"
                type="textarea"
              />
            </ElFormItem>
            <ElFormItem :label="$t('agentscope.agent.tags')">
              <ElSelect
                v-model="profile.tags"
                allow-create
                class="w-full"
                filterable
                multiple
                :reserve-keyword="false"
              />
            </ElFormItem>
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
