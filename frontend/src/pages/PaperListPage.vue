<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api/client'
import TaskOverviewCards from '../components/TaskOverviewCards.vue'
import TaskStatusList from '../components/TaskStatusList.vue'
import { deriveTaskFromPaper, sortTaskItems, summarizeTasks, type TaskListItem } from '../utils/paperStatus'

type ImportItem = {
  paper_filename: string
  answer_filename: string | null
  pair_key: string
  paper_id: number | null
  pair_status: string
  has_answer: boolean
}

const loading = ref(false)
const singleUploadLoading = ref(false)
const importLoading = ref(false)
const batchRunning = ref(false)
const papers = ref<any[]>([])
const latestImportItems = ref<ImportItem[]>([])
const latestImportSummary = ref<any | null>(null)
const transientTasks = ref<TaskListItem[]>([])

const uploadForm = ref({
  title: '',
  source: '',
  region: '',
  grade_level: '',
  term: ''
})

const paperFile = ref<File | null>(null)
const answerFile = ref<File | null>(null)
const folderPaperFiles = ref<File[]>([])
const folderAnswerFiles = ref<File[]>([])

const persistTransientTask = (task: TaskListItem) => {
  transientTasks.value = [task, ...transientTasks.value.filter((item) => item.id !== task.id)]
}

const removeTransientTask = (taskId: string) => {
  transientTasks.value = transientTasks.value.filter((item) => item.id !== taskId)
}

const errorMessage = (error: any, fallback: string) => {
  const detail = error?.response?.data?.detail
  if (Array.isArray(detail)) return detail.map((item) => item.msg || JSON.stringify(item)).join('；')
  if (typeof detail === 'string') return detail
  return error?.message || fallback
}

const loadPapers = async () => {
  loading.value = true
  try {
    const { data } = await api.get('/papers')
    papers.value = data
  } finally {
    loading.value = false
  }
}

const submitSingleUpload = async () => {
  if (!paperFile.value) {
    ElMessage.error('请选择试卷 PDF。')
    return
  }
  const selectedPaperFile = paperFile.value

  const transientId = `single-${Date.now()}`
  persistTransientTask({
    id: transientId,
    paperId: null,
    title: uploadForm.value.title || selectedPaperFile.name,
    stage: '上传中',
    progress: 18,
    hasAnswer: Boolean(answerFile.value),
    mineuSuccess: false,
    questionCount: 0,
    pendingReviewCount: 0,
    updatedAt: new Date().toISOString(),
    errorSummary: null,
    note: answerFile.value ? '正在上传试卷与答案文件。' : '正在上传试卷文件，暂未附带答案。',
    sourceLabel: '单份上传',
    isTransient: true
  })

  singleUploadLoading.value = true
  try {
    const form = new FormData()
    Object.entries(uploadForm.value).forEach(([key, value]) => {
      if (value) form.append(key, value)
    })
    form.append('paper_file', selectedPaperFile, selectedPaperFile.name)
    if (answerFile.value) form.append('answer_file', answerFile.value, answerFile.value.name)
    await api.post('/papers/upload', form)
    removeTransientTask(transientId)
    ElMessage.success('上传成功，任务已进入待运行状态。')
    paperFile.value = null
    answerFile.value = null
    await loadPapers()
  } catch (error: any) {
    const message = errorMessage(error, '上传失败，请重试。')
    persistTransientTask({
      id: transientId,
      paperId: null,
      title: uploadForm.value.title || selectedPaperFile.name,
      stage: '系统异常',
      progress: 100,
      hasAnswer: Boolean(answerFile.value),
      mineuSuccess: false,
      questionCount: 0,
      pendingReviewCount: 0,
      updatedAt: new Date().toISOString(),
      errorSummary: message,
      note: null,
      sourceLabel: '单份上传',
      isTransient: true
    })
    ElMessage.error(message)
  } finally {
    singleUploadLoading.value = false
  }
}

const submitFolderImport = async () => {
  if (!folderPaperFiles.value.length) {
    ElMessage.error('请至少选择一个试卷文件夹。')
    return
  }

  const transientId = `folder-${Date.now()}`
  persistTransientTask({
    id: transientId,
    paperId: null,
    title: `批量导入 ${folderPaperFiles.value.length} 份试卷`,
    stage: '上传中',
    progress: 24,
    hasAnswer: folderAnswerFiles.value.length > 0,
    mineuSuccess: false,
    questionCount: 0,
    pendingReviewCount: 0,
    updatedAt: new Date().toISOString(),
    errorSummary: null,
    note: `正在上传文件夹，当前试卷 ${folderPaperFiles.value.length} 份，答案 ${folderAnswerFiles.value.length} 份。`,
    sourceLabel: '文件夹导入',
    isTransient: true
  })

  importLoading.value = true
  try {
    const form = new FormData()
    folderPaperFiles.value.forEach((file) => form.append('paper_files', file, file.webkitRelativePath || file.name))
    folderAnswerFiles.value.forEach((file) => form.append('answer_files', file, file.webkitRelativePath || file.name))
    const { data } = await api.post('/papers/import-folders', form)
    latestImportItems.value = data.items
    latestImportSummary.value = data.import_job.summary
    removeTransientTask(transientId)
    ElMessage.success('文件夹导入成功，已完成自动配对。')
    await loadPapers()
  } catch (error: any) {
    const message = errorMessage(error, '文件夹导入失败，请检查文件后重试。')
    persistTransientTask({
      id: transientId,
      paperId: null,
      title: `批量导入 ${folderPaperFiles.value.length} 份试卷`,
      stage: '系统异常',
      progress: 100,
      hasAnswer: folderAnswerFiles.value.length > 0,
      mineuSuccess: false,
      questionCount: 0,
      pendingReviewCount: 0,
      updatedAt: new Date().toISOString(),
      errorSummary: message,
      note: null,
      sourceLabel: '文件夹导入',
      isTransient: true
    })
    ElMessage.error(message)
  } finally {
    importLoading.value = false
  }
}

