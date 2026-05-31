<script lang="ts" setup>
import type {
  ActionType,
  Connector,
  Datasource,
  LinkType,
  ObjectInstance,
  ObjectType,
  Ontology,
  OntologyGraph as OntologyGraphData,
  PropertyType,
} from '#/api/agentscope';

import { computed, onMounted, reactive, ref } from 'vue';

import { Page } from '@vben/common-ui';

import {
  ElButton,
  ElCard,
  ElDialog,
  ElEmpty,
  ElForm,
  ElFormItem,
  ElInput,
  ElMessage,
  ElOption,
  ElPopconfirm,
  ElScrollbar,
  ElSelect,
  ElSwitch,
  ElTable,
  ElTableColumn,
  ElTabPane,
  ElTabs,
  ElTag,
} from 'element-plus';

import { ontologyApi } from '#/api/agentscope';
import OntologyGraph from '#/components/agentscope/OntologyGraph.vue';
import { $t } from '#/locales';

const DATA_TYPES = [
  'string',
  'integer',
  'double',
  'boolean',
  'date',
  'timestamp',
  'geo_point',
  'array',
];
const CARDINALITIES = ['one_to_one', 'one_to_many', 'many_to_many'];
const EFFECTS = ['create', 'modify', 'delete', 'custom'];

const ontologies = ref<Ontology[]>([]);
const currentId = ref<string>('');
const activeTab = ref('objectTypes');

const objectTypes = ref<ObjectType[]>([]);
const linkTypes = ref<LinkType[]>([]);
const actionTypes = ref<ActionType[]>([]);
const datasources = ref<Datasource[]>([]);
const connectors = ref<Connector[]>([]);
const graph = ref<OntologyGraphData>();

const selectedObjectType = ref<ObjectType>();
const objects = ref<ObjectInstance[]>([]);
const searchText = ref('');

/* ----------------------------- dialogs ----------------------------------- */
const ontologyDialog = ref(false);
const ontologyForm = reactive({
  api_name: '',
  display_name: '',
  description: '',
});

const otDialog = ref(false);
const otForm = reactive<{
  api_name: string;
  color: string;
  description: string;
  display_name: string;
  icon: string;
  properties: Partial<PropertyType>[];
}>({
  api_name: '',
  display_name: '',
  description: '',
  icon: 'Box',
  color: '#3b82f6',
  properties: [],
});

const linkDialog = ref(false);
const linkForm = reactive({
  api_name: '',
  display_name: '',
  source_object_type_id: '',
  target_object_type_id: '',
  cardinality: 'one_to_many',
});

const actionDialog = ref(false);
const actionForm = reactive({
  api_name: '',
  display_name: '',
  effect: 'create',
  object_type_id: '',
});

const objectDialog = ref(false);
const objectForm = reactive<Record<string, any>>({});

const currentOntology = computed(() =>
  ontologies.value.find((o) => o.id === currentId.value),
);

async function loadOntologies() {
  const res = await ontologyApi.listOntologies();
  ontologies.value = res.items ?? [];
  if (!currentId.value && ontologies.value[0]) {
    void selectOntology(ontologies.value[0].id);
  }
}

async function selectOntology(id: string) {
  currentId.value = id;
  await refreshAll();
}

async function refreshAll() {
  if (!currentId.value) return;
  const [ot, lt, at, ds, cn] = await Promise.all([
    ontologyApi.listObjectTypes(currentId.value),
    ontologyApi.listLinkTypes(currentId.value),
    ontologyApi.listActionTypes(currentId.value),
    ontologyApi.listDatasources(currentId.value),
    ontologyApi.listConnectors(currentId.value),
  ]);
  objectTypes.value = ot.items ?? [];
  linkTypes.value = lt.items ?? [];
  actionTypes.value = at.items ?? [];
  datasources.value = ds.items ?? [];
  connectors.value = cn.items ?? [];
  graph.value = await ontologyApi.getGraph(currentId.value);
  if (objectTypes.value.length > 0) {
    selectedObjectType.value =
      objectTypes.value.find((t) => t.id === selectedObjectType.value?.id) ??
      objectTypes.value[0];
    await loadObjects();
  } else {
    selectedObjectType.value = undefined;
    objects.value = [];
  }
}

