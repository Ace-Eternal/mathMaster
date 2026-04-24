<script setup lang="ts">
import ExpandableText from './ExpandableText.vue'
import PipelineProgress from './PipelineProgress.vue'
import StatusBadge from './StatusBadge.vue'
import type { TaskListItem } from '../utils/paperStatus'

defineProps<{
  items: TaskListItem[]
  loading?: boolean
  runningPaperIds?: Set<number>
}>()

const emit = defineEmits<{
  rerun: [paperId: number]
}>()

const formatTime = (value: string | null) => {
  if (!value) return '刚刚'
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

const isQueueActive = (row: TaskListItem) => row.queueStatus === 'QUEUED' || row.queueStatus === 'RUNNING'

const actionText = (row: TaskListItem) => {
  if (row.queueStatus === 'QUEUED') return '已入队'
  if (row.queueStatus === 'RUNNING') return '运行中'
  return '重新运行'
}
</script>

<template>
  <section class="panel">
    <div class="section-head">
      <div>
        <div class="section-title">任务状态列表</div>
        <div class="muted">集中展示当前试卷任务的状态、进度、错误和结果摘要。</div>
      </div>
    </div>

    <el-table :data="items" v-loading="loading" class="task-table">
      <el-table-column label="试卷任务" min-width="260">
        <template #default="{ row }">
          <div class="task-title-cell">
            <div class="task-title">{{ row.title }}</div>
            <div class="task-subline">
              <span>{{ row.sourceLabel }}</span>
              <span>更新于 {{ formatTime(row.updatedAt) }}</span>
            </div>
          </div>
        </template>
      </el-table-column>

      <el-table-column label="状态" width="140">
        <template #default="{ row }">
          <StatusBadge :stage="row.stage" />
        </template>
      </el-table-column>

      <el-table-column label="整体进度" min-width="220">
        <template #default="{ row }">
          <PipelineProgress :percentage="row.progress" />
        </template>
      </el-table-column>

      <el-table-column label="结果摘要" min-width="300">
        <template #default="{ row }">
          <div class="result-grid">
            <span class="result-pill" :class="{ alert: !row.hasAnswer }">
              {{ row.hasAnswer ? '答案已配对' : '缺失答案' }}
            </span>
            <span class="result-pill" :class="{ ok: row.mineuSuccess }">
              {{ row.mineuSuccess ? 'MineU 已完成' : 'MineU 未完成' }}
            </span>
            <span class="result-pill">切题 {{ row.questionCount }} 道</span>
            <span class="result-pill" :class="{ alert: row.pendingReviewCount > 0 }">
              待审核 {{ row.pendingReviewCount }} 道
            </span>
          </div>
          <div v-if="row.errorSummary" class="error-line">
            <ExpandableText :text="row.errorSummary" tone="error" :limit="120" />
          </div>
          <div v-else-if="row.note" class="muted inline-note">
            <ExpandableText :text="row.note" :limit="120" />
          </div>
        </template>
      </el-table-column>

      <el-table-column label="操作" width="260" fixed="right">
        <template #default="{ row }">
          <div class="actions">
            <RouterLink v-if="row.paperId" :to="`/papers/${row.paperId}`">
              <el-button text>查看详情</el-button>
            </RouterLink>
            <RouterLink v-if="row.paperId" :to="`/papers/${row.paperId}/mineu`">
              <el-button text>MineU 结果</el-button>
            </RouterLink>
            <RouterLink v-if="row.paperId && row.pendingReviewCount > 0" to="/review">
              <el-button text type="warning">去审核</el-button>
            </RouterLink>
            <el-button
              v-if="row.paperId && !row.isTransient"
              text
              type="primary"
              :loading="runningPaperIds?.has(row.paperId)"
              :disabled="runningPaperIds?.has(row.paperId) || isQueueActive(row)"
              @click="emit('rerun', row.paperId)"
            >
              {{ actionText(row) }}
            </el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>
  </section>
</template>

<style scoped>
.section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.section-title {
  color: var(--mm-text);
  font-size: 20px;
  font-weight: 700;
  margin-bottom: 6px;
}

.task-title {
  color: var(--mm-text);
  font-weight: 700;
  line-height: 1.4;
}

.task-subline {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 8px;
  color: var(--mm-text-soft);
  font-size: 12px;
}

.result-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.result-pill {
  border-radius: 999px;
  padding: 6px 10px;
  background: var(--mm-soft);
  color: var(--mm-text-soft);
  font-size: 12px;
  font-weight: 600;
}

.result-pill.ok {
  background: rgba(40, 167, 69, 0.08);
  color: #1d7a37;
}

.result-pill.alert {
  background: rgba(242, 153, 74, 0.12);
  color: #b26a11;
}

.error-line {
  margin-top: 10px;
  color: #c24141;
  font-size: 13px;
  line-height: 1.5;
}

.inline-note {
  margin-top: 10px;
  line-height: 1.5;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.task-table :deep(.el-table__cell) {
  padding: 18px 0;
}
</style>
