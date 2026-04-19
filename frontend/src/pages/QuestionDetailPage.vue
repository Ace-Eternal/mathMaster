<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
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
const streamController = ref<AbortController | null>(null)
const streamState = ref<'idle' | 'streaming' | 'stopping'>('idle')
const activeGenerationId = ref<string | null>(null)
const activeAssistantMessage = ref<any>(null)
const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api'
const STOP_NOTICE = '\n\n> 已停止生成'

const questionImages = computed(() => detail.value?.assets?.question_images || [])
const answerImages = computed(() => detail.value?.assets?.answer_images || [])
const knowledges = computed(() => detail.value?.knowledges || [])
const methods = computed(() => detail.value?.methods || [])
const activeSessionId = computed(() => session.value?.id ?? null)
const isStreaming = computed(() => streamState.value === 'streaming')
const isStopping = computed(() => streamState.value === 'stopping')
const showStopAction = computed(() => streamState.value !== 'idle')
const composerButtonDisabled = computed(() => {
  if (isStopping.value) return true
  if (isStreaming.value) return false
  return !message.value.trim()
})
const composerButtonLabel = computed(() => (isStreaming.value ? '停止生成' : '发送消息'))

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

const loadSession = async (sessionId: number) => {
  session.value = (await api.get(`/chat/sessions/${sessionId}`, { params: { question_id: Number(props.id) } })).data
  activePanels.value = ['chat']
  await scrollChatToBottom()
}

const selectSession = async (sessionId: number) => {
  if (streamState.value !== 'idle') return
  await loadSession(sessionId)
}

