<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api/client'
import ExpandableText from '../components/ExpandableText.vue'

const loading = ref(false)
const saving = ref(false)
const binding = ref(false)
const papers = ref<any[]>([])
const dialogVisible = ref(false)
const editingPaper = ref<any | null>(null)
const answerFile = ref<File | null>(null)

const filters = reactive({
  keyword: '',
  year: undefined as number | undefined,
  region: '',
  grade_level: '',
  term: '',
  status: '',
  has_answer: undefined as boolean | undefined,
  include_deleted: false,
})

const form = reactive({
  title: '',
  year: undefined as number | undefined,
  source: '',
  grade_level: '',
  region: '',
  term: '',
  status: 'RAW',
  has_answer: false,
})

const loadPapers = async () => {
  loading.value = true
  try {
    const params: Record<string, any> = { include_deleted: filters.include_deleted }
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== '' && value !== undefined && key !== 'include_deleted') params[key] = value
    })
    const { data } = await api.get('/papers/manage', { params })
    papers.value = data
  } finally {
    loading.value = false
  }
}

const openEdit = (paper: any) => {
  editingPaper.value = paper
  form.title = paper.title || ''
  form.year = paper.year || undefined
  form.source = paper.source || ''
  form.grade_level = paper.grade_level || ''
  form.region = paper.region || ''
  form.term = paper.term || ''
  form.status = paper.status || 'RAW'
  form.has_answer = Boolean(paper.answer_sheet?.has_answer)
  answerFile.value = null
  dialogVisible.value = true
}

const savePaper = async () => {
  if (!editingPaper.value) return
  saving.value = true
  try {
    await api.patch(`/papers/${editingPaper.value.id}`, {
      title: form.title,
      year: form.year,
      source: form.source || null,
      grade_level: form.grade_level || null,
      region: form.region || null,
      term: form.term || null,
      status: form.status,
      has_answer: form.has_answer,
    })

    if (answerFile.value) {
      const answerForm = new FormData()
      answerForm.append('answer_file', answerFile.value)
      await api.post(`/papers/${editingPaper.value.id}/answer/bind`, answerForm)
    } else if (!form.has_answer) {
      await api.post(`/papers/${editingPaper.value.id}/answer/unbind`)
    }

    ElMessage.success('试卷信息已更新。')
    dialogVisible.value = false
    await loadPapers()
  } finally {
    saving.value = false
  }
}

const softDelete = async (paperId: number) => {
  await api.delete(`/papers/${paperId}`)
  ElMessage.success('试卷已软删除。')
  await loadPapers()
}

const restore = async (paperId: number) => {
  await api.post(`/papers/${paperId}/restore`)
  ElMessage.success('试卷已恢复。')
  await loadPapers()
}

const rerun = async (paperId: number) => {
  await api.post(`/papers/${paperId}/pipeline/run-all`)
  ElMessage.success('已重新运行整理切片。')
  await loadPapers()
}

const unbindAnswer = async (paperId: number) => {
  await api.post(`/papers/${paperId}/answer/unbind`)
  ElMessage.success('答案已解绑。')
  await loadPapers()
}

const bindAnswerOnly = async (paperId: number, file: File | null) => {
  if (!file) {
    ElMessage.warning('请先选择答案 PDF。')
    return
  }
  binding.value = true
  try {
    const formData = new FormData()
    formData.append('answer_file', file)
    await api.post(`/papers/${paperId}/answer/bind`, formData)
    ElMessage.success('答案已重新绑定。')
    await loadPapers()
  } finally {
    binding.value = false
  }
}

onMounted(loadPapers)
</script>

