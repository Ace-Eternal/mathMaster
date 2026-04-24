<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
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
    const params: Record<string, any> = {}
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== '' && value !== undefined) params[key] = value
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

const deletePaper = async (paperId: number) => {
  await ElMessageBox.confirm('确认彻底删除这份试卷吗？试卷、答案和已生成的解析/切片文件都会被删除。', '删除试卷', {
    confirmButtonText: '删除',
    cancelButtonText: '取消',
    type: 'warning',
  })
  await api.delete(`/papers/${paperId}`)
  ElMessage.success('试卷及关联文件已删除。')
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
  <div class="section-stack paper-manage-page">
    <div class="page-header">
      <div>
        <div class="page-title">试卷管理</div>
        <div class="page-subtitle">
          在这里查看全部试卷、编辑元数据、修正流程状态、删除试卷，并处理答案绑定。
        </div>
      </div>
      <div class="action-row">
        <el-button :loading="loading" @click="loadPapers">刷新列表</el-button>
      </div>
    </div>

    <section class="panel paper-filter-panel">
      <el-form class="paper-filter-form" label-position="top">
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
        <el-form-item class="paper-filter-actions">
          <el-button type="primary" @click="loadPapers">筛选</el-button>
        </el-form-item>
      </el-form>
    </section>

    <section class="panel paper-table-panel">
      <el-table class="paper-manage-table" :data="papers" v-loading="loading">
        <el-table-column label="试卷信息" min-width="280">
          <template #default="{ row }">
            <div class="paper-title-cell">
              <div class="paper-title-text">{{ row.title }}</div>
              <div class="paper-meta-list">
                <span>年份：{{ row.year || '-' }}</span>
                <span>地区：{{ row.region || '-' }}</span>
                <span>年级：{{ row.grade_level || '-' }}</span>
                <span>学期：{{ row.term || '-' }}</span>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="流程状态" min-width="220">
          <template #default="{ row }">
            <div class="status-stack">
              <span class="status-code">{{ row.status }}</span>
              <span :class="['answer-state', row.answer_sheet?.has_answer ? 'answer-state--ok' : 'answer-state--missing']">
                {{ row.answer_sheet?.has_answer ? '答案已绑定' : '答案缺失' }}
              </span>
              <span class="review-count">待审核 {{ row.pending_review_count || 0 }} 道</span>
            </div>
          </template>
        </el-table-column>
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
        <el-table-column label="操作" width="210">
          <template #default="{ row }">
            <div class="paper-table-actions">
              <RouterLink :to="`/papers/${row.id}`"><el-button text>详情</el-button></RouterLink>
              <el-button text @click="openEdit(row)">编辑</el-button>
              <el-button text type="primary" @click="rerun(row.id)">重跑</el-button>
              <el-button v-if="row.answer_sheet?.has_answer" text type="warning" @click="unbindAnswer(row.id)">解绑答案</el-button>
              <el-button text type="danger" @click="deletePaper(row.id)">删除</el-button>
            </div>
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

<style scoped>
.paper-manage-page,
.paper-filter-panel,
.paper-table-panel {
  min-width: 0;
}

.paper-filter-form {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 16px;
  align-items: end;
}

.paper-filter-form :deep(.el-form-item) {
  min-width: 0;
  margin-bottom: 0;
}

.paper-filter-form :deep(.el-input),
.paper-filter-form :deep(.el-input-number) {
  width: 100%;
}

.paper-filter-actions :deep(.el-form-item__content) {
  align-items: flex-end;
}

.paper-manage-table {
  width: 100%;
}

.paper-manage-table :deep(.el-table__cell) {
  vertical-align: top;
  padding: 16px 0;
}

.paper-title-cell {
  display: grid;
  gap: 10px;
  min-width: 0;
}

.paper-title-text {
  color: var(--mm-text);
  font-size: 15px;
  font-weight: 700;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.paper-meta-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  color: var(--mm-text-soft);
  font-size: 12px;
  line-height: 1.4;
}

.status-stack {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.status-code,
.answer-state,
.review-count {
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.2;
  overflow-wrap: anywhere;
}

.status-code {
  background: rgba(63, 109, 246, 0.08);
  color: #2f56c8;
}

.answer-state {
  background: rgba(242, 153, 74, 0.12);
  color: #a05c0c;
}

.answer-state--ok {
  background: rgba(40, 167, 69, 0.09);
  color: #1d7a37;
}

.answer-state--missing {
  background: rgba(242, 153, 74, 0.12);
  color: #a05c0c;
}

.review-count {
  background: var(--mm-soft);
  color: var(--mm-text-soft);
}

.paper-table-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 8px;
  min-width: 0;
}

.paper-table-actions :deep(.el-button) {
  margin-left: 0;
}

@media (max-width: 820px) {
  .paper-manage-table :deep(.el-table__cell) {
    padding: 14px 0;
  }

  .paper-meta-list,
  .status-stack,
  .paper-table-actions {
    gap: 6px 8px;
  }
}
</style>