const createNewSession = () => {
  if (streamState.value !== 'idle') return
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

const appendStopNotice = (target: { content?: string | null } | null) => {
  if (!target) return
  const content = String(target.content || '').trimEnd()
  if (content.includes(STOP_NOTICE.trim())) return
  target.content = content ? `${content}${STOP_NOTICE}` : STOP_NOTICE.trim()
}

const refreshCurrentSession = async (sessionId: number | null | undefined) => {
  if (!sessionId) return
  await new Promise((resolve) => window.setTimeout(resolve, 250))
  await loadChatSessions()
  if (activeSessionId.value === sessionId || session.value?.id === sessionId) {
    await loadSession(sessionId)
  }
}

const stopMessage = async () => {
  if (streamState.value !== 'streaming') return
  streamState.value = 'stopping'
  const generationId = activeGenerationId.value
  const currentSessionId = session.value?.id
  streamController.value?.abort()
  appendStopNotice(activeAssistantMessage.value)
  if (generationId) {
    try {
      await api.post(`/chat/generations/${generationId}/cancel`)
    } catch {
      // 取消接口失败时保持本地已停止状态，不额外打断交互
    }
  }
  await refreshCurrentSession(currentSessionId)
}

const handleComposerKeydown = async (event: KeyboardEvent) => {
  if (event.key !== 'Enter' || event.shiftKey) return
  event.preventDefault()
  if (streamState.value === 'idle') {
    await sendMessage()
  }
}

const sendMessage = async () => {
  const content = message.value.trim()
  if (!content || sendingMessage.value || streamState.value !== 'idle') return

  sendingMessage.value = true
  streamState.value = 'streaming'
  activeGenerationId.value = null
  activePanels.value = ['chat']
  if (!session.value) {
    session.value = { id: null, question_id: Number(props.id), messages: [] }
  }
  const streamAbortController = new AbortController()
  streamController.value = streamAbortController
  const userMessage = reactive({ id: `user-${Date.now()}`, role: 'user', content })
  const assistantMessage = reactive({
    id: `assistant-${Date.now()}`,
    role: 'assistant',
    content: '',
    model_name: null as string | null,
  })
  activeAssistantMessage.value = assistantMessage
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
      signal: streamAbortController.signal,
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
          activeGenerationId.value = event.generation_id || null
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
          if (event.finish_reason === 'stopped') {
            appendStopNotice(assistantMessage)
          }
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
    if (error?.name === 'AbortError' && isStopping.value) {
      appendStopNotice(assistantMessage)
    } else {
      assistantMessage.content = assistantMessage.content || '对话生成失败。'
      ElMessage.error(error?.message || '对话生成失败')
    }
  } finally {
    streamController.value = null
    activeGenerationId.value = null
    activeAssistantMessage.value = null
    streamState.value = 'idle'
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

onBeforeUnmount(() => {
  streamController.value?.abort()
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

    <section class="chat-shell">
      <aside class="chat-sidebar">
        <div class="chat-sidebar-head">
          <div>
            <div class="chat-sidebar-title">讲题对话</div>
            <div class="chat-sidebar-subtitle">像 ChatGPT 一样连续追问、切换历史与继续追问。</div>
          </div>
          <el-button text type="primary" @click.stop="createNewSession">新对话</el-button>
        </div>

        <div class="chat-sidebar-summary">
          <div class="chat-sidebar-summary__label">当前题目</div>
          <div class="chat-sidebar-summary__value">第 {{ detail.question_no }} 题</div>
          <div class="chat-sidebar-summary__meta">
            {{ sendingMessage ? '正在生成回答' : `${chatSessions.length} 个历史会话` }}
          </div>
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
        <div v-else class="chat-sidebar-empty">
          <div class="chat-sidebar-empty__title">还没有历史会话</div>
          <div class="muted">发送第一条消息后，会自动保存在这里，方便继续追问。</div>
        </div>
      </aside>

      <div class="chat-main">
        <div class="chat-main__header">
          <div>
            <div class="chat-main__title">MathMaster Tutor</div>
            <div class="chat-main__subtitle">
              {{ sendingMessage ? '正在流式生成讲解，你可以随时停止。' : '围绕当前题目继续提问，系统会直接结合题干、答案和图片上下文回答。' }}
            </div>
          </div>
        </div>

        <div ref="chatScrollRef" class="chat-scroll">
          <div v-if="session?.messages?.length" class="chat-thread">
            <div
              v-for="item in session.messages"
              :key="item.id"
              class="chat-turn"
              :class="item.role === 'user' ? 'chat-turn-user' : 'chat-turn-assistant'"
            >
              <div class="chat-avatar" :class="item.role === 'user' ? 'chat-avatar-user' : 'chat-avatar-assistant'">
                <span v-if="item.role === 'user'">我</span>
                <svg v-else viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M12 3 4.5 7v5.5c0 4.1 2.8 7.9 7.5 8.5 4.7-.6 7.5-4.4 7.5-8.5V7L12 3Z" />
                  <path d="M9.5 12.5 11 14l3.8-4.3" />
                </svg>
              </div>

              <div class="chat-turn__body">
                <div class="chat-turn__meta">
                  <span class="chat-turn__author">{{ item.role === 'user' ? '你' : '讲题助手' }}</span>
                  <span v-if="item.model_name && item.role !== 'user'" class="chat-turn__model">{{ item.model_name }}</span>
                </div>
                <div class="chat-bubble" :class="item.role === 'user' ? 'chat-bubble-user' : 'chat-bubble-assistant'">
                  <MarkdownContent :content="item.content" />
                </div>
              </div>
            </div>
          </div>
          <div v-else class="chat-empty">
            <div class="chat-empty__badge">New chat</div>
            <div class="chat-empty__title">从当前题目开始追问</div>
            <div class="chat-empty__text">例如：先讲思路，再讲每个选项为什么对或错；或者只解释图中的关键空间关系。</div>
          </div>
        </div>

        <div class="chat-composer-wrap">
          <div class="chat-composer-hint">
            <span>{{ showStopAction ? '点击右侧停止按钮可中断本次回答' : 'Enter 发送，Shift + Enter 换行' }}</span>
          </div>
          <div class="chat-composer">
            <el-input
              v-model="message"
              class="chat-composer__input"
              type="textarea"
              :rows="4"
              resize="none"
              placeholder="给这道题继续提问，例如：先讲总思路，再分步骤解释。"
              @keydown="handleComposerKeydown"
            />
            <button
              type="button"
              class="chat-composer__action"
              :class="{ 'is-stop': showStopAction, 'is-busy': isStopping }"
              :disabled="composerButtonDisabled"
              :aria-label="composerButtonLabel"
              :title="composerButtonLabel"
              @click="showStopAction ? stopMessage() : sendMessage()"
            >
              <svg v-if="showStopAction" viewBox="0 0 24 24" aria-hidden="true">
                <rect x="7" y="7" width="10" height="10" rx="2.5" />
              </svg>
              <svg v-else viewBox="0 0 24 24" aria-hidden="true">
                <path d="M4 11.5 19.2 4.8c.8-.35 1.58.42 1.23 1.22L13.7 21.2c-.37.83-1.58.74-1.82-.14l-1.55-5.55a1 1 0 0 0-.68-.68L4.14 13.28c-.88-.25-.97-1.46-.14-1.82Z" />
                <path d="m9.5 14.5 5.5-5.5" />
              </svg>
            </button>
          </div>
        </div>
      </div>
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

.chat-shell {
  display: grid;
  grid-template-columns: 290px minmax(0, 1fr);
  min-height: 820px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 22px;
  overflow: hidden;
  background: #fff;
  box-shadow: 0 18px 45px rgba(15, 23, 42, 0.05);
}

.chat-sidebar {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 0;
  padding: 20px;
  background: #f7f7f8;
  border-right: 1px solid rgba(15, 23, 42, 0.08);
}

.chat-sidebar-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.chat-sidebar-title {
  font-size: 18px;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: #0f172a;
}

.chat-sidebar-subtitle {
  margin-top: 6px;
  color: #64748b;
  font-size: 12px;
  line-height: 1.5;
}

.chat-sidebar-summary {
  padding: 16px;
  border-radius: 16px;
  background: #fff;
  border: 1px solid rgba(15, 23, 42, 0.08);
}

.chat-sidebar-summary__label {
  color: #64748b;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.chat-sidebar-summary__value {
  margin-top: 8px;
  font-size: 20px;
  font-weight: 800;
  color: #0f172a;
}

.chat-sidebar-summary__meta {
  margin-top: 8px;
  color: #475569;
  font-size: 12px;
}

.chat-session-list {
  display: grid;
  gap: 10px;
  flex: 1;
  overflow-y: auto;
  padding-right: 4px;
}

.chat-sidebar-empty {
  padding: 18px 16px;
  border-radius: 14px;
  background: #fff;
  border: 1px dashed rgba(15, 23, 42, 0.18);
}

.chat-sidebar-empty__title {
  margin-bottom: 8px;
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.chat-session-item {
  width: 100%;
  border: 1px solid transparent;
  border-radius: 14px;
  padding: 14px;
  background: transparent;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.18s ease, background 0.18s ease;
}

.chat-session-item:hover {
  border-color: rgba(15, 23, 42, 0.08);
  background: #fff;
}

.chat-session-item.active {
  border-color: rgba(16, 163, 127, 0.24);
  background: #fff;
}

.chat-session-title {
  color: #0f172a;
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
  color: #64748b;
  font-size: 12px;
}

.chat-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: #fff;
}

.chat-main__header {
  padding: 26px 32px 18px;
  border-bottom: 1px solid rgba(15, 23, 42, 0.08);
}

.chat-main__title {
  font-size: 22px;
  font-weight: 800;
  letter-spacing: -0.03em;
  color: #111827;
}

.chat-main__subtitle {
  margin-top: 8px;
  max-width: 720px;
  color: #6b7280;
  line-height: 1.7;
  font-size: 14px;
}

.chat-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 0;
  background: #fff;
}

.chat-composer {
  position: relative;
}

.chat-composer__input :deep(.el-textarea__inner) {
  min-height: 118px;
  padding-right: 80px;
  padding-left: 18px;
  padding-top: 16px;
  padding-bottom: 16px;
  border-radius: 24px;
  background: #fff !important;
  box-shadow: 0 0 0 1px rgba(15, 23, 42, 0.14) inset !important;
}

.chat-composer__action {
  position: absolute;
  top: 50%;
  right: 18px;
  transform: translateY(-50%);
  width: 44px;
  height: 44px;
  border: none;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #111827;
  color: #fff;
  cursor: pointer;
  transition: transform 0.2s ease, background 0.2s ease, opacity 0.2s ease;
}

.chat-composer__action:hover:not(:disabled) {
  transform: translateY(-50%) scale(1.03);
  background: #10a37f;
}

.chat-composer__action:disabled {
  opacity: 0.48;
  cursor: not-allowed;
  box-shadow: none;
}

.chat-composer__action.is-stop {
  background: #dc2626;
}

.chat-composer__action.is-busy {
  opacity: 0.72;
}

.chat-composer__action svg {
  width: 20px;
  height: 20px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.chat-composer__action.is-stop svg {
  fill: currentColor;
  stroke: none;
}

.chat-composer-wrap {
  padding: 20px 32px 28px;
  background: #fff;
  border-top: 1px solid rgba(15, 23, 42, 0.08);
}

.chat-composer-hint {
  display: flex;
  justify-content: center;
  margin-bottom: 10px;
  color: #6b7280;
  font-size: 12px;
}

.chat-thread {
  display: block;
  width: min(100%, 880px);
  margin: 0 auto;
  padding: 0 32px 24px;
}

.chat-turn {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  padding: 24px 0;
  border-bottom: 1px solid rgba(15, 23, 42, 0.08);
}

.chat-turn-user {
  flex-direction: row;
}

.chat-avatar {
  flex: 0 0 34px;
  width: 34px;
  height: 34px;
  border-radius: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 800;
  color: #fff;
}

.chat-avatar-user {
  background: #111827;
}

.chat-avatar-assistant {
  background: #10a37f;
}

.chat-avatar-assistant svg {
  width: 18px;
  height: 18px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.8;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.chat-turn__body {
  flex: 1;
  min-width: 0;
}

.chat-turn__meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
  color: #6b7280;
  font-size: 12px;
}

.chat-turn-user .chat-turn__meta {
  justify-content: flex-start;
}

.chat-turn__author {
  font-weight: 700;
  color: #111827;
}

.chat-turn__model {
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.05);
  color: #64748b;
}

.chat-bubble {
  width: 100%;
  padding: 0;
  border-radius: 0;
  line-height: 1.75;
  color: #111827;
}

.chat-bubble-user {
  background: transparent;
  box-shadow: none;
}

.chat-bubble-assistant {
  background: transparent;
  border: none;
  box-shadow: none;
}

.chat-empty {
  width: min(100%, 760px);
  margin: auto;
  padding: 56px 32px 72px;
  text-align: center;
}

.chat-empty__badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 32px;
  padding: 0 12px;
  border-radius: 999px;
  background: transparent;
  border: 1px solid rgba(15, 23, 42, 0.12);
  color: #475569;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.chat-empty__title {
  margin-top: 18px;
  font-size: 30px;
  font-weight: 800;
  letter-spacing: -0.04em;
  color: #0f172a;
}

.chat-empty__text {
  margin-top: 14px;
  color: #64748b;
  line-height: 1.8;
  font-size: 15px;
}

@media (max-width: 1080px) {
  .chat-shell {
    grid-template-columns: 1fr;
    min-height: auto;
  }

  .chat-sidebar {
    border-right: none;
    border-bottom: 1px solid rgba(15, 23, 42, 0.08);
    padding-bottom: 18px;
  }

  .chat-session-list {
    max-height: 260px;
  }

  .chat-main__header,
  .chat-composer-wrap,
  .chat-thread {
    padding-left: 20px;
    padding-right: 20px;
  }
}
</style>
