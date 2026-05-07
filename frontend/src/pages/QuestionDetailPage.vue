<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api/client'
import AnswerVisibilityButton from '../components/AnswerVisibilityButton.vue'
import MarkdownContent from '../components/MarkdownContent.vue'
import QuestionChatPanel from '../components/QuestionChatPanel.vue'

const props = defineProps<{ id: string }>()
const detail = ref<any>(null)
const dictionaryOptions = ref({ knowledgePoints: [] as any[], solutionMethods: [] as any[] })
const tagForm = ref({ knowledge_point_ids: [] as number[], solution_method_ids: [] as number[] })
const savingTags = ref(false)
const answerVisible = ref(false)
const analysisTasks = ref<any[]>([])
const analysisSubmitting = ref(false)
let analysisRefreshTimer: ReturnType<typeof window.setInterval> | null = null

const questionImages = computed(() => detail.value?.assets?.question_images || [])
const answerImages = computed(() => detail.value?.assets?.answer_images || [])
const knowledges = computed(() => detail.value?.knowledges || [])
const methods = computed(() => detail.value?.methods || [])
const parseNameList = (value: unknown) => {
  if (!Array.isArray(value)) return []
  return value
    .map((item: any) => {
      if (item && typeof item === 'object') return String(item.name || item.label || item.title || '').trim()
      return String(item || '').trim()
    })
    .filter(Boolean)
}
const analysisPayload = computed(() => {
  if (!detail.value?.analysis?.analysis_json) return {}
  try {
    return JSON.parse(detail.value.analysis.analysis_json)
  } catch {
    return {}
  }
})
const analysisMajorPoints = computed(() => parseNameList((analysisPayload.value as any).major_knowledge_points))
const analysisMinorPoints = computed(() => parseNameList((analysisPayload.value as any).minor_knowledge_points))
const analysisMethods = computed(() => parseNameList((analysisPayload.value as any).solution_methods))
const activeAnalysisTask = computed(() =>
  analysisTasks.value.find((task) => ['QUEUED', 'RUNNING', 'BLOCKED'].includes(task.status))
)
const failedAnalysisTask = computed(() => analysisTasks.value.find((task) => task.status === 'FAILED'))
const analysisButtonLabel = computed(() => {
  if (activeAnalysisTask.value?.status === 'RUNNING') return '分析中'
  if (activeAnalysisTask.value?.status === 'QUEUED') return '分析已入队'
  if (activeAnalysisTask.value?.status === 'BLOCKED') return '等待分析'
  return '运行题目分析'
})

const load = async () => {
  detail.value = (await api.get(`/questions/${props.id}`)).data
  if (detail.value) {
    localStorage.setItem(
      'mm:last-question',
      JSON.stringify({
        id: detail.value.id,
        questionNo: detail.value.question_no,
        paperId: detail.value.paper_id,
        updatedAt: new Date().toISOString(),
      })
    )
  }
  tagForm.value = {
    knowledge_point_ids: detail.value?.analysis ? knowledges.value.map((item: any) => item.id) : [],
    solution_method_ids: detail.value?.analysis ? methods.value.map((item: any) => item.id) : [],
  }
}

const loadDictionary = async () => {
  dictionaryOptions.value.knowledgePoints = (await api.get('/dictionary/knowledge-points')).data
  dictionaryOptions.value.solutionMethods = (await api.get('/dictionary/solution-methods')).data
}

const loadAnalysisTasks = async () => {
  const { data } = await api.get('/tasks', {
    params: {
      question_id: Number(props.id),
      task_type: 'QUESTION_ANALYSIS',
    },
  })
  analysisTasks.value = data || []
}

const stopAnalysisRefresh = () => {
  if (analysisRefreshTimer) {
    window.clearInterval(analysisRefreshTimer)
    analysisRefreshTimer = null
  }
}

const startAnalysisRefresh = () => {
  if (analysisRefreshTimer) return
  analysisRefreshTimer = window.setInterval(async () => {
    await Promise.all([loadAnalysisTasks(), load()])
    if (!activeAnalysisTask.value) stopAnalysisRefresh()
  }, 2500)
}

