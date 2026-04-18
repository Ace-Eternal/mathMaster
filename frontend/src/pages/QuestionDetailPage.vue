<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api/client'
import MarkdownContent from '../components/MarkdownContent.vue'

const props = defineProps<{ id: string }>()
const detail = ref<any>(null)
const message = ref('')
const session = ref<any>(null)
const chatSessions = ref<any[]>([])
const dictionaryOptions = ref({ knowledgePoints: [] as any[], solutionMethods: [] as any[] })
const tagForm = ref({ knowledge_point_ids: [] as number[], solution_method_ids: [] as number[] })
const savingTags = ref(false)
const sendingMessage = ref(false)
const activePanels = ref(['chat'])
const chatScrollRef = ref<HTMLElement | null>(null)
const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api'

const questionImages = computed(() => detail.value?.assets?.question_images || [])
const answerImages = computed(() => detail.value?.assets?.answer_images || [])
const knowledges = computed(() => detail.value?.knowledges || [])
const methods = computed(() => detail.value?.methods || [])
const activeSessionId = computed(() => session.value?.id ?? null)

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
    knowledge_point_ids: knowledges.value.map((item: any) => item.id),
    solution_method_ids: methods.value.map((item: any) => item.id),
  }
}

const loadDictionary = async () => {
  dictionaryOptions.value.knowledgePoints = (await api.get('/dictionary/knowledge-points')).data
  dictionaryOptions.value.solutionMethods = (await api.get('/dictionary/solution-methods')).data
}

const loadChatSessions = async () => {
  const { data } = await api.get(`/chat/questions/${props.id}/sessions`)
  chatSessions.value = data
  if (!session.value && data.length) {
    await selectSession(data[0].id)
  }
}

const selectSession = async (sessionId: number) => {
  session.value = (await api.get(`/chat/sessions/${sessionId}`, { params: { question_id: Number(props.id) } })).data
  activePanels.value = ['chat']
  await scrollChatToBottom()
}

const createNewSession = () => {
  session.value = null
  message.value = ''
}

const runAnalysis = async () => {
  await api.post(`/analysis/questions/${props.id}`)
  await load()
}

const scrollChatToBottom = async () => {
  await nextTick()
  if (chatScrollRef.value) {
    chatScrollRef.value.scrollTop = chatScrollRef.value.scrollHeight
  }
}

const parseSseBlock = (block: string) => {
  const dataLine = block
    .split('\n')
    .map((line) => line.trim())
    .find((line) => line.startsWith('data:'))
  if (!dataLine) return null
  try {
    return JSON.parse(dataLine.slice(5).trim())
  } catch {
    return null
  }
}

