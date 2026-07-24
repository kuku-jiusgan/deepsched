<template>
  <div>
    <div class="page-header role-header">
      <div>
        <h2>角色管理</h2>
        <p>按页面配置角色的查看和操作权限，权限变更在用户下次进入页面时实时校验。</p>
      </div>
    </div>

    <div class="role-toolbar">
      <span class="toolbar-label">当前角色</span>
      <a-segmented v-model:value="selectedRole" :options="roles" />
      <a-tag v-if="selectedRole === ADMIN_ROLE" color="blue">全部权限</a-tag>
      <a-button v-operation="'save'" class="save-permissions-button" type="primary" :loading="isSaving" :disabled="selectedRole === ADMIN_ROLE" @click="savePermissions">
        <SaveOutlined /> 保存权限
      </a-button>
    </div>

    <a-alert
      v-if="selectedRole === ADMIN_ROLE"
      type="info"
      show-icon
      message="系统管理员始终拥有全部页面的查看和操作权限，不能修改。"
      class="permission-alert"
    />

    <a-table
      :loading="isLoading"
      :data-source="currentPermissions"
      :columns="columns"
      row-key="page_key"
      size="small"
      :pagination="false"
      :scroll="{ x: 900 }"
      class="permission-table"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'view'">
          <a-checkbox
            :checked="record.can_view"
            :disabled="selectedRole === ADMIN_ROLE"
            @change="setViewPermission(record, $event.target.checked)"
          />
        </template>
        <template v-else-if="column.key === 'actions'">
          <a-space v-if="record.actions.length" wrap :size="[16, 8]">
            <a-checkbox
              v-for="action in record.actions"
              :key="action.action_key"
              :checked="action.allowed"
              :disabled="selectedRole === ADMIN_ROLE"
              @change="setActionPermission(record, action.action_key, $event.target.checked)"
            >{{ action.action_name }}</a-checkbox>
          </a-space>
          <span v-else class="no-actions">无操作按钮</span>
        </template>
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { SaveOutlined } from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import { getRolePermissions, updateRolePermissions, type PagePermission } from '@/services/api'
import { loadMyPermissions } from '@/services/permissions'

const ADMIN_ROLE = '系统管理员'
const roles = ref<string[]>([])
const selectedRole = ref(ADMIN_ROLE)
const permissionItems = ref<Record<string, PagePermission[]>>({})
const isLoading = ref(false)
const isSaving = ref(false)
const currentPermissions = computed(() => permissionItems.value[selectedRole.value] || [])
const columns = [
  { title: '功能分组', dataIndex: 'group_name', key: 'group', width: 160 },
  { title: '页面', dataIndex: 'page_name', key: 'page' },
  { title: '查看权限', key: 'view', width: 120, align: 'center' },
  { title: '按钮操作权限', key: 'actions', width: 520 },
]

function setViewPermission(record: PagePermission, checked: boolean) {
  record.can_view = checked
  if (!checked) record.actions.forEach(action => { action.allowed = false })
  record.can_operate = record.actions.some(action => action.allowed)
}

function setActionPermission(record: PagePermission, actionKey: string, checked: boolean) {
  const action = record.actions.find(item => item.action_key === actionKey)
  if (action) action.allowed = checked
  if (checked) record.can_view = true
  record.can_operate = record.actions.some(item => item.allowed)
}

async function loadPermissions() {
  isLoading.value = true
  try {
    const result = await getRolePermissions()
    roles.value = result.roles
    permissionItems.value = result.items
  } catch {
    message.error('角色权限加载失败')
  } finally {
    isLoading.value = false
  }
}

async function savePermissions() {
  if (selectedRole.value === ADMIN_ROLE) return
  isSaving.value = true
  try {
    permissionItems.value[selectedRole.value] = await updateRolePermissions(selectedRole.value, currentPermissions.value)
    await loadMyPermissions(true)
    message.success('角色权限已保存')
  } catch {
    message.error('角色权限保存失败')
  } finally {
    isSaving.value = false
  }
}

onMounted(loadPermissions)
</script>

<style scoped>
.role-header p { margin: 4px 0 0; color: #64748b; }
.role-toolbar { display: flex; align-items: center; gap: 12px; margin: 16px 0; }
.toolbar-label { color: #475569; font-weight: 600; }
.save-permissions-button { margin-left: auto; }
.permission-alert { margin-bottom: 12px; }
.permission-table :deep(.ant-table-cell:nth-last-child(2)) { text-align: center; }
.no-actions { color: #94a3b8; }
@media (max-width: 720px) {
  .role-toolbar { align-items: flex-start; flex-direction: column; }
  .save-permissions-button { margin-left: 0; }
}
</style>
