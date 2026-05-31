<script lang="ts" setup>
import type { RbacRole, RbacUser } from '#/api/agentscope/rbac';

import { computed, onMounted, reactive, ref } from 'vue';

import { Page } from '@vben/common-ui';

import {
  ElButton,
  ElCard,
  ElCol,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElMessage,
  ElOption,
  ElPopconfirm,
  ElRow,
  ElSelect,
  ElSwitch,
  ElTable,
  ElTableColumn,
  ElTag,
} from 'element-plus';

import { rbacApi } from '#/api/agentscope';
import { $t } from '#/locales';

const loading = ref(false);
const users = ref<RbacUser[]>([]);
const roles = ref<RbacRole[]>([]);

type TagType = 'danger' | 'info' | 'primary' | 'success' | 'warning';
const roleTagType: Record<string, TagType> = {
  admin: 'danger',
  editor: 'warning',
  viewer: 'info',
};

const dialog = ref(false);
const saving = ref(false);
const editingId = ref<string>('');
const form = reactive({
  username: '',
  display_name: '',
  role: 'viewer',
  enabled: true,
});

const isEdit = computed(() => editingId.value !== '');

async function load() {
  loading.value = true;
  try {
    const [u, r] = await Promise.all([
      rbacApi.listUsers(),
      rbacApi.listRoles(),
    ]);
    users.value = u.items ?? [];
    roles.value = r.items ?? [];
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  editingId.value = '';
  form.username = '';
  form.display_name = '';
  form.role = 'viewer';
  form.enabled = true;
  dialog.value = true;
}

function openEdit(row: RbacUser) {
  editingId.value = row.id;
  form.username = row.username;
  form.display_name = row.display_name;
  form.role = row.role;
  form.enabled = row.enabled;
  dialog.value = true;
}

async function save() {
  if (!form.username.trim()) {
    ElMessage.warning($t('agentscope.rbac.usernameRequired'));
    return;
  }
  saving.value = true;
  try {
    await (isEdit.value
      ? rbacApi.updateUser(editingId.value, {
          display_name: form.display_name,
          role: form.role,
          enabled: form.enabled,
        })
      : rbacApi.createUser({
          username: form.username.trim(),
          display_name: form.display_name,
          role: form.role,
          enabled: form.enabled,
        }));
    ElMessage.success($t('agentscope.common.saveSuccess'));
    dialog.value = false;
    await load();
  } finally {
    saving.value = false;
  }
}

async function toggleEnabled(row: RbacUser) {
  await rbacApi.updateUser(row.id, { enabled: row.enabled });
  ElMessage.success($t('agentscope.common.saveSuccess'));
}

async function remove(row: RbacUser) {
  await rbacApi.deleteUser(row.id);
  ElMessage.success($t('agentscope.common.deleteSuccess'));
  await load();
}

onMounted(load);
</script>

<template>
  <Page :title="$t('agentscope.menu.users')">
    <template #extra>
      <ElButton type="primary" @click="openCreate">
        {{ $t('agentscope.rbac.addUser') }}
      </ElButton>
    </template>

    <ElRow :gutter="16">
      <ElCol :lg="16" :md="14" :sm="24" :xs="24" class="mb-4">
        <ElCard shadow="never">
          <template #header>{{ $t('agentscope.rbac.members') }}</template>
          <ElTable v-loading="loading" :data="users" stripe>
            <ElTableColumn
              :label="$t('agentscope.rbac.username')"
              prop="username"
            />
            <ElTableColumn
              :label="$t('agentscope.rbac.displayName')"
              prop="display_name"
            />
            <ElTableColumn :label="$t('agentscope.rbac.role')" width="120">
              <template #default="{ row }">
                <ElTag :type="roleTagType[row.role] ?? 'info'" size="small">
                  {{ row.role }}
                </ElTag>
              </template>
            </ElTableColumn>
            <ElTableColumn :label="$t('agentscope.common.enabled')" width="100">
              <template #default="{ row }">
                <ElSwitch
                  v-model="row.enabled"
                  :disabled="row.username === 'admin'"
                  @change="toggleEnabled(row)"
                />
              </template>
            </ElTableColumn>
            <ElTableColumn :label="$t('agentscope.common.actions')" width="160">
              <template #default="{ row }">
                <ElButton link type="primary" @click="openEdit(row)">
                  {{ $t('agentscope.common.edit') }}
                </ElButton>
                <ElPopconfirm
                  v-if="row.username !== 'admin'"
                  :title="$t('agentscope.common.confirmDelete')"
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
      </ElCol>

      <ElCol :lg="8" :md="10" :sm="24" :xs="24" class="mb-4">
        <ElCard shadow="never">
          <template #header>{{ $t('agentscope.rbac.roleCatalog') }}</template>
          <div
            v-for="r in roles"
            :key="r.name"
            class="border-border mb-3 rounded border p-3"
          >
            <div class="mb-2 flex items-center gap-2">
              <ElTag :type="roleTagType[r.name] ?? 'info'" size="small">
                {{ r.name }}
              </ElTag>
              <span class="text-foreground/60 text-sm">{{ r.label }}</span>
            </div>
            <div class="flex flex-wrap gap-1">
              <ElTag
                v-for="p in r.permissions"
                :key="p"
                effect="plain"
                size="small"
              >
                {{ p }}
              </ElTag>
            </div>
          </div>
        </ElCard>
      </ElCol>
    </ElRow>

    <ElDialog
      v-model="dialog"
      :title="
        isEdit ? $t('agentscope.rbac.editUser') : $t('agentscope.rbac.addUser')
      "
      width="460px"
    >
      <ElForm label-position="top">
        <ElFormItem :label="$t('agentscope.rbac.username')">
          <ElInput v-model="form.username" :disabled="isEdit" />
        </ElFormItem>
        <ElFormItem :label="$t('agentscope.rbac.displayName')">
          <ElInput v-model="form.display_name" />
        </ElFormItem>
        <ElFormItem :label="$t('agentscope.rbac.role')">
          <ElSelect v-model="form.role" class="w-full">
            <ElOption
              v-for="r in roles"
              :key="r.name"
              :label="`${r.name} · ${r.label}`"
              :value="r.name"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem :label="$t('agentscope.common.enabled')">
          <ElSwitch v-model="form.enabled" />
        </ElFormItem>
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
