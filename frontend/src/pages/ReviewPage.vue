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
  include_deleted: false,
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
}

const selectQuestion = async (questionId: number) => {
  selectedQuestionId.value = questionId
  await router.replace(`/review/${questionId}`)
}

const submitReview = async () => {
  if (!selectedQuestionId.value) return
  await api.post(`/review/questions/${selectedQuestionId.value}`, form.value)
  ElMessage.success('审核结果已保存。')
  await loadQueue()
  await loadDetail()
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
        优先处理低置信度、未匹配答案、缺少定位信息的题目。左侧选择题目，中间查看渲染预览与原 PDF，右侧完成原始文本修正。
      </div>
    </div>
  </div>

  <section class="panel" style="margin-bottom: 18px">
    <el-form inline>
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
      <el-form-item label="包含已删除">
        <el-switch v-model="filters.include_deleted" />
      </el-form-item>
      <el-button @click="loadQueue">筛选</el-button>
    </el-form>
  </section>

  <section class="panel queue-panel" style="margin-bottom: 18px">
    <h3>待审核题目</h3>
    <el-table :data="queue" height="320" @row-click="(row: any) => selectQuestion(row.question_id)">
      <el-table-column prop="paper_title" label="试卷" min-width="220" />
      <el-table-column prop="question_no" label="题号" width="80" />
      <el-table-column prop="match_confidence" label="置信度" width="100" />
      <el-table-column prop="review_note" label="待审核原因" min-width="260" show-overflow-tooltip />
    </el-table>
  </section>

  <div class="review-content-grid">
    <section class="panel preview-panel">
      <h3>渲染预览</h3>
      <div v-if="detail" class="section-stack">
        <div class="surface-note">
          页码：{{ detail.page_start || '-' }} ~ {{ detail.page_end || '-' }}<br />
          待审核原因：{{ detail.review_note || '无' }}
        </div>

        <div v-if="questionImages.length" class="image-stack">
          <div v-for="(image, index) in questionImages" :key="`${index}-${image.src || image.caption || 'img'}`" class="image-card">
            <img v-if="image.src" :src="image.src" :alt="image.caption || `题图 ${index + 1}`" class="image-card__img" />
            <div v-else class="surface-note">图片块：{{ image.caption || '当前题图暂无独立图片地址。' }}</div>
            <div class="muted" style="margin-top: 6px">页码：{{ image.page || '-' }} ｜ {{ image.caption || '无标题' }}</div>
          </div>
        </div>

        <div>
          <h4>题目 Markdown 渲染</h4>
          <div class="surface-note" style="margin-bottom: 10px">这里展示的是 Markdown 渲染结果，不会改写右侧题干原始文本。</div>
          <MarkdownContent :content="detail.assets.question_md" />
        </div>

        <div>
          <h4>答案 Markdown 渲染</h4>
          <MarkdownContent :content="detail.assets.answer_md || '暂无答案片段'" />
        </div>

        <div v-if="answerImages.length" class="image-stack">
          <div v-for="(image, index) in answerImages" :key="`answer-${index}-${image.src || image.caption || 'img'}`" class="image-card">
            <img v-if="image.src" :src="image.src" :alt="image.caption || `答案图 ${index + 1}`" class="image-card__img" />
            <div v-else class="surface-note">图片块：{{ image.caption || '当前答案图暂无独立图片地址。' }}</div>
            <div class="muted" style="margin-top: 6px">页码：{{ image.page || '-' }} ｜ {{ image.caption || '无标题' }}</div>
          </div>
        </div>
      </div>
      <el-empty v-else description="请先从左侧选择题目" />
    </section>

    <section class="panel pdf-panel">
      <div v-if="detail" class="pdf-stack">
        <div class="pdf-card">
          <div class="pdf-card__header">
            <div>
              <h3>原试卷 PDF</h3>
              <div class="muted">{{ paperPdfPath || '缺失试卷原文件' }}</div>
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
              <div class="muted">{{ answerPdfPath || '缺失答案原文件' }}</div>
            </div>
            <a v-if="answerPdfUrl" :href="answerPdfUrl" target="_blank" rel="noreferrer">新标签打开</a>
          </div>
          <iframe v-if="answerPdfUrl" :key="answerPdfUrl" :src="answerPdfUrl" class="pdf-frame" title="原答案 PDF 预览"></iframe>
          <el-empty v-else description="当前没有可预览的答案原文件" />
        </div>
      </div>
      <el-empty v-else description="请先从左侧选择题目" />
    </section>

    <section class="panel edit-panel">
      <h3>人工修正文本</h3>
      <div v-if="detail">
        <el-form label-position="top">
          <el-form-item label="题号">
            <el-input v-model="form.question_no" />
          </el-form-item>
          <el-form-item label="题干">
            <div class="muted" style="margin-bottom: 8px">这里保存的是原始文本，不会写入渲染后的 HTML。</div>
            <el-input v-model="form.stem_text" type="textarea" :rows="6" />
          </el-form-item>
          <el-form-item label="答案">
            <el-input v-model="form.answer_text" type="textarea" :rows="5" />
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
          <el-form-item label="审核备注">
            <el-input v-model="form.review_note" type="textarea" :rows="3" />
          </el-form-item>
          <el-form-item label="操作说明">
            <el-input v-model="form.comment" type="textarea" :rows="3" />
          </el-form-item>
          <el-button type="primary" @click="submitReview">保存审核结果</el-button>
        </el-form>
      </div>
      <el-empty v-else description="请选择一个待审核题目" />
    </section>
  </div>
</template>

<style scoped>
.review-content-grid {
  display: grid;
  grid-template-columns: minmax(360px, 1.1fr) minmax(360px, 1fr) minmax(340px, 0.95fr);
  gap: 18px;
  align-items: start;
}

.preview-panel,
.pdf-panel,
.edit-panel {
  min-height: 720px;
}

.pdf-stack {
  display: grid;
  gap: 16px;
}

.pdf-card {
  display: grid;
  gap: 12px;
}

.pdf-card__header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.pdf-frame {
  width: 100%;
  height: 340px;
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

@media (max-width: 1680px) {
  .review-content-grid {
    grid-template-columns: minmax(360px, 1.1fr) minmax(360px, 1fr);
  }

  .edit-panel {
    grid-column: 1 / 3;
  }
}

@media (max-width: 1280px) {
  .review-content-grid {
    grid-template-columns: 1fr;
  }

  .preview-panel,
  .pdf-panel,
  .edit-panel {
    min-height: auto;
  }
}
</style>
