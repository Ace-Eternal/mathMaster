<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api/client'
import AnswerVisibilityButton from '../components/AnswerVisibilityButton.vue'
import DiceIcon from '../components/DiceIcon.vue'
import MarkdownContent from '../components/MarkdownContent.vue'
import PracticeStatusBadge from '../components/PracticeStatusBadge.vue'

const loading = ref(false)
const stateSaving = ref(false)
const answerVisible = ref(false)
const current = ref<any>(null)
const dictionaryOptions = ref({ knowledgePoints: [] as any[], solutionMethods: [] as any[] })
const chatMessage = ref('')
const chatSession = ref<any>(null)
const chatSending = ref(false)
const chatModels = ref<any[]>([])
const selectedModel = ref<string | null>(null)

const filters = reactive({
  grade_levels: [] as string[],
  knowledge_point_ids: [] as number[],
  solution_method_ids: [] as number[],
  question_type: '',
  has_answer: null as boolean | null,
})
const practiceStatusOptions = [
  { value: 'NOT_STARTED', label: '未解决' },
  { value: 'IN_PROGRESS', label: '解决中' },
  { value: 'SOLVED', label: '已解决' },
]

const question = computed(() => current.value?.question)
const practiceState = computed(() => current.value?.practice_state)
const answerContent = computed(() => question.value?.answer?.answer_text || question.value?.assets?.answer_md || '')
const questionImages = computed(() => question.value?.assets?.question_images || [])
const answerImages = computed(() => question.value?.assets?.answer_images || [])
const hasActiveFilters = computed(
  () =>
    filters.grade_levels.length > 0 ||
    filters.knowledge_point_ids.length > 0 ||
    filters.solution_method_ids.length > 0 ||
    Boolean(filters.question_type) ||
    filters.has_answer !== null
)

const loadDictionary = async () => {
  const [knowledgeResponse, methodResponse, modelResponse] = await Promise.all([
    api.get('/dictionary/knowledge-points'),
    api.get('/dictionary/solution-methods'),
    api.get('/chat/models'),
  ])
  dictionaryOptions.value.knowledgePoints = knowledgeResponse.data
  dictionaryOptions.value.solutionMethods = methodResponse.data
  chatModels.value = modelResponse.data || []
  selectedModel.value = chatModels.value.find((item: any) => item.is_default)?.id || chatModels.value[0]?.id || null
}

const randomQuestion = async () => {
  loading.value = true
  answerVisible.value = false
  chatSession.value = null
  try {
    const { data } = await api.get('/practice/random-question', {
      params: {
        grade_levels: filters.grade_levels,
        knowledge_point_ids: filters.knowledge_point_ids,
        solution_method_ids: filters.solution_method_ids,
        question_type: filters.question_type || undefined,
        has_answer: filters.has_answer ?? undefined,
      },
      paramsSerializer: { indexes: null },
    })
    current.value = data
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '当前范围内没有可随机的题目。')
  } finally {
    loading.value = false
  }
}

const updateState = async (payload: Record<string, unknown>) => {
  if (!question.value) return
  stateSaving.value = true
  try {
    const { data } = await api.patch(`/practice/questions/${question.value.id}/state`, payload)
    current.value.practice_state = data
  } finally {
    stateSaving.value = false
  }
}

const changePracticeStatus = async (status: string) => {
  await updateState({ practice_status: status })
  const label = practiceStatusOptions.find((item) => item.value === status)?.label || status
  ElMessage.success(`状态已更新为${label}。`)
}

const toggleFavorite = async () => {
  await updateState({ is_favorited: !practiceState.value?.is_favorited })
}

const sendChat = async () => {
  const content = chatMessage.value.trim()
  if (!content || !question.value) return
  chatSending.value = true
  try {
    const { data } = await api.post('/chat/sessions/message', {
      session_id: chatSession.value?.id || null,
      question_id: question.value.id,
      content,
      model_name: selectedModel.value,
    })
    chatSession.value = data
    chatMessage.value = ''
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '讲题对话失败。')
  } finally {
    chatSending.value = false
  }
}

onMounted(async () => {
  await loadDictionary()
})
</script>