const runAnalysis = async () => {
  analysisSubmitting.value = true
  try {
    const { data } = await api.post(`/analysis/questions/${props.id}`)
    if (data.pipeline_task) {
      analysisTasks.value = [
        data.pipeline_task,
        ...analysisTasks.value.filter((task) => task.id !== data.pipeline_task.id),
      ]
    }
    ElMessage.success(data.pipeline_task?.status === 'RUNNING' ? '题目分析正在运行。' : '题目分析已加入队列。')
    startAnalysisRefresh()
  } finally {
    analysisSubmitting.value = false
  }
}

const saveTags = async () => {
  savingTags.value = true
  try {
    detail.value = (
      await api.patch(`/questions/${props.id}/tags`, {
        knowledge_point_ids: tagForm.value.knowledge_point_ids,
        solution_method_ids: tagForm.value.solution_method_ids,
      })
    ).data
    tagForm.value = {
      knowledge_point_ids: (detail.value?.knowledges || []).map((item: any) => item.id),
      solution_method_ids: (detail.value?.methods || []).map((item: any) => item.id),
    }
    ElMessage.success('题目标签已更新')
  } finally {
    savingTags.value = false
  }
}

onMounted(async () => {
  await Promise.all([load(), loadDictionary(), loadAnalysisTasks()])
  if (activeAnalysisTask.value) startAnalysisRefresh()
})

onBeforeUnmount(() => {
  stopAnalysisRefresh()
})
</script>

<template>
  <div v-if="detail" class="section-stack">
    <div class="page-header">
      <div>
        <div class="page-title">题目 {{ detail.question_no }}</div>
        <div class="page-subtitle">
          审核状态：{{ detail.review_status }}。{{ detail.review_note || '当前题目暂无额外审核备注。' }}
        </div>
      </div>
      <el-button
        type="primary"
        :loading="analysisSubmitting || activeAnalysisTask?.status === 'RUNNING'"
        :disabled="Boolean(activeAnalysisTask)"
        @click="runAnalysis"
      >
        {{ analysisButtonLabel }}
      </el-button>
    </div>

    <div class="grid cols-2">
      <section class="panel">
        <h3>题干</h3>
        <div class="detail-markdown-surface">
          <MarkdownContent :content="detail.assets.question_md" />
        </div>

        <div v-if="questionImages.length" class="image-stack">
          <h3>题目图片</h3>
          <div v-for="(image, index) in questionImages" :key="`${index}-${image.storage_key || image.src || image.caption || 'image'}`" class="question-image-card">
            <img v-if="image.src" :src="image.src" :alt="image.caption || `题图 ${index + 1}`" class="question-image" />
            <div v-else class="surface-note">
              图片块：{{ image.caption || '已识别到图片区域，但当前图片文件未落地，暂时无法渲染。' }}
            </div>
            <div class="muted" style="margin-top: 8px">
              页码：{{ image.page ?? '-' }} ｜ {{ image.caption || '无标题' }} ｜ 状态：{{ image.status === 'ready' ? '可显示' : '文件缺失' }}
            </div>
          </div>
        </div>

        <div class="answer-head">
          <h3>答案</h3>
          <AnswerVisibilityButton :visible="answerVisible" @toggle="answerVisible = !answerVisible" />
        </div>
        <template v-if="answerVisible">
          <div class="detail-markdown-surface">
            <MarkdownContent :content="detail.answer?.answer_text || detail.assets.answer_md || '当前题目暂无答案。'" />
          </div>

        <div v-if="answerImages.length" class="image-stack">
          <h3>答案图片</h3>
          <div v-for="(image, index) in answerImages" :key="`answer-${index}-${image.storage_key || image.src || image.caption || 'image'}`" class="question-image-card">
            <img v-if="image.src" :src="image.src" :alt="image.caption || `答案图 ${index + 1}`" class="question-image" />
            <div v-else class="surface-note">
              图片块：{{ image.caption || '已识别到答案图片区域，但当前图片文件未落地，暂时无法渲染。' }}
            </div>
            <div class="muted" style="margin-top: 8px">
              页码：{{ image.page ?? '-' }} ｜ {{ image.caption || '无标题' }} ｜ 状态：{{ image.status === 'ready' ? '可显示' : '文件缺失' }}
            </div>
          </div>
        </div>
        </template>
        <div v-else class="surface-note">答案已隐藏。</div>
      </section>

      <section class="panel">
        <h3>分析结果</h3>
        <div v-if="detail.analysis">
          <div v-if="analysisMajorPoints.length" class="meta-group">
            <div class="meta-label">主要知识点</div>
            <div class="tag-wrap">
              <span v-for="item in analysisMajorPoints" :key="`major-${item}`" class="pill-tag">{{ item }}</span>
            </div>
          </div>
          <div v-if="analysisMinorPoints.length" class="meta-group">
            <div class="meta-label">次级知识点</div>
            <div class="tag-wrap">
              <span v-for="item in analysisMinorPoints" :key="`minor-${item}`" class="pill-tag">{{ item }}</span>
            </div>
          </div>
          <div v-if="analysisMethods.length" class="meta-group">
            <div class="meta-label">推荐解法</div>
            <div class="tag-wrap">
              <span v-for="item in analysisMethods" :key="`analysis-method-${item}`" class="pill-tag">{{ item }}</span>
            </div>
          </div>
          <MarkdownContent :content="detail.analysis.explanation_md" />
        </div>
        <div v-else class="muted">尚未生成分析结果。</div>
        <div v-if="activeAnalysisTask" class="muted" style="margin-top: 12px">
          分析任务状态：{{ activeAnalysisTask.status }}{{ activeAnalysisTask.queue_position ? `，队列第 ${activeAnalysisTask.queue_position} 位` : '' }}
        </div>
        <div v-else-if="failedAnalysisTask" class="error-line" style="margin-top: 12px">
          {{ failedAnalysisTask.error_message || '题目分析失败，请重新运行。' }}
        </div>

        <div class="tag-editor">
          <h3>人工维护标签</h3>
          <div class="muted" style="margin-bottom: 12px">这里直接修改当前题目的知识点与解法标签，保存后会立即写入数据库，并可用于搜索筛选。</div>
          <el-form label-position="top">
            <el-form-item label="知识点标签">
              <el-select v-model="tagForm.knowledge_point_ids" multiple filterable clearable style="width: 100%">
                <el-option
                  v-for="item in dictionaryOptions.knowledgePoints"
                  :key="`kp-${item.id}`"
                  :value="item.id"
                  :label="item.name"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="解法标签">
              <el-select v-model="tagForm.solution_method_ids" multiple filterable clearable style="width: 100%">
                <el-option
                  v-for="item in dictionaryOptions.solutionMethods"
                  :key="`method-${item.id}`"
                  :value="item.id"
                  :label="item.name"
                />
              </el-select>
            </el-form-item>
            <el-button type="primary" :loading="savingTags" @click="saveTags">保存标签</el-button>
          </el-form>
        </div>
      </section>
    </div>

    <QuestionChatPanel :question-id="detail.id" :question-no="detail.question_no" />
  </div>
