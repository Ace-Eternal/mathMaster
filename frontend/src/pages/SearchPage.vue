<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api/client'
import MarkdownContent from '../components/MarkdownContent.vue'

const paperKeyword = ref('')
const questionKeyword = ref('')
const selectedKnowledgePointId = ref<number | null>(null)
const selectedSolutionMethodId = ref<number | null>(null)
const papers = ref<any[]>([])
const questions = ref<any[]>([])
const knowledgePoints = ref<any[]>([])
const solutionMethods = ref<any[]>([])

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
  questions.value = (
    await api.get('/search/questions', {
      params: {
        keyword: questionKeyword.value,
        knowledge_point_id: selectedKnowledgePointId.value || undefined,
        solution_method_id: selectedSolutionMethodId.value || undefined,
      },
    })
  ).data.items
}

const loadFilters = async () => {
  knowledgePoints.value = (await api.get('/dictionary/knowledge-points')).data
  solutionMethods.value = (await api.get('/dictionary/solution-methods')).data
}

onMounted(loadFilters)
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
      <el-select v-model="selectedKnowledgePointId" clearable placeholder="按知识点筛选" style="margin-top: 12px; width: 100%">
        <el-option v-for="item in knowledgePoints" :key="item.id" :value="item.id" :label="item.name" />
      </el-select>
      <el-select v-model="selectedSolutionMethodId" clearable placeholder="按解法筛选" style="margin-top: 12px; width: 100%">
        <el-option v-for="item in solutionMethods" :key="item.id" :value="item.id" :label="item.name" />
      </el-select>
      <el-button type="primary" style="margin-top: 12px" @click="searchQuestions">搜索题目</el-button>
        <div v-if="questions.length" class="result-list">
          <div v-for="question in questions" :key="question.id" class="result-card">
            <RouterLink :to="`/questions/${question.id}`" class="result-title">{{ question.question_no }}.</RouterLink>
            <MarkdownContent :content="buildSnippet(question.stem_text)" />
            <div class="muted">试卷：{{ question.paper_title }} ｜ 题型：{{ question.question_type || '-' }} ｜ 审核状态：{{ question.review_status }}</div>
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