const runPipeline = async (paperId: number) => {
  const paper = papers.value.find((item) => item.id === paperId)
  persistTransientTask({
    id: `run-${paperId}`,
    paperId,
    title: paper?.title || `试卷 #${paperId}`,
    stage: 'MineU解析中',
    progress: 20,
    hasAnswer: Boolean(paper?.answer_sheet?.has_answer),
    mineuSuccess: false,
    questionCount: paper?.questions?.length || 0,
    pendingReviewCount: paper?.pending_review_count || 0,
    updatedAt: new Date().toISOString(),
    errorSummary: null,
    note: '已手动触发流程，准备执行 MineU 解析。',
    sourceLabel: '试卷任务',
    isTransient: true
  })

  try {
    await api.post(`/papers/${paperId}/pipeline/run-all`)
    removeTransientTask(`run-${paperId}`)
    ElMessage.success('整理切片完成。')
    await loadPapers()
  } catch (error: any) {
    const message = errorMessage(error, '流水线执行失败。')
    persistTransientTask({
      id: `run-${paperId}`,
      paperId,
      title: paper?.title || `试卷 #${paperId}`,
      stage: '系统异常',
      progress: 100,
      hasAnswer: Boolean(paper?.answer_sheet?.has_answer),
      mineuSuccess: false,
      questionCount: paper?.questions?.length || 0,
      pendingReviewCount: paper?.pending_review_count || 0,
      updatedAt: new Date().toISOString(),
      errorSummary: message,
      note: null,
      sourceLabel: '试卷任务',
      isTransient: true
    })
    ElMessage.error(message)
  }
}

const runImportedBatch = async () => {
  const paperIds = latestImportItems.value.map((item) => item.paper_id).filter(Boolean) as number[]
  if (!paperIds.length) {
    ElMessage.warning('当前没有可执行的导入记录。')
    return
  }

  batchRunning.value = true
  paperIds.forEach((paperId) => {
    const item = latestImportItems.value.find((entry) => entry.paper_id === paperId)
    persistTransientTask({
      id: `run-${paperId}`,
      paperId,
      title: item?.paper_filename || `试卷 #${paperId}`,
      stage: 'MineU解析中',
      progress: 20,
      hasAnswer: Boolean(item?.has_answer),
      mineuSuccess: false,
      questionCount: 0,
      pendingReviewCount: 0,
      updatedAt: new Date().toISOString(),
      errorSummary: null,
      note: '已手动触发批量流程，准备执行 MineU 解析。',
      sourceLabel: '批量任务',
      isTransient: true
    })
  })

  try {
    await api.post('/papers/batch/run', { paper_ids: paperIds })
    paperIds.forEach((paperId) => removeTransientTask(`run-${paperId}`))
    ElMessage.success('本次导入任务已完成批量整理。')
    await loadPapers()
  } catch (error: any) {
    const message = errorMessage(error, '批量任务执行失败。')
    paperIds.forEach((paperId) => {
      const item = latestImportItems.value.find((entry) => entry.paper_id === paperId)
      persistTransientTask({
        id: `run-${paperId}`,
        paperId,
        title: item?.paper_filename || `试卷 #${paperId}`,
        stage: '系统异常',
        progress: 100,
        hasAnswer: Boolean(item?.has_answer),
        mineuSuccess: false,
        questionCount: 0,
        pendingReviewCount: 0,
        updatedAt: new Date().toISOString(),
        errorSummary: message,
        note: null,
        sourceLabel: '批量任务',
        isTransient: true
      })
    })
    ElMessage.error(message)
  } finally {
    batchRunning.value = false
  }
}

const taskItems = computed(() => {
  const paperTasks = papers.value.map((paper) => deriveTaskFromPaper(paper))
  const withoutShadowedTransient = transientTasks.value.filter(
    (task) => !task.paperId || !paperTasks.some((paperTask) => paperTask.paperId === task.paperId)
  )
  return sortTaskItems([...withoutShadowedTransient, ...paperTasks])
})

const summary = computed(() => summarizeTasks(taskItems.value))

onMounted(loadPapers)
</script>

