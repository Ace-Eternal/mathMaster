<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api/client'

const knowledgePoints = ref<any[]>([])
const solutionMethods = ref<any[]>([])
const knowledgeForm = ref({ name: '', level: 1, parent_id: null as number | null })
const methodForm = ref({ name: '', description: '' })

const load = async () => {
  knowledgePoints.value = (await api.get('/dictionary/knowledge-points')).data
  solutionMethods.value = (await api.get('/dictionary/solution-methods')).data
}

const createKnowledge = async () => {
  await api.post('/dictionary/knowledge-points', knowledgeForm.value)
  knowledgeForm.value = { name: '', level: 1, parent_id: null }
  await load()
}

const createMethod = async () => {
  await api.post('/dictionary/solution-methods', methodForm.value)
  methodForm.value = { name: '', description: '' }
  await load()
}

onMounted(load)
</script>

<template>
  <div class="page-header">
    <div>
      <div class="page-title">知识点与方法</div>
      <div class="muted">一期先提供后台 CRUD 能力，为自动分析和人工修正提供字典基础。</div>
    </div>
  </div>

  <div class="grid cols-2">
    <section class="panel">
      <h3>知识点体系</h3>
      <el-form inline>
        <el-input v-model="knowledgeForm.name" placeholder="名称" />
        <el-select v-model="knowledgeForm.level" style="width: 120px">
          <el-option :value="1" label="大知识点" />
          <el-option :value="2" label="小知识点" />
        </el-select>
        <el-button type="primary" @click="createKnowledge">新增</el-button>
      </el-form>
      <el-table :data="knowledgePoints" style="margin-top: 16px">
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="level" label="层级" width="100" />
      </el-table>
    </section>
    <section class="panel">
      <h3>解题方法</h3>
      <el-form label-position="top">
        <el-form-item label="名称"><el-input v-model="methodForm.name" /></el-form-item>
        <el-form-item label="说明"><el-input v-model="methodForm.description" type="textarea" :rows="3" /></el-form-item>
        <el-button type="primary" @click="createMethod">新增</el-button>
      </el-form>
      <el-table :data="solutionMethods" style="margin-top: 16px">
        <el-table-column prop="name" label="方法" />
        <el-table-column prop="description" label="说明" />
      </el-table>
    </section>
  </div>
</template>
