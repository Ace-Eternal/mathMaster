<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { api } from '../api/client'
import PracticeStatusBadge from '../components/PracticeStatusBadge.vue'
import { useAuthStore } from '../stores/auth'

type TabKey = 'papers' | 'revisions' | 'practice' | 'favorites' | 'chats' | 'audits'

const auth = useAuthStore()
const loading = ref(false)
const activeTab = ref<TabKey>('papers')
const summary = ref<any>(null)
const auditGroups = ref<any[]>([])

const tabs = reactive<Record<TabKey, { total: number; page: number; pageSize: number; items: any[]; endpoint?: string }>>({
  papers: { total: 0, page: 1, pageSize: 10, items: [], endpoint: '/profile/papers' },
  revisions: { total: 0, page: 1, pageSize: 10, items: [], endpoint: '/profile/revised-questions' },
  practice: { total: 0, page: 1, pageSize: 10, items: [], endpoint: '/profile/practice-questions' },
  favorites: { total: 0, page: 1, pageSize: 10, items: [], endpoint: '/profile/favorites' },
  chats: { total: 0, page: 1, pageSize: 10, items: [], endpoint: '/profile/chat-sessions' },
  audits: { total: 0, page: 1, pageSize: 10, items: [] },
})

const currentTab = computed(() => tabs[activeTab.value])
const displayUser = computed(() => summary.value?.user || auth.user)