<template>
  <div class="section-stack">
    <div class="page-header">
      <div>
        <div class="page-title">试卷任务中心</div>
        <div class="page-subtitle">
          在一个页面里完成试卷上传、文件夹导入和导入摘要查看。任务状态与错误摘要会集中展示在上传区域下方。
        </div>
      </div>
      <div class="action-row">
        <el-button :loading="loading" @click="loadPapers">刷新任务</el-button>
      </div>
    </div>

    <div class="grid cols-2">
      <section class="panel">
        <div class="section-head">
          <div>
            <div class="section-title">单份上传</div>
            <div class="muted">适合手动补录单份试卷与答案，上传后可立即进入任务状态列表。</div>
          </div>
        </div>

        <el-form label-position="top">
          <el-form-item label="试卷标题">
            <el-input v-model="uploadForm.title" placeholder="可留空，默认使用文件名" />
          </el-form-item>

          <div class="grid cols-2">
            <el-form-item label="来源">
              <el-input v-model="uploadForm.source" placeholder="如：联考、学校、自有整理" />
            </el-form-item>
            <el-form-item label="地区">
              <el-input v-model="uploadForm.region" placeholder="如：浙江、上海、江苏" />
            </el-form-item>
          </div>

          <div class="grid cols-2">
            <el-form-item label="年级">
              <el-input v-model="uploadForm.grade_level" placeholder="如：高一 / 高二 / 高三" />
            </el-form-item>
            <el-form-item label="学期">
              <el-input v-model="uploadForm.term" placeholder="如：期中 / 期末 / 春季" />
            </el-form-item>
          </div>

          <el-form-item label="试卷 PDF">
            <input type="file" accept=".pdf,application/pdf" @change="paperFile = ($event.target as HTMLInputElement).files?.[0] || null" />
          </el-form-item>
          <el-form-item label="答案 PDF">
            <input type="file" accept=".pdf,application/pdf" @change="answerFile = ($event.target as HTMLInputElement).files?.[0] || null" />
          </el-form-item>

          <div class="action-row">
            <el-button type="primary" :loading="singleUploadLoading" @click="submitSingleUpload">上传单份试卷</el-button>
          </div>
        </el-form>
      </section>

      <section class="panel">
        <div class="section-head">
          <div>
            <div class="section-title">文件夹批量导入</div>
            <div class="muted">分别选择试卷目录和答案目录，系统按文件名自动配对并生成导入摘要。</div>
          </div>
        </div>

        <el-form label-position="top">
          <el-form-item label="试卷文件夹">
            <input
              type="file"
              multiple
              webkitdirectory
              directory
              accept=".pdf,application/pdf"
              @change="folderPaperFiles = Array.from(($event.target as HTMLInputElement).files || [])"
            />
          </el-form-item>

          <el-form-item label="答案文件夹">
            <input
              type="file"
              multiple
              webkitdirectory
              directory
              accept=".pdf,application/pdf"
              @change="folderAnswerFiles = Array.from(($event.target as HTMLInputElement).files || [])"
            />
          </el-form-item>

          <div class="surface-note">
            当前已选试卷 {{ folderPaperFiles.length }} 份，答案 {{ folderAnswerFiles.length }} 份。
          </div>

          <div style="height: 16px" />

          <div class="action-row">
            <el-button type="primary" :loading="importLoading" @click="submitFolderImport">导入并自动配对</el-button>
            <el-button :loading="batchRunning" @click="runImportedBatch">运行本次导入任务</el-button>
          </div>
        </el-form>
      </section>
    </div>

    <section v-if="latestImportSummary" class="panel">
      <div class="section-head">
        <div>
          <div class="section-title">最近一次导入摘要</div>
          <div class="muted">
            已配对 {{ latestImportSummary.paired_count }} 份，缺失答案 {{ latestImportSummary.missing_answer_count }} 份，孤立答案 {{ latestImportSummary.orphan_answer_count }} 份。
          </div>
        </div>
      </div>

      <el-table :data="latestImportItems">
        <el-table-column prop="paper_filename" label="试卷文件" min-width="240" />
        <el-table-column prop="answer_filename" label="答案文件" min-width="240" />
        <el-table-column prop="pair_status" label="配对状态" width="140" />
        <el-table-column label="答案情况" width="120">
          <template #default="{ row }">
            {{ row.has_answer ? '已匹配' : '缺失' }}
          </template>
        </el-table-column>
        <el-table-column label="查看" width="120">
          <template #default="{ row }">
            <RouterLink v-if="row.paper_id" :to="`/papers/${row.paper_id}`">详情</RouterLink>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <TaskOverviewCards :summary="summary" />
    <TaskStatusList :items="taskItems" :loading="loading" @rerun="runPipeline" />
  </div>
</template>

<style scoped>
.section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.section-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--mm-text);
  margin-bottom: 6px;
}

input[type='file'] {
  width: 100%;
  border: 1px dashed var(--mm-border-strong);
  border-radius: 16px;
  background: rgba(247, 249, 252, 0.78);
  padding: 14px;
  color: var(--mm-text-soft);
}
</style>