/* ----------------------------- ontology ---------------------------------- */
async function createOntology() {
  if (!ontologyForm.api_name || !ontologyForm.display_name) return;
  const ont = await ontologyApi.createOntology({ ...ontologyForm });
  ontologyDialog.value = false;
  ontologyForm.api_name = '';
  ontologyForm.display_name = '';
  ontologyForm.description = '';
  await loadOntologies();
  await selectOntology(ont.id);
}

async function removeOntology(id: string) {
  await ontologyApi.deleteOntology(id);
  if (currentId.value === id) currentId.value = '';
  await loadOntologies();
}

/* --------------------------- object types --------------------------------- */
function openObjectType() {
  otForm.api_name = '';
  otForm.display_name = '';
  otForm.description = '';
  otForm.icon = 'Box';
  otForm.color = '#3b82f6';
  otForm.properties = [
    {
      api_name: 'name',
      display_name: 'Name',
      data_type: 'string',
      required: true,
    },
  ];
  otDialog.value = true;
}

function addProperty() {
  otForm.properties.push({
    api_name: '',
    display_name: '',
    data_type: 'string',
    required: false,
  });
}

async function createObjectType() {
  if (!otForm.api_name) return;
  await ontologyApi.createObjectType(currentId.value, { ...otForm });
  otDialog.value = false;
  await refreshAll();
}

async function removeObjectType(row: ObjectType) {
  await ontologyApi.deleteObjectType(currentId.value, row.id);
  await refreshAll();
}

/* ---------------------------- link types ---------------------------------- */
function openLink() {
  linkForm.api_name = '';
  linkForm.display_name = '';
  linkForm.source_object_type_id = '';
  linkForm.target_object_type_id = '';
  linkForm.cardinality = 'one_to_many';
  linkDialog.value = true;
}

async function createLink() {
  if (!linkForm.source_object_type_id || !linkForm.target_object_type_id) {
    ElMessage.warning('source / target required');
    return;
  }
  await ontologyApi.createLinkType(currentId.value, { ...linkForm });
  linkDialog.value = false;
  await refreshAll();
}

async function removeLink(row: LinkType) {
  await ontologyApi.deleteLinkType(currentId.value, row.id);
  await refreshAll();
}

/* --------------------------- action types --------------------------------- */
function openAction() {
  actionForm.api_name = '';
  actionForm.display_name = '';
  actionForm.effect = 'create';
  actionForm.object_type_id = '';
  actionDialog.value = true;
}

async function createAction() {
  if (!actionForm.api_name) return;
  await ontologyApi.createActionType(currentId.value, { ...actionForm });
  actionDialog.value = false;
  await refreshAll();
}

async function removeAction(row: ActionType) {
  await ontologyApi.deleteActionType(currentId.value, row.id);
  await refreshAll();
}

/* ------------------------------ objects ----------------------------------- */
async function loadObjects() {
  if (!selectedObjectType.value) return;
  if (searchText.value) {
    const res = await ontologyApi.queryObjects(currentId.value, {
      object_type: selectedObjectType.value.api_name,
      search: searchText.value,
    });
    objects.value = res.items ?? [];
  } else {
    const res = await ontologyApi.listObjects(
      currentId.value,
      selectedObjectType.value.id,
    );
    objects.value = res.items ?? [];
  }
}

function openObject() {
  Object.keys(objectForm).forEach((k) => delete objectForm[k]);
  (selectedObjectType.value?.properties ?? []).forEach((p) => {
    objectForm[p.api_name] = '';
  });
  objectDialog.value = true;
}

async function createObject() {
  if (!selectedObjectType.value) return;
  await ontologyApi.createObject(currentId.value, selectedObjectType.value.id, {
    ...objectForm,
  });
  objectDialog.value = false;
  await loadObjects();
  await refreshGraphCount();
}

async function removeObject(row: ObjectInstance) {
  if (!selectedObjectType.value) return;
  await ontologyApi.deleteObject(
    currentId.value,
    selectedObjectType.value.id,
    row.id,
  );
  await loadObjects();
}