const formatDate = (value?: string | null) => {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

const shortText = (value?: string | null) => {
  const text = (value || '').trim()
  if (!text) return '-'
  return text.length > 80 ? `${text.slice(0, 80)}...` : text
}

const loadSummary = async () => {
  summary.value = (await api.get('/profile/summary')).data
}

const loadList = async (key: TabKey = activeTab.value) => {
  if (key === 'audits') {
    const { data } = await api.get('/profile/audit-groups')
    auditGroups.value = data
    tabs.audits.total = data.reduce((sum: number, group: any) => sum + group.total, 0)
    return
  }
  const tab = tabs[key]
  const { data } = await api.get(tab.endpoint || '', {
    params: { page: tab.page, page_size: tab.pageSize },
  })
  tab.total = data.total
  tab.items = data.items
}

const loadCurrent = async () => {
  loading.value = true
  try {
    await Promise.all([loadSummary(), loadList()])
  } finally {
    loading.value = false
  }
}

const handleTabChange = async () => {
  await loadList()
}

const handlePageChange = async (page: number) => {
  currentTab.value.page = page
  await loadList()
}

onMounted(loadCurrent)
</script>

<template>
  <div class="section-stack">
    <div class="page-header">
      <div>
        <div class="page-title">个人中心</div>
        <div class="page-subtitle">查看与你绑定的试卷、题目修订、刷题、收藏、对话和操作记录。</div>
      </div>
      <el-button :loading="loading" @click="loadCurrent">刷新</el-button>
    </div>

    <section class="panel">
      <div class="profile-head">
        <div>
          <div class="profile-name">{{ displayUser?.display_name || displayUser?.username || '-' }}</div>
          <div class="muted">
            {{ displayUser?.username || '-' }} ｜ {{ (displayUser?.roles || []).join('、') || '未分配角色' }} ｜ 最近登录：
            {{ formatDate(displayUser?.last_login_at) }}
          </div>
        </div>
        <el-tag :type="displayUser?.status === 'ACTIVE' ? 'success' : 'info'">{{ displayUser?.status || '-' }}</el-tag>
      </div>
      <div class="stats-grid">
        <div class="stat-card">
          <span>我的试卷</span>
          <strong>{{ summary?.paper_count ?? 0 }}</strong>
        </div>
        <div class="stat-card">
          <span>我的修订</span>
          <strong>{{ summary?.revised_question_count ?? 0 }}</strong>
        </div>
        <div class="stat-card">
          <span>做过的题</span>
          <strong>{{ summary?.practice_count ?? 0 }}</strong>
        </div>
        <div class="stat-card">
          <span>收藏题目</span>
          <strong>{{ summary?.favorite_count ?? 0 }}</strong>
        </div>
        <div class="stat-card">
          <span>讲题对话</span>
          <strong>{{ summary?.chat_session_count ?? 0 }}</strong>
        </div>
        <div class="stat-card">
          <span>操作记录</span>
          <strong>{{ summary?.audit_count ?? 0 }}</strong>
        </div>
      </div>
    </section>

    <section class="panel">
      <el-tabs v-model="activeTab" @tab-change="handleTabChange">
        <el-tab-pane label="我的试卷" name="papers">
          <el-table :data="tabs.papers.items" v-loading="loading" empty-text="暂无与你绑定的试卷">
            <el-table-column prop="title" label="试卷" min-width="220">
              <template #default="{ row }"><RouterLink :to="`/papers/${row.paper_id}`">{{ row.title }}</RouterLink></template>
            </el-table-column>
            <el-table-column prop="grade_level" label="年级" width="100" />
            <el-table-column prop="region" label="地区" width="120" />
            <el-table-column prop="status" label="状态" width="120" />
            <el-table-column label="更新时间" min-width="170">
              <template #default="{ row }">{{ formatDate(row.updated_at) }}</template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="我的修订" name="revisions">
          <el-table :data="tabs.revisions.items" v-loading="loading" empty-text="暂无修订过的题目">
            <el-table-column label="题目" min-width="220">
              <template #default="{ row }">
                <RouterLink :to="`/questions/${row.question_id}`">{{ row.paper_title }} / {{ row.question_no }}</RouterLink>
              </template>
            </el-table-column>
            <el-table-column prop="question_type" label="题型" width="120" />
            <el-table-column prop="review_status" label="审核" width="120" />
            <el-table-column label="题干摘要" min-width="260">
              <template #default="{ row }">{{ shortText(row.stem_text) }}</template>
            </el-table-column>
            <el-table-column label="最后修订" min-width="170">
              <template #default="{ row }">{{ formatDate(row.last_revised_at) }}</template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="我的刷题" name="practice">
          <el-table :data="tabs.practice.items" v-loading="loading" empty-text="暂无刷题记录">
            <el-table-column label="题目" min-width="220">
              <template #default="{ row }"><RouterLink :to="`/questions/${row.question_id}`">{{ row.paper_title }} / {{ row.question_no }}</RouterLink></template>
            </el-table-column>
            <el-table-column label="状态" width="130">
              <template #default="{ row }"><PracticeStatusBadge :status="row.practice_status" /></template>
            </el-table-column>
            <el-table-column label="收藏" width="90">
              <template #default="{ row }">
                <svg class="profile-star" viewBox="0 0 24 24" aria-hidden="true" :class="{ filled: row.is_favorited }">
                  <path d="m12 3.8 2.5 5.1 5.6.8-4 3.9.9 5.6-5-2.7-5 2.7.9-5.6-4-3.9 5.6-.8L12 3.8Z" />
                </svg>
              </template>
            </el-table-column>
            <el-table-column label="更新时间" min-width="170">
              <template #default="{ row }">{{ formatDate(row.updated_at) }}</template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="我的收藏" name="favorites">
          <el-table :data="tabs.favorites.items" v-loading="loading" empty-text="暂无收藏题目">
            <el-table-column label="题目" min-width="220">
              <template #default="{ row }"><RouterLink :to="`/questions/${row.question_id}`">{{ row.paper_title }} / {{ row.question_no }}</RouterLink></template>
            </el-table-column>
            <el-table-column label="刷题状态" width="130">
              <template #default="{ row }"><PracticeStatusBadge :status="row.practice_status" /></template>
            </el-table-column>
            <el-table-column label="收藏时间" min-width="170">
              <template #default="{ row }">{{ formatDate(row.updated_at) }}</template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="我的对话" name="chats">
          <el-table :data="tabs.chats.items" v-loading="loading" empty-text="暂无讲题对话">
            <el-table-column label="对话" min-width="220">
              <template #default="{ row }"><RouterLink :to="`/questions/${row.question_id}`">{{ row.title || `题目 ${row.question_no}` }}</RouterLink></template>
            </el-table-column>
            <el-table-column prop="message_count" label="消息数" width="100" />
            <el-table-column label="最近消息" min-width="260">
              <template #default="{ row }">{{ shortText(row.last_message_preview) }}</template>
            </el-table-column>
            <el-table-column label="更新时间" min-width="170">
              <template #default="{ row }">{{ formatDate(row.updated_at) }}</template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="操作记录" name="audits">
          <div v-loading="loading" class="audit-group-list">
            <div v-for="group in auditGroups" :key="group.group" class="audit-group">
              <div class="section-head">
                <div class="section-title">{{ group.label }}</div>
                <span class="muted">{{ group.total }} 条</span>
              </div>
              <el-table :data="group.items" size="small" empty-text="暂无记录">
                <el-table-column prop="action" label="动作" min-width="160" />
                <el-table-column prop="resource_type" label="对象" width="120" />
                <el-table-column prop="resource_id" label="对象 ID" width="120" />
                <el-table-column label="时间" min-width="170">
                  <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
                </el-table-column>
              </el-table>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>

      <el-pagination
        v-if="activeTab !== 'audits'"
        class="profile-pagination"
        background
        layout="prev, pager, next, total"
        :total="currentTab.total"
        :page-size="currentTab.pageSize"
        :current-page="currentTab.page"
        @current-change="handlePageChange"
      />
    </section>
  </div>
</template>

<style scoped>
.profile-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 18px;
}

.profile-name {
  font-size: 20px;
  font-weight: 700;
  color: var(--mm-text);
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: 12px;
}

.stat-card {
  border: 1px solid var(--mm-border);
  border-radius: 8px;
  padding: 14px;
  background: var(--mm-surface-soft);
}

.stat-card span {
  display: block;
  color: var(--mm-text-soft);
  font-size: 13px;
}

.stat-card strong {
  display: block;
  margin-top: 6px;
  font-size: 24px;
  color: var(--mm-text);
}

.audit-group-list {
  display: grid;
  gap: 18px;
}

.audit-group {
  min-width: 0;
}

.profile-pagination {
  justify-content: flex-end;
  margin-top: 16px;
}

.profile-star {
  width: 18px;
  height: 18px;
  fill: none;
  stroke: var(--mm-text-soft);
  stroke-width: 2;
  stroke-linejoin: round;
}

.profile-star.filled {
  fill: #facc15;
  stroke: #eab308;
}
</style>
