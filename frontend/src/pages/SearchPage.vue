<script setup lang="ts">
import { ref } from 'vue'
import { api } from '../api/client'

const paperKeyword = ref('')
const questionKeyword = ref('')
const papers = ref<any[]>([])
const questions = ref<any[]>([])

const searchPapers = async () => {
  papers.value = (await api.get('/search/papers', { params: { keyword: paperKeyword.value } })).data.items
}

const searchQuestions = async () => {
  questions.value = (await api.get('/search/questions', { params: { keyword: questionKeyword.value } })).data.items
}
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
      <div v-for="paper in papers" :key="paper.id" style="margin-top: 12px">
        <RouterLink :to="`/papers/${paper.id}`">{{ paper.title }}</RouterLink>
      </div>
    </section>

    <section class="panel">
      <h3>题目搜索</h3>
      <el-input v-model="questionKeyword" placeholder="输入题干关键词" />
      <el-button type="primary" style="margin-top: 12px" @click="searchQuestions">搜索题目</el-button>
      <div v-for="question in questions" :key="question.id" style="margin-top: 12px">
        <RouterLink :to="`/questions/${question.id}`">{{ question.question_no }}. {{ question.stem_text }}</RouterLink>
      </div>
    </section>
  </div>
</template>
