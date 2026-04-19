<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../api/client'

const knowledgePoints = ref<any[]>([])
const solutionMethods = ref<any[]>([])
const knowledgeForm = ref({ id: null as number | null, name: '', level: 1, parent_id: null as number | null, sort_no: 0 })
const methodForm = ref({ id: null as number | null, name: '', description: '' })

const parentOptions = computed(() => knowledgePoints.value.filter((item) => item.level === 1))

const load = async () => {
  knowledgePoints.value = (await api.get('/dictionary/knowledge-points')).data
  solutionMethods.value = (await api.get('/dictionary/solution-methods')).data
}

const resetKnowledgeForm = () => {
  knowledgeForm.value = { id: null, name: '', level: 1, parent_id: null, sort_no: 0 }
}

const resetMethodForm = () => {
  methodForm.value = { id: null, name: '', description: '' }
}

const saveKnowledge = async () => {
  const payload = {
    name: knowledgeForm.value.name,
    level: knowledgeForm.value.level,
    parent_id: knowledgeForm.value.level === 2 ? knowledgeForm.value.parent_id : null,
    sort_no: knowledgeForm.value.sort_no,
  }
  if (knowledgeForm.value.id) {
    await api.patch(`/dictionary/knowledge-points/${knowledgeForm.value.id}`, payload)
    ElMessage.success('知识点已更新')
  } else {
    await api.post('/dictionary/knowledge-points', payload)
    ElMessage.success('知识点已新增')
  }
  resetKnowledgeForm()
  await load()
}

const editKnowledge = (item: any) => {
  knowledgeForm.value = {
    id: item.id,
    name: item.name,
    level: item.level,
    parent_id: item.parent_id,
    sort_no: item.sort_no ?? 0,
  }
}

const deleteKnowledge = async (item: any) => {
  await ElMessageBox.confirm(`确认删除知识点“${item.name}”吗？相关题目标记也会一并移除。`, '删除知识点', {
    type: 'warning',
  })
  await api.delete(`/dictionary/knowledge-points/${item.id}`)
  ElMessage.success('知识点已删除')
  if (knowledgeForm.value.id === item.id) resetKnowledgeForm()
  await load()
}

const saveMethod = async () => {
  const payload = {
    name: methodForm.value.name,
    description: methodForm.value.description || null,
  }
  if (methodForm.value.id) {
    await api.patch(`/dictionary/solution-methods/${methodForm.value.id}`, payload)
    ElMessage.success('解法已更新')
  } else {
    await api.post('/dictionary/solution-methods', payload)
    ElMessage.success('解法已新增')
  }
  resetMethodForm()
  await load()
}

const editMethod = (item: any) => {
  methodForm.value = {
    id: item.id,
    name: item.name,
    description: item.description || '',
  }
}

const deleteMethod = async (item: any) => {
  await ElMessageBox.confirm(`确认删除解法“${item.name}”吗？相关题目标记也会一并移除。`, '删除解法', {
    type: 'warning',
  })
  await api.delete(`/dictionary/solution-methods/${item.id}`)
  ElMessage.success('解法已删除')
  if (methodForm.value.id === item.id) resetMethodForm()
  await load()
}

onMounted(load)
</script>

<template>
  <div class="page-header">
    <div>
      <div class="page-title">知识点与方法</div>
      <div class="muted">这里维护全局标签字典。题目分析会写入这些标签，搜索页和题目详情页也会直接复用。</div>
    </div>
  </div>

  <div class="grid cols-2">
    <section class="panel">
      <h3>知识点体系</h3>
      <el-form label-position="top">
        <el-form-item label="名称">
          <el-input v-model="knowledgeForm.name" placeholder="例如：概率与统计" />
        </el-form-item>
        <el-form-item label="层级">
          <el-select v-model="knowledgeForm.level" style="width: 100%">
            <el-option :value="1" label="大知识点" />
            <el-option :value="2" label="小知识点" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="knowledgeForm.level === 2" label="父知识点">
          <el-select v-model="knowledgeForm.parent_id" clearable style="width: 100%">
            <el-option v-for="item in parentOptions" :key="item.id" :value="item.id" :label="item.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="knowledgeForm.sort_no" :min="0" style="width: 100%" />
        </el-form-item>
        <div class="action-row">
          <el-button type="primary" @click="saveKnowledge">{{ knowledgeForm.id ? '保存修改' : '新增知识点' }}</el-button>
          <el-button v-if="knowledgeForm.id" @click="resetKnowledgeForm">取消编辑</el-button>
        </div>
      </el-form>
      <el-table :data="knowledgePoints" style="margin-top: 16px">
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="level" label="层级" width="90" />
        <el-table-column prop="parent_id" label="父级ID" width="90" />
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button link type="primary" @click="editKnowledge(row)">编辑</el-button>
            <el-button link type="danger" @click="deleteKnowledge(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <section class="panel">
      <h3>解题方法</h3>
      <el-form label-position="top">
        <el-form-item label="名称"><el-input v-model="methodForm.name" placeholder="例如：概率计算" /></el-form-item>
        <el-form-item label="说明"><el-input v-model="methodForm.description" type="textarea" :rows="3" /></el-form-item>
        <div class="action-row">
          <el-button type="primary" @click="saveMethod">{{ methodForm.id ? '保存修改' : '新增解法' }}</el-button>
          <el-button v-if="methodForm.id" @click="resetMethodForm">取消编辑</el-button>
        </div>
      </el-form>
      <el-table :data="solutionMethods" style="margin-top: 16px">
        <el-table-column prop="name" label="方法" />
        <el-table-column prop="description" label="说明" />
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button link type="primary" @click="editMethod(row)">编辑</el-button>
            <el-button link type="danger" @click="deleteMethod(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>
  </div>
</template>

<style scoped>
.action-row {
  display: flex;
  gap: 12px;
}
</style>
