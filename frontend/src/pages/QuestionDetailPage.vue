<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api/client'
import MarkdownContent from '../components/MarkdownContent.vue'

const props = defineProps<{ id: string }>()
const detail = ref<any>(null)
const message = ref('')
const session = ref<any>(null)

const questionImages = computed(() => detail.value?.assets?.question_images || [])
const answerImages = computed(() => detail.value?.assets?.answer_images || [])

const load = async () => {
  detail.value = (await api.get(`/questions/${props.id}`)).data
}

const runAnalysis = async () => {
  await api.post(`/analysis/questions/${props.id}`)
  await load()
}

const sendMessage = async () => {
  const { data } = await api.post('/chat/sessions/message', {
    session_id: session.value?.id,
    question_id: Number(props.id),
    content: message.value,
  })
  session.value = data
  message.value = ''
}

onMounted(load)
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
      <el-button type="primary" @click="runAnalysis">运行题目分析</el-button>
    </div>

    <div class="grid cols-2">
      <section class="panel">
        <h3>题干</h3>
        <MarkdownContent :content="detail.assets.question_md" />

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

        <h3>答案</h3>
        <MarkdownContent :content="detail.answer?.answer_text || detail.assets.answer_md" />

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
      </section>

      <section class="panel">
        <h3>分析结果</h3>
        <div v-if="detail.analysis">
          <MarkdownContent :content="detail.analysis.explanation_md" />
          <pre class="mono preview-text">{{ detail.analysis.analysis_json }}</pre>
        </div>
        <div v-else class="muted">尚未生成分析结果。</div>
      </section>
    </div>

    <section class="panel">
      <h3>讲题对话</h3>
      <div v-if="session?.messages?.length">
        <div v-for="item in session.messages" :key="item.id" class="chat-message">
          <strong>{{ item.role }}</strong>
          <MarkdownContent :content="item.content" />
        </div>
      </div>
      <el-input v-model="message" type="textarea" :rows="4" placeholder="例如：请按步骤讲解这道题，并解释图中的关键关系。" />
      <el-button type="primary" style="margin-top: 12px" @click="sendMessage">发送</el-button>
    </section>
  </div>
</template>

<style scoped>
.preview-text {
  white-space: pre-wrap;
  line-height: 1.75;
}

.image-stack {
  display: grid;
  gap: 14px;
  margin: 18px 0;
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

.chat-message {
  margin-bottom: 12px;
  padding: 12px 14px;
  border-radius: 14px;
  background: var(--mm-soft);
}
</style>
