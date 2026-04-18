<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api/client'
import MarkdownContent from '../components/MarkdownContent.vue'

const paperKeyword = ref('')
const questionKeyword = ref('')
const selectedYear = ref<number | null>(null)
const selectedRegion = ref('')
const selectedGradeLevel = ref('')
const selectedTerm = ref('')
const selectedQuestionType = ref('')
const selectedReviewStatus = ref('')
const selectedHasAnswer = ref<boolean | null>(null)
const selectedKnowledgePointId = ref<number | null>(null)
const selectedSolutionMethodId = ref<number | null>(null)
const selectedSortBy = ref('updated_desc')
const papers = ref<any[]>([])
const questions = ref<any[]>([])
const knowledgePoints = ref<any[]>([])
const solutionMethods = ref<any[]>([])
const recentQuestionSearches = ref<string[]>([])

const buildSnippet = (text: string | null | undefined, limit = 180) => {
  const normalized = String(text || '').replace(/\s+/g, ' ').trim()
  if (!normalized) return ''
  if (normalized.length <= limit) return normalized
  return `${normalized.slice(0, limit)}...`
}

const searchPapers = async () => {
  papers.value = (await api.get('/search/papers', { params: { keyword: paperKeyword.value } })).data.items
}

const searchQuestions = async () => {
  if (questionKeyword.value.trim()) {
    recentQuestionSearches.value = [questionKeyword.value.trim(), ...recentQuestionSearches.value.filter((item) => item !== questionKeyword.value.trim())].slice(0, 6)
    localStorage.setItem('mm:recent-question-searches', JSON.stringify(recentQuestionSearches.value))
  }
  questions.value = (
    await api.get('/search/questions', {
      params: {
        keyword: questionKeyword.value,
        year: selectedYear.value || undefined,
        region: selectedRegion.value || undefined,
        grade_level: selectedGradeLevel.value || undefined,
        term: selectedTerm.value || undefined,
        question_type: selectedQuestionType.value || undefined,
        review_status: selectedReviewStatus.value || undefined,
        has_answer: selectedHasAnswer.value ?? undefined,
        knowledge_point_id: selectedKnowledgePointId.value || undefined,
        solution_method_id: selectedSolutionMethodId.value || undefined,
        sort_by: selectedSortBy.value,
      },
    })
  ).data.items
}

const applyRecentSearch = async (keyword: string) => {
  questionKeyword.value = keyword
  await searchQuestions()
}

const loadFilters = async () => {
  knowledgePoints.value = (await api.get('/dictionary/knowledge-points')).data
  solutionMethods.value = (await api.get('/dictionary/solution-methods')).data
  try {
    recentQuestionSearches.value = JSON.parse(localStorage.getItem('mm:recent-question-searches') || '[]')
  } catch {
    recentQuestionSearches.value = []
  }
}

onMounted(loadFilters)

const activeFilterSummary = computed(() =>
  [
    selectedYear.value ? `年份 ${selectedYear.value}` : null,
    selectedRegion.value ? `地区 ${selectedRegion.value}` : null,
    selectedGradeLevel.value ? `年级 ${selectedGradeLevel.value}` : null,
    selectedTerm.value ? `学期 ${selectedTerm.value}` : null,
    selectedQuestionType.value ? `题型 ${selectedQuestionType.value}` : null,
    selectedReviewStatus.value ? `审核 ${selectedReviewStatus.value}` : null,
    selectedHasAnswer.value === null ? null : selectedHasAnswer.value ? '有答案' : '缺答案',
  ].filter(Boolean)
)
</script>