const sendMessage = async () => {
  const content = message.value.trim()
  if (!content || sendingMessage.value) return

  sendingMessage.value = true
  activePanels.value = ['chat']
  if (!session.value) {
    session.value = { id: null, question_id: Number(props.id), messages: [] }
  }
  const userMessage = { id: `user-${Date.now()}`, role: 'user', content }
  const assistantMessage = { id: `assistant-${Date.now()}`, role: 'assistant', content: '', model_name: null as string | null }
  session.value.messages = [...(session.value.messages || []), userMessage, assistantMessage]
  message.value = ''
  await scrollChatToBottom()

  try {
    const response = await fetch(`${apiBase}/chat/sessions/message/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: session.value?.id,
        question_id: Number(props.id),
        content,
      }),
    })
    if (!response.ok || !response.body) {
      throw new Error(`请求失败：${response.status}`)
    }
    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const blocks = buffer.split('\n\n')
      buffer = blocks.pop() || ''
      for (const block of blocks) {
        const event = parseSseBlock(block)
        if (!event) continue
        if (event.type === 'meta') {
          session.value.id = event.session_id
          await loadChatSessions()
          continue
        }
        if (event.type === 'start') {
          assistantMessage.model_name = event.model_name || null
          if (event.notice) {
            assistantMessage.content += `${event.notice}\n\n`
          }
          continue
        }
        if (event.type === 'chunk') {
          assistantMessage.content += event.content || ''
          await scrollChatToBottom()
          continue
        }
        if (event.type === 'done') {
          if (event.session_id) session.value.id = event.session_id
          await loadChatSessions()
          continue
        }
        if (event.type === 'error') {
          assistantMessage.content = assistantMessage.content || '对话生成失败。'
          ElMessage.error(event.message || '对话生成失败')
        }
      }
    }
  } catch (error: any) {
    assistantMessage.content = assistantMessage.content || '对话生成失败。'
    ElMessage.error(error?.message || '对话生成失败')
  } finally {
    sendingMessage.value = false
    await scrollChatToBottom()
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
  await Promise.all([load(), loadDictionary(), loadChatSessions()])
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
          <div v-if="knowledges.length" class="meta-group">
            <div class="meta-label">知识点</div>
            <div class="tag-wrap">
              <span v-for="item in knowledges" :key="`kp-${item.id}`" class="pill-tag">{{ item.name }}</span>
            </div>
          </div>
          <div v-if="methods.length" class="meta-group">
            <div class="meta-label">推荐解法</div>
            <div class="tag-wrap">
              <span v-for="item in methods" :key="`method-${item.id}`" class="pill-tag">{{ item.name }}</span>
            </div>
          </div>
          <MarkdownContent :content="detail.analysis.explanation_md" />
        </div>
        <div v-else class="muted">尚未生成分析结果。</div>

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

    <section class="panel">
      <el-collapse v-model="activePanels">
        <el-collapse-item name="chat">
          <template #title>
            <div class="chat-header">
              <span>讲题对话</span>
              <span class="muted">{{ sendingMessage ? '正在生成中...' : '展开后可在独立面板中滚动查看' }}</span>
            </div>
          </template>
          <div class="chat-layout">
            <aside class="chat-sidebar">
              <div class="chat-sidebar-head">
                <div class="chat-sidebar-title">会话列表</div>
                <el-button text type="primary" @click.stop="createNewSession">新对话</el-button>
              </div>
              <div v-if="chatSessions.length" class="chat-session-list">
                <button
                  v-for="item in chatSessions"
                  :key="item.id"
                  type="button"
                  class="chat-session-item"
                  :class="{ active: activeSessionId === item.id }"
                  @click="selectSession(item.id)"
                >
                  <div class="chat-session-title">{{ item.title || `会话 ${item.id}` }}</div>
                  <div class="chat-session-preview">{{ item.last_message_preview || '暂无消息摘要' }}</div>
                  <div class="chat-session-meta">
                    <span>{{ item.message_count }} 条消息</span>
                    <span>{{ new Date(item.updated_at || item.created_at).toLocaleString('zh-CN', { hour12: false }) }}</span>
                  </div>
                </button>
              </div>
              <div v-else class="muted">还没有历史会话，发送第一条消息后会自动保存。</div>
            </aside>

            <div class="chat-main">
              <div ref="chatScrollRef" class="chat-scroll">
                <div v-if="session?.messages?.length" class="chat-thread">
                  <div
                    v-for="item in session.messages"
                    :key="item.id"
                    class="chat-row"
                    :class="item.role === 'user' ? 'chat-row-user' : 'chat-row-assistant'"
                  >
                    <div class="chat-bubble" :class="item.role === 'user' ? 'chat-bubble-user' : 'chat-bubble-assistant'">
                      <div class="chat-role">{{ item.role === 'user' ? '我' : '讲题助手' }}</div>
                      <MarkdownContent :content="item.content" />
                    </div>
                  </div>
                </div>
                <div v-else class="muted">当前是新对话，发送消息后会自动保存并出现在左侧会话栏。</div>
              </div>
              <el-input v-model="message" type="textarea" :rows="4" placeholder="例如：请按步骤讲解这道题，并解释图中的关键关系。" />
              <el-button type="primary" :loading="sendingMessage" style="margin-top: 12px" @click="sendMessage">发送</el-button>
            </div>
          </div>
        </el-collapse-item>
      </el-collapse>
    </section>
  </div>
</template>

<style scoped>
.image-stack {
  display: grid;
  gap: 14px;
  margin: 18px 0;
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

.chat-message {
  margin-bottom: 12px;
  padding: 12px 14px;
  border-radius: 14px;
  background: var(--mm-soft);
}

.tag-editor {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid rgba(15, 23, 42, 0.08);
}

.chat-header {
  display: flex;
  justify-content: space-between;
  width: 100%;
  padding-right: 12px;
}

.chat-scroll {
  min-height: 240px;
  max-height: 520px;
  overflow-y: auto;
  padding-right: 8px;
  margin-bottom: 16px;
}

.chat-layout {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 18px;
}

.chat-sidebar {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
  padding-right: 6px;
  border-right: 1px solid rgba(15, 23, 42, 0.08);
}

.chat-sidebar-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.chat-sidebar-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--mm-text);
}

.chat-session-list {
  display: grid;
  gap: 10px;
  max-height: 520px;
  overflow-y: auto;
  padding-right: 6px;
}

.chat-session-item {
  width: 100%;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 14px;
  padding: 12px;
  background: #fff;
  text-align: left;
  cursor: pointer;
}

.chat-session-item.active {
  border-color: rgba(59, 130, 246, 0.35);
  background: #eff6ff;
}

.chat-session-title {
  color: var(--mm-text);
  font-size: 14px;
  font-weight: 700;
  line-height: 1.4;
}

.chat-session-preview {
  margin-top: 6px;
  color: var(--mm-text-soft);
  font-size: 12px;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.chat-session-meta {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  margin-top: 8px;
  color: var(--mm-text-soft);
  font-size: 12px;
}

.chat-main {
  min-width: 0;
}

.chat-thread {
  display: grid;
  gap: 12px;
}

.chat-row {
  display: flex;
}

.chat-row-user {
  justify-content: flex-end;
}

.chat-row-assistant {
  justify-content: flex-start;
}

.chat-bubble {
  max-width: min(82%, 860px);
  padding: 14px 16px;
  border-radius: 18px;
}

.chat-bubble-user {
  background: #dbeafe;
}

.chat-bubble-assistant {
  background: var(--mm-soft);
}

.chat-role {
  margin-bottom: 8px;
  font-size: 12px;
  color: var(--mm-muted);
}

@media (max-width: 1080px) {
  .chat-layout {
    grid-template-columns: 1fr;
  }

  .chat-sidebar {
    border-right: none;
    border-bottom: 1px solid rgba(15, 23, 42, 0.08);
    padding-right: 0;
    padding-bottom: 12px;
  }

  .chat-session-list {
    max-height: 220px;
  }
}
</style>
