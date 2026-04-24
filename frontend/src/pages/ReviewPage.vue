<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api } from '../api/client'
import MarkdownContent from '../components/MarkdownContent.vue'

const props = defineProps<{ questionId?: string }>()
const router = useRouter()

const queue = ref<any[]>([])
const selectedQuestionId = ref<number | null>(props.questionId ? Number(props.questionId) : null)
const detail = ref<any>(null)
const filters = ref({
  paper_id: undefined as number | undefined,
  review_status: 'PENDING',
  has_answer: undefined as boolean | undefined,
})
const form = ref({
  question_no: '',
  stem_text: '',
  answer_text: '',
  match_status: 'MANUAL_FIXED',
  review_status: 'FIXED',
  review_note: '',
  comment: '',
  reviewer_id: 'local-reviewer',
})
const activeSections = ref(['queue'])

const questionImages = computed(() => detail.value?.assets?.question_images || [])
const answerImages = computed(() => detail.value?.assets?.answer_images || [])
const paperPdfUrl = computed(() => detail.value?.assets?.paper_pdf_url || null)
const answerPdfUrl = computed(() => detail.value?.assets?.answer_pdf_url || null)
const paperPdfPath = computed(() => detail.value?.assets?.paper_pdf_path || null)
const answerPdfPath = computed(() => detail.value?.assets?.answer_pdf_path || null)

const loadQueue = async () => {
  const { data } = await api.get('/review/queue', { params: filters.value })
  queue.value = data
  if (!selectedQuestionId.value && queue.value.length) selectedQuestionId.value = queue.value[0].question_id
}

const loadDetail = async () => {
  if (!selectedQuestionId.value) {
    detail.value = null
    return
  }
  const { data } = await api.get(`/questions/${selectedQuestionId.value}`)
  detail.value = data
  form.value.question_no = data.question_no
  form.value.stem_text = data.stem_text
  form.value.answer_text = data.answer?.answer_text || ''
  form.value.match_status = data.answer?.match_status || 'MANUAL_FIXED'
  form.value.review_status = data.review_status === 'APPROVED' ? 'APPROVED' : 'FIXED'
  form.value.review_note = data.review_note || ''
  localStorage.setItem(
    'mm:last-review-question',
    JSON.stringify({
      questionId: data.id,
      paperId: data.paper_id,
      questionNo: data.question_no,
      updatedAt: new Date().toISOString(),
    })
  )
}

const selectQuestion = async (questionId: number) => {
  selectedQuestionId.value = questionId
  await router.replace(`/review/${questionId}`)
}

const moveSelection = async (direction: 'prev' | 'next') => {
  if (!queue.value.length || !selectedQuestionId.value) return
  const currentIndex = queue.value.findIndex((item) => item.question_id === selectedQuestionId.value)
  if (currentIndex === -1) return
  const nextIndex = direction === 'next' ? currentIndex + 1 : currentIndex - 1
  if (nextIndex < 0 || nextIndex >= queue.value.length) return
  await selectQuestion(queue.value[nextIndex].question_id)
}

const submitReview = async () => {
  if (!selectedQuestionId.value) return
  await api.post(`/review/questions/${selectedQuestionId.value}`, form.value)
  ElMessage.success('审核结果已保存。')
  const currentQuestionId = selectedQuestionId.value
  await loadQueue()
  const nextCandidate = queue.value.find((item) => item.question_id !== currentQuestionId)
  if (nextCandidate) {
    await selectQuestion(nextCandidate.question_id)
  } else {
    await loadDetail()
  }
}

watch(
  () => props.questionId,
  async (value) => {
    selectedQuestionId.value = value ? Number(value) : null
    await loadDetail()
  },
)

onMounted(async () => {
  await loadQueue()
  await loadDetail()
})
</script>