<template>
  <div class="page-header">
    <div>
      <div class="page-title">题库搜索</div>
      <div class="page-subtitle">
        支持按试卷标题和题干关键词搜索，方便回查整理结果并快速进入题目详情。
      </div>
    </div>
  </div>

  <div class="grid cols-2">
    <section class="panel">
      <h3>试卷搜索</h3>
      <el-input v-model="paperKeyword" placeholder="输入试卷标题关键词" />
      <el-button type="primary" style="margin-top: 12px" @click="searchPapers">搜索试卷</el-button>
      <div v-if="papers.length" class="result-list">
        <div v-for="paper in papers" :key="paper.id" class="result-card">
          <RouterLink :to="`/papers/${paper.id}`" class="result-title">{{ paper.title }}</RouterLink>
          <div class="muted">年份：{{ paper.year || '-' }} ｜ 地区：{{ paper.region || '-' }} ｜ 年级：{{ paper.grade_level || '-' }} ｜ 状态：{{ paper.status }}</div>
        </div>
      </div>
      <div v-else class="muted" style="margin-top: 12px">
        暂无试卷结果。
      </div>
    </section>

    <section class="panel">
      <h3>题目搜索</h3>
      <el-input v-model="questionKeyword" placeholder="输入题干关键词" />
      <div class="grid cols-2" style="margin-top: 12px">
        <el-input-number v-model="selectedYear" :min="2000" :max="2100" placeholder="年份" style="width: 100%" />
        <el-input v-model="selectedRegion" placeholder="地区，如浙江" />
      </div>
      <div class="grid cols-2" style="margin-top: 12px">
        <el-input v-model="selectedGradeLevel" placeholder="年级，如高一" />
        <el-input v-model="selectedTerm" placeholder="学期，如期末" />
      </div>
      <div class="grid cols-2" style="margin-top: 12px">
        <el-select v-model="selectedQuestionType" clearable placeholder="按题型筛选" style="width: 100%">
          <el-option label="选择题" value="选择题" />
          <el-option label="多选题" value="多选题" />
          <el-option label="填空题" value="填空题" />
          <el-option label="解答题" value="解答题" />
        </el-select>
        <el-select v-model="selectedReviewStatus" clearable placeholder="按审核状态筛选" style="width: 100%">
          <el-option label="PENDING" value="PENDING" />
          <el-option label="FIXED" value="FIXED" />
          <el-option label="APPROVED" value="APPROVED" />
        </el-select>
      </div>
      <div class="grid cols-2" style="margin-top: 12px">
        <el-select v-model="selectedHasAnswer" clearable placeholder="按答案情况筛选" style="width: 100%">
          <el-option label="有答案" :value="true" />
          <el-option label="缺失答案" :value="false" />
        </el-select>
        <el-select v-model="selectedSortBy" placeholder="结果排序" style="width: 100%">
          <el-option label="最近更新优先" value="updated_desc" />
          <el-option label="按题号排序" value="question_no" />
          <el-option label="待审核优先" value="review_first" />
        </el-select>
      </div>
      <el-select v-model="selectedKnowledgePointId" clearable placeholder="按知识点筛选" style="margin-top: 12px; width: 100%">
        <el-option v-for="item in knowledgePoints" :key="item.id" :value="item.id" :label="item.name" />
      </el-select>
      <el-select v-model="selectedSolutionMethodId" clearable placeholder="按解法筛选" style="margin-top: 12px; width: 100%">
        <el-option v-for="item in solutionMethods" :key="item.id" :value="item.id" :label="item.name" />
      </el-select>
      <el-button type="primary" style="margin-top: 12px" @click="searchQuestions">搜索题目</el-button>
      <div v-if="recentQuestionSearches.length" class="recent-searches">
        <span class="muted">最近搜索：</span>
        <el-button v-for="item in recentQuestionSearches" :key="item" text @click="applyRecentSearch(item)">{{ item }}</el-button>
      </div>
      <div v-if="activeFilterSummary.length" class="muted" style="margin-top: 12px">
        当前筛选：{{ activeFilterSummary.join(' ｜ ') }}
      </div>
        <div v-if="questions.length" class="result-list">
          <div v-for="question in questions" :key="question.id" class="result-card">
            <RouterLink :to="`/questions/${question.id}`" class="result-title">{{ question.question_no }}.</RouterLink>
            <MarkdownContent :content="buildSnippet(question.stem_text)" />
            <div class="muted">试卷：{{ question.paper_title }} ｜ {{ question.year || '-' }} ｜ {{ question.region || '-' }} ｜ {{ question.grade_level || '-' }} ｜ {{ question.term || '-' }}</div>
            <div class="muted">题型：{{ question.question_type || '-' }} ｜ 审核状态：{{ question.review_status }} ｜ {{ question.has_answer ? '有答案' : '缺答案' }}</div>
            <div class="action-row" style="margin-top: 8px">
              <RouterLink :to="`/questions/${question.id}`" class="result-title">查看题目</RouterLink>
              <RouterLink :to="`/papers/${question.paper_id}`" class="result-title">所属试卷</RouterLink>
              <RouterLink :to="`/review/${question.id}`" class="result-title">进入审核</RouterLink>
            </div>
          </div>
        </div>
      <div v-else class="muted" style="margin-top: 12px">
        暂无题目结果。
      </div>
    </section>
  </div>
</template>

<style scoped>
.result-list {
  display: grid;
  gap: 12px;
  margin-top: 14px;
}

.result-card {
  padding: 14px;
  border-radius: 16px;
  background: var(--mm-soft);
}

.recent-searches {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  margin-top: 12px;
}

.result-title {
  display: inline-block;
  margin-bottom: 6px;
  font-weight: 600;
  color: var(--mm-ink);
  text-decoration: none;
}

.result-title:hover {
  text-decoration: underline;
}
</style>
