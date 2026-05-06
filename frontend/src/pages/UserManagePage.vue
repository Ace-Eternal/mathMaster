<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api/client'

const loading = ref(false)
const creating = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const users = ref<any[]>([])
const permissionOptions = ref<{ roles: any[]; groups: any[] }>({ roles: [], groups: [] })
const editingUser = ref<any>(null)

const form = reactive({
  username: '',
  display_name: '',
  password: '',
})

const editForm = reactive({
  display_name: '',
  status: 'ACTIVE',
  password: '',
  roles: [] as string[],
  permissions: [] as string[],
})

const roleNameMap = computed(() => {
  const map = new Map<string, string>()
  permissionOptions.value.roles.forEach((role) => map.set(role.code, role.name))
  return map
})

const formatDate = (value?: string | null) => {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

const formatRoles = (roles: string[]) => {
  if (!roles?.length) return '-'
  return roles.map((role) => roleNameMap.value.get(role) || role).join('、')
}

const loadOptions = async () => {
  permissionOptions.value = (await api.get('/users/permission-options')).data
}

const loadUsers = async () => {
  loading.value = true
  try {
    const [usersResponse] = await Promise.all([api.get('/users'), loadOptions()])
    users.value = usersResponse.data
  } finally {
    loading.value = false
  }
}

const createUser = async () => {
  if (!form.username.trim() || !form.password) {
    ElMessage.warning('请输入账号和密码。')
    return
  }
  creating.value = true
  try {
    await api.post('/users', {
      username: form.username.trim(),
      display_name: form.display_name.trim() || form.username.trim(),
      password: form.password,
    })
    form.username = ''
    form.display_name = ''
    form.password = ''
    ElMessage.success('用户已创建，默认角色为学生。')
    await loadUsers()
  } finally {
    creating.value = false
  }
}

const openEdit = (row: any) => {
  editingUser.value = row
  editForm.display_name = row.display_name || row.username
  editForm.status = row.status || 'ACTIVE'
  editForm.password = ''
  editForm.roles = [...(row.roles || [])]
  editForm.permissions = [...(row.direct_permissions || [])]
  dialogVisible.value = true
}

const saveUser = async () => {
  if (!editingUser.value) return
  saving.value = true
  try {
    const userId = editingUser.value.id
    await api.patch(`/users/${userId}`, {
      display_name: editForm.display_name,
      status: editForm.status,
      password: editForm.password || undefined,
    })
    await api.put(`/users/${userId}/roles`, { roles: editForm.roles })
    await api.put(`/users/${userId}/permissions`, { permissions: editForm.permissions })
    ElMessage.success('用户权限已更新。')
    dialogVisible.value = false
    await loadUsers()
  } finally {
    saving.value = false
  }
}

onMounted(loadUsers)
</script>

<template>
  <div class="section-stack">
    <div class="page-header">
      <div>
        <div class="page-title">用户管理</div>
        <div class="page-subtitle">仅超级管理员可访问；新用户默认是学生，后续可按角色和直接权限收紧或放开操作。</div>
      </div>
      <el-button :loading="loading" @click="loadUsers">刷新</el-button>
    </div>

    <section class="panel">
      <div class="section-title">新增用户</div>
      <div class="user-form-grid">
        <el-input v-model="form.username" placeholder="账号" />
        <el-input v-model="form.display_name" placeholder="姓名" />
        <el-input v-model="form.password" type="password" show-password placeholder="初始密码" />
        <el-button type="primary" :loading="creating" @click="createUser">创建用户</el-button>
      </div>
    </section>

    <section class="panel">
      <el-table :data="users" v-loading="loading" empty-text="暂无用户">
        <el-table-column prop="username" label="账号" min-width="130" />
        <el-table-column prop="display_name" label="姓名" min-width="130" />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.status === 'ACTIVE' ? 'success' : 'info'">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="角色" min-width="220">
          <template #default="{ row }">{{ formatRoles(row.roles) }}</template>
        </el-table-column>
        <el-table-column label="直接权限" min-width="220">
          <template #default="{ row }">{{ (row.direct_permissions || []).join('、') || '-' }}</template>
        </el-table-column>
        <el-table-column label="最近登录" min-width="170">
          <template #default="{ row }">{{ formatDate(row.last_login_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-dialog v-model="dialogVisible" title="编辑用户" width="760px">
      <div class="edit-stack">
        <div class="edit-grid">
          <el-input v-model="editForm.display_name" placeholder="姓名" />
          <el-select v-model="editForm.status" placeholder="状态">
            <el-option label="启用" value="ACTIVE" />
            <el-option label="停用" value="DISABLED" />
          </el-select>
          <el-input v-model="editForm.password" type="password" show-password placeholder="重置密码，留空则不修改" />
        </div>

        <div>
          <div class="section-title">角色</div>
          <el-checkbox-group v-model="editForm.roles" class="role-grid">
            <el-checkbox v-for="role in permissionOptions.roles" :key="role.code" :label="role.code">
              {{ role.name }}
              <span class="muted">{{ role.description }}</span>
            </el-checkbox>
          </el-checkbox-group>
        </div>

        <div>
          <div class="section-title">直接权限</div>
          <div class="permission-grid">
            <div v-for="group in permissionOptions.groups" :key="group.code" class="permission-group">
              <div class="permission-group__title">{{ group.name }}</div>
              <el-checkbox-group v-model="editForm.permissions">
                <el-checkbox v-for="permission in group.permissions" :key="permission.code" :label="permission.code">
                  {{ permission.name }}
                </el-checkbox>
              </el-checkbox-group>
            </div>
          </div>
        </div>
      </div>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveUser">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.user-form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  align-items: center;
}

.edit-stack {
  display: grid;
  gap: 20px;
}

.edit-grid {
  display: grid;
  grid-template-columns: 1fr 160px 1fr;
  gap: 12px;
}

.role-grid {
  display: grid;
  gap: 8px;
}

.role-grid :deep(.el-checkbox) {
  height: auto;
  align-items: flex-start;
}

.permission-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 12px;
}

.permission-group {
  border: 1px solid var(--mm-border);
  border-radius: 8px;
  padding: 12px;
  background: var(--mm-surface-soft);
}

.permission-group__title {
  font-weight: 700;
  margin-bottom: 8px;
  color: var(--mm-text);
}

.permission-group :deep(.el-checkbox-group) {
  display: grid;
  gap: 4px;
}

@media (max-width: 760px) {
  .edit-grid {
    grid-template-columns: 1fr;
  }
}
</style>