<template>
  <div class="page-header">
    <div>
      <div class="page-title">人工审核队列</div>
      <div class="page-subtitle">
        优先处理低置信度、未匹配答案、缺少定位信息的题目。上方控制流转，下面直接一边查看渲染结果一边修改原始文本，右侧保留原试卷与原答案 PDF 方便比对。
      </div>
    </div>
  </div>

  <section class="panel" style="margin-bottom: 18px">
    <div class="review-toolbar">
      <el-form inline class="review-filter-form">
        <el-form-item label="审核状态">
          <el-select v-model="filters.review_status" style="width: 160px">
            <el-option label="待审核" value="PENDING" />
            <el-option label="已修复" value="FIXED" />
            <el-option label="已通过" value="APPROVED" />
          </el-select>
        </el-form-item>
        <el-form-item label="答案情况">
          <el-select v-model="filters.has_answer" clearable style="width: 160px">
            <el-option label="有答案" :value="true" />
            <el-option label="缺失答案" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item class="review-filter-actions">
          <el-button type="primary" plain @click="loadQueue">筛选</el-button>
        </el-form-item>
      </el-form>
      <div class="action-row review-nav-actions">
        <el-button @click="moveSelection('prev')" :disabled="!selectedQuestionId">上一题</el-button>
        <el-button type="primary" plain @click="moveSelection('next')" :disabled="!selectedQuestionId">下一题</el-button>
      </div>
    </div>
  </section>

  <div class="review-content-grid">
    <section class="panel preview-panel">
      <h3>审阅与修正</h3>
      <div v-if="detail" class="section-stack">
        <div class="surface-note">
          页码：{{ detail.page_start || '-' }} ~ {{ detail.page_end || '-' }}<br />
          待审核原因：{{ detail.review_note || '无' }}
        </div>

        <el-form label-position="top" class="review-edit-form">
          <div class="review-meta-grid">
            <el-form-item label="题号">
              <el-input v-model="form.question_no" />
            </el-form-item>
            <el-form-item label="匹配状态">
              <el-select v-model="form.match_status">
                <el-option label="自动匹配" value="AUTO_MATCHED" />
                <el-option label="人工修正" value="MANUAL_FIXED" />
                <el-option label="未匹配" value="UNMATCHED" />
              </el-select>
            </el-form-item>
            <el-form-item label="审核状态">
              <el-select v-model="form.review_status">
                <el-option label="已修复" value="FIXED" />
                <el-option label="已通过" value="APPROVED" />
                <el-option label="退回待审核" value="PENDING" />
              </el-select>
            </el-form-item>
          </div>

          <div class="edit-preview-block">
            <div class="edit-preview-head">
              <h4>题目</h4>
              <div class="muted">上方修改原始文本，下方实时查看 Markdown 渲染。</div>
            </div>
            <el-form-item label="题干原始文本">
              <el-input v-model="form.stem_text" type="textarea" :rows="7" />
            </el-form-item>
            <div v-if="questionImages.length" class="image-stack">
              <div v-for="(image, index) in questionImages" :key="`${index}-${image.src || image.caption || 'img'}`" class="image-card">
                <img v-if="image.src" :src="image.src" :alt="image.caption || `题图 ${index + 1}`" class="image-card__img" />
                <div v-else class="surface-note">图片块：{{ image.caption || '当前题图暂无独立图片地址。' }}</div>
                <div class="muted" style="margin-top: 6px">页码：{{ image.page || '-' }} ｜ {{ image.caption || '无标题' }}</div>
              </div>
            </div>
            <div class="preview-surface">
              <div class="surface-note" style="margin-bottom: 10px">当前题目渲染效果</div>
              <MarkdownContent :content="form.stem_text || detail.assets.question_md" />
            </div>
          </div>

          <div class="edit-preview-block">
            <div class="edit-preview-head">
              <h4>答案</h4>
              <div class="muted">修改答案文本后，下方会实时显示最终渲染效果。</div>
            </div>
            <el-form-item label="答案原始文本">
              <el-input v-model="form.answer_text" type="textarea" :rows="6" />
            </el-form-item>
            <div v-if="answerImages.length" class="image-stack">
              <div v-for="(image, index) in answerImages" :key="`answer-${index}-${image.src || image.caption || 'img'}`" class="image-card">
                <img v-if="image.src" :src="image.src" :alt="image.caption || `答案图 ${index + 1}`" class="image-card__img" />
                <div v-else class="surface-note">图片块：{{ image.caption || '当前答案图暂无独立图片地址。' }}</div>
                <div class="muted" style="margin-top: 6px">页码：{{ image.page || '-' }} ｜ {{ image.caption || '无标题' }}</div>
              </div>
            </div>
            <div class="preview-surface">
              <div class="surface-note" style="margin-bottom: 10px">当前答案渲染效果</div>
              <MarkdownContent :content="form.answer_text || detail.assets.answer_md || '暂无答案片段'" />
            </div>
          </div>

          <div class="review-meta-grid review-meta-grid--wide">
            <el-form-item label="审核备注">
              <el-input v-model="form.review_note" type="textarea" :rows="3" />
            </el-form-item>
            <el-form-item label="操作说明">
              <el-input v-model="form.comment" type="textarea" :rows="3" />
            </el-form-item>
          </div>

          <el-button type="primary" @click="submitReview">保存审核结果</el-button>
        </el-form>
      </div>
      <el-empty v-else description="请先从左侧选择题目" />
    </section>

    <section class="panel pdf-panel">
      <div v-if="detail" class="pdf-stack">
        <div class="pdf-card">
          <div class="pdf-card__header">
            <div>
              <h3>原试卷 PDF</h3>
              <div class="muted pdf-card__path" :title="paperPdfPath || '缺失试卷原文件'">{{ paperPdfPath || '缺失试卷原文件' }}</div>
            </div>
            <a v-if="paperPdfUrl" :href="paperPdfUrl" target="_blank" rel="noreferrer">新标签打开</a>
          </div>
          <iframe v-if="paperPdfUrl" :key="paperPdfUrl" :src="paperPdfUrl" class="pdf-frame" title="原试卷 PDF 预览"></iframe>
          <el-empty v-else description="当前没有可预览的试卷原文件" />
        </div>

        <div class="pdf-card">
          <div class="pdf-card__header">
            <div>
              <h3>原答案 PDF</h3>
              <div class="muted pdf-card__path" :title="answerPdfPath || '缺失答案原文件'">{{ answerPdfPath || '缺失答案原文件' }}</div>
            </div>
            <a v-if="answerPdfUrl" :href="answerPdfUrl" target="_blank" rel="noreferrer">新标签打开</a>
          </div>
          <iframe v-if="answerPdfUrl" :key="answerPdfUrl" :src="answerPdfUrl" class="pdf-frame" title="原答案 PDF 预览"></iframe>
          <el-empty v-else description="当前没有可预览的答案原文件" />
        </div>
      </div>
      <el-empty v-else description="请先从左侧选择题目" />
    </section>

  </div>

  <section class="panel queue-panel" style="margin-top: 18px">
    <el-collapse v-model="activeSections">
      <el-collapse-item name="queue">
        <template #title>
          <div class="queue-header">
            <span>待审核题目列表</span>
            <span class="muted">共 {{ queue.length }} 题，可展开选择或收起专注当前审阅。</span>
          </div>
        </template>
        <el-table :data="queue" height="320" @row-click="(row: any) => selectQuestion(row.question_id)">
          <el-table-column prop="paper_title" label="试卷" min-width="220" />
          <el-table-column prop="question_no" label="题号" width="80" />
          <el-table-column prop="match_confidence" label="置信度" width="100" />
          <el-table-column prop="review_note" label="待审核原因" min-width="260" show-overflow-tooltip />
        </el-table>
      </el-collapse-item>
    </el-collapse>
  </section>