async function refreshGraphCount() {
  graph.value = await ontologyApi.getGraph(currentId.value);
}

function typeName(id: string) {
  return objectTypes.value.find((t) => t.id === id)?.display_name ?? id;
}

function datasourceOf(row: ObjectType) {
  return datasources.value.find((d) => d.id === row.datasource_id);
}

function connectorOf(row: ActionType) {
  return connectors.value.find((c) => c.id === row.connector_id);
}

function operationLabel(row: ActionType) {
  const cn = connectorOf(row);
  if (!cn || !row.connector_operation) return '';
  const op = cn.operations.find((o) => o.api_name === row.connector_operation);
  return `${cn.api_name}.${op?.api_name ?? row.connector_operation}`;
}

async function selectObjectTypeRow(row: ObjectType) {
  selectedObjectType.value = row;
  searchText.value = '';
  await loadObjects();
}

async function onObjectTypeSelect(id: string) {
  const row = objectTypes.value.find((t) => t.id === id);
  if (row) await selectObjectTypeRow(row);
}

onMounted(loadOntologies);
</script>

<template>
  <Page :title="$t('agentscope.menu.ontology')">
    <div class="flex gap-4">
      <!-- Left: ontology list -->
      <ElCard class="w-60 shrink-0" shadow="never">
        <template #header>
          <div class="flex items-center justify-between">
            <span>{{ $t('agentscope.menu.ontology') }}</span>
            <ElButton link type="primary" @click="ontologyDialog = true">
              {{ $t('agentscope.common.create') }}
            </ElButton>
          </div>
        </template>
        <ElScrollbar max-height="600px">
          <div
            v-for="o in ontologies"
            :key="o.id"
            class="mb-1 cursor-pointer rounded px-3 py-2 text-sm"
            :class="[
              currentId === o.id
                ? 'bg-primary/10 text-primary'
                : 'hover:bg-accent',
            ]"
            @click="selectOntology(o.id)"
          >
            <div class="flex items-center justify-between">
              <span class="truncate">{{ o.display_name }}</span>
              <ElPopconfirm
                :title="$t('agentscope.common.deleteConfirm')"
                @confirm="removeOntology(o.id)"
              >
                <template #reference>
                  <span
                    class="text-foreground/40 hover:text-red-500"
                    @click.stop
                  >
                    ×
                  </span>
                </template>
              </ElPopconfirm>
            </div>
            <div class="text-foreground/40 text-xs">{{ o.api_name }}</div>
          </div>
          <ElEmpty
            v-if="ontologies.length === 0"
            :description="$t('agentscope.common.empty')"
            :image-size="60"
          />
        </ElScrollbar>
      </ElCard>

      <!-- Right: detail -->
      <ElCard class="min-w-0 flex-1" shadow="never">
        <ElEmpty
          v-if="!currentOntology"
          :description="$t('agentscope.ontology.selectOntology')"
        />
        <ElTabs v-else v-model="activeTab">
          <!-- Object types -->
          <ElTabPane
            :label="$t('agentscope.ontology.objectTypes')"
            name="objectTypes"
          >
            <div class="mb-3">
              <ElButton type="primary" @click="openObjectType">
                {{ $t('agentscope.ontology.newObjectType') }}
              </ElButton>
            </div>
            <ElTable
              :data="objectTypes"
              highlight-current-row
              row-key="id"
              @row-click="selectObjectTypeRow"
            >
              <ElTableColumn type="expand">
                <template #default="{ row }">
                  <div class="px-6 py-2">
                    <div class="text-foreground/60 mb-2 text-xs font-medium">
                      {{ $t('agentscope.ontology.propertyColumnMapping') }}
                    </div>
                    <ElTable :data="row.properties" size="small">
                      <ElTableColumn
                        :label="$t('agentscope.ontology.apiName')"
                        prop="api_name"
                      />
                      <ElTableColumn
                        :label="$t('agentscope.ontology.dataType')"
                        prop="data_type"
                      />
                      <ElTableColumn
                        :label="$t('agentscope.ontology.columnMapping')"
                      >
                        <template #default="{ row: p }">
                          <ElTag size="small" type="info">
                            {{ p.column_mapping || p.api_name }}
                          </ElTag>
                        </template>
                      </ElTableColumn>
                    </ElTable>
                  </div>
                </template>
              </ElTableColumn>
              <ElTableColumn
                :label="$t('agentscope.ontology.displayName')"
                prop="display_name"
              />
              <ElTableColumn
                :label="$t('agentscope.ontology.apiName')"
                prop="api_name"
              />
              <ElTableColumn :label="$t('agentscope.ontology.datasource')">
                <template #default="{ row }">
                  <template v-if="datasourceOf(row)">
                    <ElTag size="small" type="success">
                      {{ datasourceOf(row)?.api_name }}
                    </ElTag>
                    <span class="text-foreground/50 ml-1 text-xs">
                      {{ row.backing_table }}
                    </span>
                  </template>
                  <span v-else class="text-foreground/40 text-xs">
                    {{ $t('agentscope.ontology.noDatasource') }}
                  </span>
                </template>
              </ElTableColumn>
              <ElTableColumn :label="$t('agentscope.ontology.properties')">
                <template #default="{ row }">
                  <ElTag
                    v-for="p in row.properties"
                    :key="p.id"
                    class="mr-1"
                    size="small"
                  >
                    {{ p.api_name }}
                  </ElTag>
                </template>
              </ElTableColumn>
              <ElTableColumn
                :label="$t('agentscope.common.actions')"
                width="100"
              >
                <template #default="{ row }">
                  <ElPopconfirm
                    :title="$t('agentscope.common.deleteConfirm')"
                    @confirm="removeObjectType(row)"
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
          </ElTabPane>

          <!-- Link types -->
          <ElTabPane
            :label="$t('agentscope.ontology.linkTypes')"
            name="linkTypes"
          >
            <div class="mb-3">
              <ElButton type="primary" @click="openLink">
                {{ $t('agentscope.ontology.newLinkType') }}
              </ElButton>
            </div>
            <ElTable :data="linkTypes">
              <ElTableColumn
                :label="$t('agentscope.ontology.displayName')"
                prop="display_name"
              />
              <ElTableColumn :label="$t('agentscope.ontology.source')">
                <template #default="{ row }">
                  {{ typeName(row.source_object_type_id) }}
                </template>
              </ElTableColumn>
              <ElTableColumn :label="$t('agentscope.ontology.target')">
                <template #default="{ row }">
                  {{ typeName(row.target_object_type_id) }}
                </template>
              </ElTableColumn>
              <ElTableColumn
                :label="$t('agentscope.ontology.cardinality')"
                prop="cardinality"
              />
              <ElTableColumn
                :label="$t('agentscope.common.actions')"
                width="100"
              >
                <template #default="{ row }">
                  <ElPopconfirm
                    :title="$t('agentscope.common.deleteConfirm')"
                    @confirm="removeLink(row)"
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
          </ElTabPane>

          <!-- Action types -->
          <ElTabPane
            :label="$t('agentscope.ontology.actionTypes')"
            name="actionTypes"
          >
            <div class="mb-3">
              <ElButton type="primary" @click="openAction">
                {{ $t('agentscope.ontology.newActionType') }}
              </ElButton>
            </div>
            <ElTable :data="actionTypes">
              <ElTableColumn
                :label="$t('agentscope.ontology.displayName')"
                prop="display_name"
              />
              <ElTableColumn
                :label="$t('agentscope.ontology.apiName')"
                prop="api_name"
              />
              <ElTableColumn
                :label="$t('agentscope.ontology.effect')"
                prop="effect"
              />
              <ElTableColumn :label="$t('agentscope.ontology.writesBackTo')">
                <template #default="{ row }">
                  <ElTag v-if="connectorOf(row)" size="small" type="warning">
                    {{ operationLabel(row) }}
                  </ElTag>
                  <span v-else class="text-foreground/40 text-xs">
                    {{ $t('agentscope.ontology.noWriteBack') }}
                  </span>
                </template>
              </ElTableColumn>
              <ElTableColumn
                :label="$t('agentscope.common.actions')"
                width="100"
              >
                <template #default="{ row }">
                  <ElPopconfirm
                    :title="$t('agentscope.common.deleteConfirm')"
                    @confirm="removeAction(row)"
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
          </ElTabPane>

          <!-- Datasources -->
          <ElTabPane
            :label="$t('agentscope.ontology.datasources')"
            name="datasources"
          >
            <ElTable :data="datasources" row-key="id">
              <ElTableColumn type="expand">
                <template #default="{ row }">
                  <div class="px-6 py-2">
                    <div class="text-foreground/60 mb-2 text-xs font-medium">
                      {{ $t('agentscope.ontology.columns') }}
                    </div>
                    <ElTable :data="row.columns" size="small">
                      <ElTableColumn label="name" prop="name" />
                      <ElTableColumn label="data_type" prop="data_type" />
                    </ElTable>
                  </div>
                </template>
              </ElTableColumn>
              <ElTableColumn
                :label="$t('agentscope.ontology.displayName')"
                prop="display_name"
              />
              <ElTableColumn
                :label="$t('agentscope.ontology.apiName')"
                prop="api_name"
              />
              <ElTableColumn :label="$t('agentscope.ontology.kind')">
                <template #default="{ row }">
                  <ElTag size="small">{{ row.kind }}</ElTag>
                </template>
              </ElTableColumn>
              <ElTableColumn :label="$t('agentscope.ontology.columns')">
                <template #default="{ row }">
                  {{ row.columns.length }}
                </template>
              </ElTableColumn>
            </ElTable>
            <ElEmpty
              v-if="datasources.length === 0"
              :description="$t('agentscope.common.empty')"
              :image-size="60"
            />
          </ElTabPane>

          <!-- Connectors -->
          <ElTabPane
            :label="$t('agentscope.ontology.connectors')"
            name="connectors"
          >
            <ElTable :data="connectors" row-key="id">
              <ElTableColumn type="expand">
                <template #default="{ row }">
                  <div class="px-6 py-2">
                    <div class="text-foreground/60 mb-2 text-xs font-medium">
                      {{ $t('agentscope.ontology.operations') }}
                    </div>
                    <ElTable :data="row.operations" size="small">
                      <ElTableColumn label="api_name" prop="api_name" />
                      <ElTableColumn label="method" prop="method" />
                      <ElTableColumn label="path" prop="path" />
                      <ElTableColumn label="params">
                        <template #default="{ row: op }">
                          <ElTag
                            v-for="pp in op.params ?? []"
                            :key="pp"
                            class="mr-1"
                            size="small"
                            type="info"
                          >
                            {{ pp }}
                          </ElTag>
                        </template>
                      </ElTableColumn>
                    </ElTable>
                  </div>
                </template>
              </ElTableColumn>
              <ElTableColumn
                :label="$t('agentscope.ontology.displayName')"
                prop="display_name"
              />
              <ElTableColumn
                :label="$t('agentscope.ontology.apiName')"
                prop="api_name"
              />
              <ElTableColumn :label="$t('agentscope.ontology.kind')">
                <template #default="{ row }">
                  <ElTag size="small" type="warning">{{ row.kind }}</ElTag>
                </template>
              </ElTableColumn>
              <ElTableColumn :label="$t('agentscope.ontology.operations')">
                <template #default="{ row }">
                  {{ row.operations.length }}
                </template>
              </ElTableColumn>
            </ElTable>
            <ElEmpty
              v-if="connectors.length === 0"
              :description="$t('agentscope.common.empty')"
              :image-size="60"
            />
          </ElTabPane>

          <!-- Objects -->
          <ElTabPane :label="$t('agentscope.ontology.objects')" name="objects">
            <div class="mb-3 flex items-center gap-2">
              <ElSelect
                :model-value="selectedObjectType?.id"
                class="w-48"
                @change="onObjectTypeSelect"
              >
                <ElOption
                  v-for="t in objectTypes"
                  :key="t.id"
                  :label="t.display_name"
                  :value="t.id"
                />
              </ElSelect>
              <ElInput
                v-model="searchText"
                :placeholder="$t('agentscope.ontology.query')"
                class="w-60"
                clearable
                @keyup.enter="loadObjects"
                @clear="loadObjects"
              />
              <ElButton @click="loadObjects">
                {{ $t('agentscope.common.search') }}
              </ElButton>
              <ElButton
                :disabled="!selectedObjectType"
                type="primary"
                @click="openObject"
              >
                {{ $t('agentscope.ontology.newObject') }}
              </ElButton>
            </div>
            <ElTable :data="objects">
              <ElTableColumn
                v-for="p in selectedObjectType?.properties ?? []"
                :key="p.api_name"
                :label="p.display_name"
              >
                <template #default="{ row }">
                  {{ row.properties?.[p.api_name] }}
                </template>
              </ElTableColumn>
              <ElTableColumn
                :label="$t('agentscope.common.actions')"
                width="100"
              >
                <template #default="{ row }">
                  <ElPopconfirm
                    :title="$t('agentscope.common.deleteConfirm')"
                    @confirm="removeObject(row)"
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
          </ElTabPane>

          <!-- Graph -->
          <ElTabPane :label="$t('agentscope.ontology.graph')" name="graph">
            <OntologyGraph :graph="graph" />
          </ElTabPane>
        </ElTabs>
      </ElCard>
    </div>

    <!-- Ontology dialog -->
    <ElDialog
      v-model="ontologyDialog"
      :title="$t('agentscope.ontology.newOntology')"
      width="460px"
    >
      <ElForm label-position="top">
        <ElFormItem :label="$t('agentscope.ontology.apiName')" required>
          <ElInput v-model="ontologyForm.api_name" />
        </ElFormItem>
        <ElFormItem :label="$t('agentscope.ontology.displayName')" required>
          <ElInput v-model="ontologyForm.display_name" />
        </ElFormItem>
        <ElFormItem :label="$t('agentscope.common.description')">
          <ElInput v-model="ontologyForm.description" type="textarea" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="ontologyDialog = false">
          {{ $t('agentscope.common.cancel') }}
        </ElButton>
        <ElButton type="primary" @click="createOntology">
          {{ $t('agentscope.common.save') }}
        </ElButton>
      </template>
    </ElDialog>

    <!-- Object type dialog -->
    <ElDialog
      v-model="otDialog"
      :title="$t('agentscope.ontology.newObjectType')"
      width="720px"
    >
      <ElForm label-position="top">
        <div class="flex gap-3">
          <ElFormItem
            :label="$t('agentscope.ontology.apiName')"
            class="flex-1"
            required
          >
            <ElInput v-model="otForm.api_name" />
          </ElFormItem>
          <ElFormItem
            :label="$t('agentscope.ontology.displayName')"
            class="flex-1"
          >
            <ElInput v-model="otForm.display_name" />
          </ElFormItem>
          <ElFormItem label="Color" style="width: 120px">
            <ElInput v-model="otForm.color" />
          </ElFormItem>
        </div>
        <div class="mb-2 flex items-center justify-between">
          <span class="font-medium">
            {{ $t('agentscope.ontology.properties') }}
          </span>
          <ElButton link type="primary" @click="addProperty">
            {{ $t('agentscope.ontology.addProperty') }}
          </ElButton>
        </div>
        <ElTable :data="otForm.properties" size="small">
          <ElTableColumn :label="$t('agentscope.ontology.apiName')">
            <template #default="{ row }">
              <ElInput v-model="row.api_name" size="small" />
            </template>
          </ElTableColumn>
          <ElTableColumn :label="$t('agentscope.ontology.displayName')">
            <template #default="{ row }">
              <ElInput v-model="row.display_name" size="small" />
            </template>
          </ElTableColumn>
          <ElTableColumn :label="$t('agentscope.ontology.dataType')">
            <template #default="{ row }">
              <ElSelect v-model="row.data_type" size="small">
                <ElOption
                  v-for="dt in DATA_TYPES"
                  :key="dt"
                  :label="dt"
                  :value="dt"
                />
              </ElSelect>
            </template>
          </ElTableColumn>
          <ElTableColumn :label="$t('agentscope.ontology.required')" width="80">
            <template #default="{ row }">
              <ElSwitch v-model="row.required" size="small" />
            </template>
          </ElTableColumn>
        </ElTable>
      </ElForm>
      <template #footer>
        <ElButton @click="otDialog = false">
          {{ $t('agentscope.common.cancel') }}
        </ElButton>
        <ElButton type="primary" @click="createObjectType">
          {{ $t('agentscope.common.save') }}
        </ElButton>
      </template>
    </ElDialog>

    <!-- Link type dialog -->
    <ElDialog
      v-model="linkDialog"
      :title="$t('agentscope.ontology.newLinkType')"
      width="520px"
    >
      <ElForm label-position="top">
        <ElFormItem :label="$t('agentscope.ontology.apiName')" required>
          <ElInput v-model="linkForm.api_name" />
        </ElFormItem>
        <ElFormItem :label="$t('agentscope.ontology.displayName')">
          <ElInput v-model="linkForm.display_name" />
        </ElFormItem>
        <ElFormItem :label="$t('agentscope.ontology.source')" required>
          <ElSelect v-model="linkForm.source_object_type_id" class="w-full">
            <ElOption
              v-for="t in objectTypes"
              :key="t.id"
              :label="t.display_name"
              :value="t.id"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem :label="$t('agentscope.ontology.target')" required>
          <ElSelect v-model="linkForm.target_object_type_id" class="w-full">
            <ElOption
              v-for="t in objectTypes"
              :key="t.id"
              :label="t.display_name"
              :value="t.id"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem :label="$t('agentscope.ontology.cardinality')">
          <ElSelect v-model="linkForm.cardinality" class="w-full">
            <ElOption
              v-for="c in CARDINALITIES"
              :key="c"
              :label="c"
              :value="c"
            />
          </ElSelect>
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="linkDialog = false">
          {{ $t('agentscope.common.cancel') }}
        </ElButton>
        <ElButton type="primary" @click="createLink">
          {{ $t('agentscope.common.save') }}
        </ElButton>
      </template>
    </ElDialog>

    <!-- Action type dialog -->
    <ElDialog
      v-model="actionDialog"
      :title="$t('agentscope.ontology.newActionType')"
      width="520px"
    >
      <ElForm label-position="top">
        <ElFormItem :label="$t('agentscope.ontology.apiName')" required>
          <ElInput v-model="actionForm.api_name" />
        </ElFormItem>
        <ElFormItem :label="$t('agentscope.ontology.displayName')">
          <ElInput v-model="actionForm.display_name" />
        </ElFormItem>
        <ElFormItem :label="$t('agentscope.ontology.effect')">
          <ElSelect v-model="actionForm.effect" class="w-full">
            <ElOption v-for="e in EFFECTS" :key="e" :label="e" :value="e" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="Object Type">
          <ElSelect
            v-model="actionForm.object_type_id"
            class="w-full"
            clearable
          >
            <ElOption
              v-for="t in objectTypes"
              :key="t.id"
              :label="t.display_name"
              :value="t.id"
            />
          </ElSelect>
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="actionDialog = false">
          {{ $t('agentscope.common.cancel') }}
        </ElButton>
        <ElButton type="primary" @click="createAction">
          {{ $t('agentscope.common.save') }}
        </ElButton>
      </template>
    </ElDialog>

    <!-- Object instance dialog -->
    <ElDialog
      v-model="objectDialog"
      :title="$t('agentscope.ontology.newObject')"
      width="520px"
    >
      <ElForm label-position="top">
        <ElFormItem
          v-for="p in selectedObjectType?.properties ?? []"
          :key="p.api_name"
          :label="p.display_name || p.api_name"
          :required="p.required"
        >
          <ElInput v-model="objectForm[p.api_name]" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="objectDialog = false">
          {{ $t('agentscope.common.cancel') }}
        </ElButton>
        <ElButton type="primary" @click="createObject">
          {{ $t('agentscope.common.save') }}
        </ElButton>
      </template>
    </ElDialog>
  </Page>
</template>
