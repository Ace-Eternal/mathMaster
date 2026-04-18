<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../api/client'
import ExpandableText from '../components/ExpandableText.vue'
import PipelineProgress from '../components/PipelineProgress.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { deriveTaskFromPaper } from '../utils/paperStatus'

const props = defineProps<{ id: string }>()
const paper = ref<any>(null)
const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const submitting = ref(false)
const editingQuestionId = ref<number | null>(null)
const form = reactive({
  question_no: '',
  question_type: '',
  stem_text: '',
  answer_text: '',
  page_start: null as number | null,
  page_end: null as number | null,
  review_status: 'PENDING',
  review_note: '',
})
const questionTypeOptions = ['选择题', '多选题', '填空题', '解答题']

const load = async () => {
  paper.value = (await api.get(`/papers/${props.id}`)).data
  if (paper.value) {
    localStorage.setItem(
      'mm:last-paper',
      JSON.stringify({
        id: paper.value.id,
        title: paper.value.title,
        updatedAt: new Date().toISOString(),
      })
    )
  }
}

const task = computed(() => (paper.value ? deriveTaskFromPaper(paper.value) : null))

const resetForm = () => {
  form.question_no = ''
  form.question_type = ''
  form.stem_text = ''
  form.answer_text = ''
  form.page_start = null
  form.page_end = null
  form.review_status = 'PENDING'
  form.review_note = ''
  editingQuestionId.value = null
}

const openCreateDialog = () => {
  dialogMode.value = 'create'
  resetForm()
  dialogVisible.value = true
}

const openEditDialog = async (questionId: number) => {
  dialogMode.value = 'edit'
  resetForm()
  const { data } = await api.get(`/questions/${questionId}`)
  editingQuestionId.value = questionId
  form.question_no = data.question_no || ''
  form.question_type = data.question_type || ''
  form.stem_text = data.stem_text || ''
  form.answer_text = data.answer?.answer_text || ''
  form.page_start = data.page_start ?? null
  form.page_end = data.page_end ?? null
  form.review_status = data.review_status || 'PENDING'
  form.review_note = data.review_note || ''
  dialogVisible.value = true
}

const submitQuestion = async () => {
  submitting.value = true
  try {
    const payload = {
      question_no: form.question_no,
      question_type: form.question_type || null,
      stem_text: form.stem_text,
      answer_text: form.answer_text,
      page_start: form.page_start,
      page_end: form.page_end,
      review_status: form.review_status,
      review_note: form.review_note || null,
    }
    if (dialogMode.value === 'create') {
      await api.post(`/papers/${props.id}/questions`, payload)
      ElMessage.success('题目已新增')
    } else if (editingQuestionId.value !== null) {
      await api.patch(`/papers/${props.id}/questions/${editingQuestionId.value}`, payload)
      ElMessage.success('题目已更新')
    }
    dialogVisible.value = false
    await load()
  } finally {
    submitting.value = false
  }
}