<template>
  <div class="section-stack">
    <div class="page-header">
      <div>
        <div class="page-title">随机刷题</div>
        <div class="page-subtitle">不选择任何范围时默认从所有题目中随机抽题；答案默认隐藏，刷题状态和收藏只同步到当前用户。</div>
      </div>
      <div class="action-row">
        <el-tooltip content="随机一题" placement="bottom">
          <el-button class="random-question-button" :loading="loading" type="primary" circle aria-label="随机一题" @click="randomQuestion">
            <el-icon><DiceIcon /></el-icon>
          </el-button>
        </el-tooltip>
        <el-button :disabled="!question" @click="randomQuestion">下一题</el-button>
      </div>
    </div>

    <section class="panel">
      <div class="filter-hint">
        {{ hasActiveFilters ? '当前将从所选范围中随机抽题。' : '当前未选择范围，将从所有题目中随机抽题。' }}
      </div>
      <div class="practice-filter-grid">
        <el-select v-model="filters.grade_levels" multiple clearable placeholder="年级范围" style="width: 100%">
          <el-option label="高一" value="高一" />
          <el-option label="高二" value="高二" />
          <el-option label="高三" value="高三" />
        </el-select>
        <el-select v-model="filters.question_type" clearable placeholder="题型" style="width: 100%">
          <el-option label="选择题" value="选择题" />
          <el-option label="多选题" value="多选题" />
          <el-option label="填空题" value="填空题" />
          <el-option label="解答题" value="解答题" />
        </el-select>
        <el-select v-model="filters.has_answer" clearable placeholder="答案情况" style="width: 100%">
          <el-option label="有答案" :value="true" />
          <el-option label="缺失答案" :value="false" />
        </el-select>
        <el-select v-model="filters.knowledge_point_ids" multiple filterable clearable placeholder="知识点" style="width: 100%">
          <el-option v-for="item in dictionaryOptions.knowledgePoints" :key="item.id" :label="item.name" :value="item.id" />
        </el-select>
        <el-select v-model="filters.solution_method_ids" multiple filterable clearable placeholder="解题方法" style="width: 100%">
          <el-option v-for="item in dictionaryOptions.solutionMethods" :key="item.id" :label="item.name" :value="item.id" />
        </el-select>
      </div>
    </section>

    <section v-if="question" class="panel practice-question-panel">
      <div class="section-head">
        <div>
          <div class="section-title">题目 {{ question.question_no }}</div>
          <div class="question-meta-row">
            <span>当前状态：</span>
            <PracticeStatusBadge :status="practiceState?.practice_status" />
            <span>匹配题量：{{ current.match_count }}</span>
          </div>
        </div>
        <div class="practice-control-row">
          <el-select
            :model-value="practiceState?.practice_status || 'NOT_STARTED'"
            class="practice-status-select"
            :disabled="stateSaving"
            @change="changePracticeStatus"
          >
            <el-option v-for="item in practiceStatusOptions" :key="item.value" :label="item.label" :value="item.value">
              <PracticeStatusBadge :status="item.value" />
            </el-option>
          </el-select>
          <el-button class="favorite-button" :loading="stateSaving" :aria-label="practiceState?.is_favorited ? '取消收藏' : '收藏'" @click="toggleFavorite">
            <svg viewBox="0 0 24 24" aria-hidden="true" :class="{ filled: practiceState?.is_favorited }">
              <path d="m12 3.8 2.5 5.1 5.6.8-4 3.9.9 5.6-5-2.7-5 2.7.9-5.6-4-3.9 5.6-.8L12 3.8Z" />
            </svg>
            <span>{{ practiceState?.is_favorited ? '已收藏' : '收藏' }}</span>
          </el-button>
        </div>
      </div>

      <div class="detail-markdown-surface">
        <MarkdownContent :content="question.assets.question_md || question.stem_text" />
      </div>
      <div v-if="questionImages.length" class="image-stack">
        <img v-for="(image, index) in questionImages" :key="index" :src="image.src" :alt="image.caption || `题图 ${index + 1}`" class="question-image" />
      </div>

      <div class="answer-head">
        <div class="section-title">答案</div>
        <AnswerVisibilityButton :visible="answerVisible" @toggle="answerVisible = !answerVisible" />
      </div>
      <template v-if="answerVisible">
        <div class="detail-markdown-surface">
          <MarkdownContent :content="answerContent || '当前题目暂无答案。'" />
        </div>
        <div v-if="answerImages.length" class="image-stack">
          <img v-for="(image, index) in answerImages" :key="`answer-${index}`" :src="image.src" :alt="image.caption || `答案图 ${index + 1}`" class="question-image" />
        </div>
      </template>
      <div v-else class="surface-note">答案已隐藏。</div>
    </section>

    <section v-if="question" class="panel">
      <div class="section-head">
        <div>
          <div class="section-title">讲题对话</div>
          <div class="muted">围绕当前随机题继续追问，和题目详情页使用同一套大模型讲题接口。</div>
        </div>
        <el-select v-model="selectedModel" placeholder="模型" style="width: 220px">
          <el-option v-for="item in chatModels" :key="item.id" :label="item.label" :value="item.id" />
        </el-select>
      </div>
      <div v-if="chatSession?.messages?.length" class="chat-list">
        <div v-for="item in chatSession.messages" :key="item.id" class="surface-note">
          <strong>{{ item.role === 'user' ? '我' : '讲题助手' }}</strong>
          <MarkdownContent :content="item.content" />
        </div>
      </div>
      <el-input v-model="chatMessage" type="textarea" :rows="4" placeholder="例如：先讲思路，再讲关键步骤。" />
      <el-button type="primary" :loading="chatSending" style="margin-top: 12px" @click="sendChat">发送消息</el-button>
    </section>

    <section v-else class="panel">
      <div class="surface-note">点击随机图标开始；未选择范围时会从所有题目中随机抽题。</div>
    </section>
  </div>
</template>

<style scoped>
.practice-filter-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}

.filter-hint {
  margin-bottom: 12px;
  color: var(--mm-text-soft);
  font-size: 13px;
}

.question-meta-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  margin-top: 6px;
  color: var(--mm-text-soft);
  font-size: 13px;
}

.practice-control-row {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  flex-wrap: wrap;
}

.practice-status-select {
  width: 150px;
}

.favorite-button {
  gap: 8px;
}

.favorite-button svg {
  width: 19px;
  height: 19px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2;
  stroke-linejoin: round;
}

.favorite-button svg.filled {
  fill: #facc15;
  stroke: #eab308;
}

.random-question-button {
  width: 56px;
  height: 56px;
  min-width: 56px;
  box-shadow: 0 12px 26px rgba(63, 109, 246, 0.28);
}

.random-question-button :deep(.el-icon) {
  font-size: 32px;
}

.section-head,
.answer-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.detail-markdown-surface {
  min-width: 0;
  max-width: 100%;
  overflow-x: auto;
}

.image-stack {
  display: grid;
  gap: 12px;
  margin: 16px 0;
}

.question-image {
  width: 100%;
  max-height: 340px;
  object-fit: contain;
  background: #fff;
  border-radius: 8px;
}

.chat-list {
  display: grid;
  gap: 12px;
  margin-bottom: 12px;
}
</style>