</template>

<style scoped>
.image-stack {
  display: grid;
  gap: 14px;
  margin: 18px 0;
}

.answer-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.detail-markdown-surface {
  min-width: 0;
  max-width: 100%;
  overflow-x: auto;
  overflow-y: hidden;
}

.detail-markdown-surface :deep(.markdown-content) {
  width: max-content;
  min-width: 100%;
  max-width: none;
  overflow-x: visible;
}

.detail-markdown-surface :deep(.markdown-content p),
.detail-markdown-surface :deep(.markdown-content ul),
.detail-markdown-surface :deep(.markdown-content ol),
.detail-markdown-surface :deep(.markdown-content pre),
.detail-markdown-surface :deep(.markdown-content table),
.detail-markdown-surface :deep(.markdown-content .katex-display),
.detail-markdown-surface :deep(.markdown-content .katex-display > .katex) {
  max-width: none;
  overflow-x: visible;
}

.meta-group {
  margin-bottom: 14px;
}

.meta-label {
  margin-bottom: 8px;
  color: var(--mm-muted);
  font-size: 13px;
}

.tag-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.pill-tag {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 999px;
  background: var(--mm-soft);
  color: var(--mm-ink);
  font-size: 13px;
}

.question-image-card {
  padding: 14px;
  border-radius: 18px;
  background: var(--mm-soft);
}

.question-image {
  width: 100%;
  max-height: 320px;
  object-fit: contain;
  border-radius: 14px;
  background: #fff;
}

.tag-editor {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid rgba(15, 23, 42, 0.08);
}
</style>