</template>

<style scoped>
.review-toolbar {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
  flex-wrap: wrap;
}

.review-filter-form {
  flex: 1 1 720px;
  display: flex;
  align-items: flex-end;
  gap: 12px;
  flex-wrap: wrap;
}

.review-filter-form :deep(.el-form-item) {
  margin-right: 0;
  margin-bottom: 0;
}

.review-filter-form :deep(.el-form-item__content) {
  align-items: center;
}

.review-filter-actions {
  padding-top: 22px;
}

.review-nav-actions {
  justify-content: flex-end;
  align-items: flex-end;
  min-height: 54px;
}

.review-content-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr);
  gap: 18px;
  align-items: stretch;
}

.preview-panel,
.pdf-panel {
  min-width: 0;
  min-height: 720px;
  height: 100%;
}

.pdf-panel {
  overflow: hidden;
}

.review-edit-form :deep(.el-form-item) {
  margin-bottom: 16px;
}

.review-meta-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.review-meta-grid--wide {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.edit-preview-block {
  display: grid;
  gap: 12px;
  padding: 18px;
  border-radius: 18px;
  background: rgba(243, 246, 251, 0.72);
}

.edit-preview-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.edit-preview-head h4 {
  margin: 0;
}

.preview-surface {
  padding: 16px;
  border-radius: 16px;
  background: #fff;
  border: 1px solid var(--mm-border);
}

.pdf-stack {
  display: grid;
  grid-template-rows: repeat(2, minmax(0, 1fr));
  gap: 16px;
  height: 100%;
}

.pdf-card {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: 12px;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.pdf-card__header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
  min-width: 0;
}

.pdf-card__header > div {
  min-width: 0;
}

.pdf-card__header a {
  flex: 0 0 auto;
  white-space: nowrap;
  color: var(--mm-primary-deep);
  font-weight: 600;
}

.pdf-card__path {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pdf-frame {
  display: block;
  width: 100%;
  max-width: 100%;
  height: 100%;
  min-height: 520px;
  min-width: 0;
  border: 1px solid var(--mm-border);
  border-radius: 16px;
  background: #fff;
}

.image-stack {
  display: grid;
  gap: 12px;
}

.image-card {
  padding: 12px;
  border-radius: 16px;
  background: var(--mm-soft);
}

.image-card__img {
  width: 100%;
  max-height: 260px;
  object-fit: contain;
  border-radius: 12px;
  background: #fff;
}

.queue-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding-right: 12px;
  gap: 12px;
}

@media (max-width: 1680px) {
  .review-content-grid {
    grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr);
  }
}

@media (max-width: 1280px) {
  .review-content-grid {
    grid-template-columns: 1fr;
  }

  .preview-panel,
  .pdf-panel {
    min-height: auto;
    height: auto;
  }

  .pdf-stack {
    grid-template-rows: none;
    height: auto;
  }

  .pdf-frame {
    height: 420px;
    min-height: 420px;
  }

  .review-toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .review-filter-form {
    align-items: stretch;
  }

  .review-filter-actions {
    padding-top: 0;
  }

  .review-nav-actions {
    justify-content: flex-start;
    min-height: 0;
  }

  .review-meta-grid,
  .review-meta-grid--wide {
    grid-template-columns: 1fr;
  }
}
</style>