const removeQuestion = async (questionId: number, questionNo: string) => {
  try {
    await ElMessageBox.confirm(`删除题号 ${questionNo} 后，会同步删除对应切片文件，是否继续？`, '确认删除', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await api.delete(`/papers/${props.id}/questions/${questionId}`)
    ElMessage.success('题目已删除')
    await load()
  } catch {
    // 用户取消删除时保持静默
  }
}

onMounted(load)
</script>

<template>
  <div v-if="paper && task" class="section-stack">
    <div class="page-header">
      <div>
        <div class="page-title">{{ paper.title }}</div>
        <div class="page-subtitle">
          这里汇总当前试卷的文件信息、流程状态、MineU 转换记录和切片结果，便于快速判断是否需要继续审核或重跑。
        </div>
      </div>
    </div>

    <div class="grid cols-2">
      <section class="panel">
        <h3>试卷概览</h3>
        <div class="detail-list">
          <div class="detail-row"><span>状态</span><StatusBadge :stage="task.stage" /></div>
          <div class="detail-row"><span>年份</span><strong>{{ paper.year || '未识别' }}</strong></div>
          <div class="detail-row"><span>年级</span><strong>{{ paper.grade_level || '未识别' }}</strong></div>
          <div class="detail-row"><span>地区</span><strong>{{ paper.region || '未填写' }}</strong></div>
          <div class="detail-row"><span>学期</span><strong>{{ paper.term || '未填写' }}</strong></div>
        </div>

        <div style="height: 18px" />
        <PipelineProgress :percentage="task.progress" />
        <div v-if="task.note" class="surface-note" style="margin-top: 16px">{{ task.note }}</div>
        <div v-if="task.errorSummary" class="surface-note detail-error" style="margin-top: 16px">
          <ExpandableText :text="task.errorSummary" tone="error" :limit="140" />
        </div>
      </section>

      <section class="panel">
        <h3>原始文件</h3>
        <div class="detail-list">
          <div class="detail-block">
            <div class="detail-label">试卷 PDF</div>
            <div class="mono detail-path">{{ paper.paper_pdf_path }}</div>
          </div>
          <div class="detail-block">
            <div class="detail-label">答案 PDF</div>
            <div class="mono detail-path">{{ paper.answer_sheet?.answer_pdf_path || '缺失答案文件' }}</div>
          </div>
          <div class="detail-row"><span>答案状态</span><strong>{{ paper.answer_sheet?.has_answer ? '已匹配' : '缺失答案' }}</strong></div>
          <div class="detail-row"><span>待审核题数</span><strong>{{ paper.pending_review_count }}</strong></div>
          <div class="detail-row"><span>切题数量</span><strong>{{ paper.questions?.length || 0 }}</strong></div>
        </div>
      </section>
    </div>

    <section class="panel">
      <h3>MineU 转换任务</h3>
      <el-table :data="paper.conversion_jobs || []">
        <el-table-column prop="job_type" label="任务类型" width="120" />
        <el-table-column prop="status" label="状态" width="120" />
        <el-table-column prop="markdown_path" label="Markdown 路径" min-width="240" />
        <el-table-column prop="json_path" label="JSON 路径" min-width="240" />
        <el-table-column label="错误信息" min-width="240">
          <template #default="{ row }">
            <ExpandableText :text="row.error_message" empty-text="暂无错误" tone="error" :limit="120" />
          </template>
        </el-table-column>
      </el-table>
    </section>

    <section class="panel">
      <div class="panel-header">
        <h3>切片结果</h3>
        <el-button type="primary" @click="openCreateDialog">新增题目</el-button>
      </div>
      <el-table :data="paper.questions || []">
        <el-table-column prop="question_no" label="题号" width="100" />
        <el-table-column prop="question_type" label="题型" width="120" />
        <el-table-column prop="stem_text" label="题干" min-width="380" />
        <el-table-column prop="review_status" label="审核状态" width="140" />
        <el-table-column prop="review_note" label="提示信息" min-width="220" />
        <el-table-column label="操作" width="240">
          <template #default="{ row }">
            <RouterLink :to="`/questions/${row.id}`"><el-button text>查看</el-button></RouterLink>
            <el-button text type="primary" @click="openEditDialog(row.id)">编辑</el-button>
            <RouterLink :to="`/review/${row.id}`"><el-button text type="warning">审核</el-button></RouterLink>
            <el-button text type="danger" @click="removeQuestion(row.id, row.question_no)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-dialog
      v-model="dialogVisible"
      :title="dialogMode === 'create' ? '新增题目' : '编辑题目'"
      width="760px"
      destroy-on-close
    >
      <el-form label-position="top">
        <div class="question-form-grid">
          <el-form-item label="题号">
            <el-input v-model="form.question_no" />
          </el-form-item>
          <el-form-item label="题型">
            <el-select v-model="form.question_type" placeholder="请选择题型" clearable style="width: 100%">
              <el-option v-for="item in questionTypeOptions" :key="item" :label="item" :value="item" />
            </el-select>
          </el-form-item>
          <el-form-item label="起始页码">
            <el-input-number v-model="form.page_start" :min="0" controls-position="right" style="width: 100%" />
          </el-form-item>
          <el-form-item label="结束页码">
            <el-input-number v-model="form.page_end" :min="0" controls-position="right" style="width: 100%" />
          </el-form-item>
        </div>
        <el-form-item label="题干">
          <el-input v-model="form.stem_text" type="textarea" :rows="6" />
        </el-form-item>
        <el-form-item label="答案">
          <el-input v-model="form.answer_text" type="textarea" :rows="6" />
        </el-form-item>
        <div class="question-form-grid">
          <el-form-item label="审核状态">
            <el-select v-model="form.review_status" style="width: 100%">
              <el-option label="PENDING" value="PENDING" />
              <el-option label="APPROVED" value="APPROVED" />
              <el-option label="FIXED" value="FIXED" />
            </el-select>
          </el-form-item>
          <el-form-item label="审核备注">
            <el-input v-model="form.review_note" />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitQuestion">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.detail-list {
  display: grid;
  gap: 14px;
}

.detail-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  color: var(--mm-text-soft);
}

.detail-row strong {
  color: var(--mm-text);
}

.detail-block {
  padding: 14px 16px;
  background: var(--mm-soft);
  border-radius: 16px;
}

.detail-label {
  color: var(--mm-text-soft);
  font-size: 13px;
  margin-bottom: 8px;
}

.detail-path {
  color: var(--mm-text);
  word-break: break-all;
}

.detail-error {
  color: #b42318;
  background: rgba(254, 242, 242, 0.92);
}

.question-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}
</style>