<template>
  <div class="section-stack">
    <div class="page-header">
      <div>
        <div class="page-title">试卷管理</div>
        <div class="page-subtitle">
          在这里查看全部试卷、编辑元数据、修正流程状态、软删除或恢复试卷，并处理答案绑定。
        </div>
      </div>
      <div class="action-row">
        <el-button :loading="loading" @click="loadPapers">刷新列表</el-button>
      </div>
    </div>

    <section class="panel">
      <el-form inline>
        <el-form-item label="标题">
          <el-input v-model="filters.keyword" placeholder="试卷标题关键词" />
        </el-form-item>
        <el-form-item label="年份">
          <el-input-number v-model="filters.year" :min="2000" :max="2100" />
        </el-form-item>
        <el-form-item label="地区">
          <el-input v-model="filters.region" placeholder="如：浙江" />
        </el-form-item>
        <el-form-item label="年级">
          <el-input v-model="filters.grade_level" placeholder="如：高二" />
        </el-form-item>
        <el-form-item label="学期">
          <el-input v-model="filters.term" placeholder="如：期末" />
        </el-form-item>
        <el-form-item label="状态">
          <el-input v-model="filters.status" placeholder="如：RAW / SLICED" />
        </el-form-item>
        <el-form-item label="已删除">
          <el-switch v-model="filters.include_deleted" />
        </el-form-item>
        <el-button type="primary" @click="loadPapers">筛选</el-button>
      </el-form>
    </section>

    <section class="panel">
      <el-table :data="papers" v-loading="loading">
        <el-table-column prop="title" label="标题" min-width="220" />
        <el-table-column prop="year" label="年份" width="90" />
        <el-table-column prop="region" label="地区" width="100" />
        <el-table-column prop="grade_level" label="年级" width="100" />
        <el-table-column prop="term" label="学期" width="100" />
        <el-table-column prop="status" label="状态" width="130" />
        <el-table-column label="答案" width="110">
          <template #default="{ row }">{{ row.answer_sheet?.has_answer ? '已绑定' : '缺失' }}</template>
        </el-table-column>
        <el-table-column prop="pending_review_count" label="待审核" width="100" />
        <el-table-column label="最近错误" min-width="260">
          <template #default="{ row }">
            <ExpandableText
              :text="row.latest_error_message"
              empty-text="暂无错误"
              tone="error"
              :limit="120"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="380" fixed="right">
          <template #default="{ row }">
            <RouterLink :to="`/papers/${row.id}`"><el-button text>详情</el-button></RouterLink>
            <el-button text @click="openEdit(row)">编辑</el-button>
            <el-button text type="primary" @click="rerun(row.id)">重跑</el-button>
            <el-button v-if="row.answer_sheet?.has_answer" text type="warning" @click="unbindAnswer(row.id)">解绑答案</el-button>
            <el-button v-if="!row.is_deleted" text type="danger" @click="softDelete(row.id)">软删除</el-button>
            <el-button v-else text type="success" @click="restore(row.id)">恢复</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-dialog v-model="dialogVisible" width="720px" title="编辑试卷">
      <div class="grid cols-2">
        <el-form-item label="标题">
          <el-input v-model="form.title" />
        </el-form-item>
        <el-form-item label="年份">
          <el-input-number v-model="form.year" :min="2000" :max="2100" style="width: 100%" />
        </el-form-item>
        <el-form-item label="来源">
          <el-input v-model="form.source" />
        </el-form-item>
        <el-form-item label="年级">
          <el-input v-model="form.grade_level" />
        </el-form-item>
        <el-form-item label="地区">
          <el-input v-model="form.region" />
        </el-form-item>
        <el-form-item label="学期">
          <el-input v-model="form.term" />
        </el-form-item>
        <el-form-item label="流程状态">
          <el-select v-model="form.status" style="width: 100%">
            <el-option label="RAW" value="RAW" />
            <el-option label="MINEU_DONE" value="MINEU_DONE" />
            <el-option label="REVIEW_PENDING" value="REVIEW_PENDING" />
            <el-option label="SLICED" value="SLICED" />
            <el-option label="REVIEWED" value="REVIEWED" />
            <el-option label="ARCHIVED" value="ARCHIVED" />
          </el-select>
        </el-form-item>
      </div>

      <div class="surface-note" style="margin-bottom: 16px">
        当前可以直接修正元数据、流程状态和答案绑定状态。如果需要重新上传答案，可在下方重新选择答案 PDF。
      </div>

      <el-form-item label="是否有答案">
        <el-switch v-model="form.has_answer" />
      </el-form-item>
      <el-form-item label="重新绑定答案 PDF">
        <input type="file" accept=".pdf" @change="answerFile = ($event.target as HTMLInputElement).files?.[0] || null" />
      </el-form-item>

      <template #footer>
        <div class="action-row" style="justify-content: flex-end">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="saving" @click="savePaper">保存</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>
