<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api/client'
import PipelineProgress from '../components/PipelineProgress.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { deriveTaskFromPaper } from '../utils/paperStatus'

const props = defineProps<{ id: string }>()
const paper = ref<any>(null)

const load = async () => {
  paper.value = (await api.get(`/papers/${props.id}`)).data
}

const task = computed(() => (paper.value ? deriveTaskFromPaper(paper.value) : null))

onMounted(load)
</script>

<template>
  <div v-if="paper && task" class="section-stack">
    <div class="page-header">
      <div>
        <div class="page-title">{{ paper.title }}</div>
        <div class="page-subtitle">
          这里汇总当前试卷的文件信息、流程状态、MineU 转换记录和切片结果，便于快速判断是否需要继续审核或重跑。
        </div>
      </div>
    </div>

    <div class="grid cols-2">
      <section class="panel">
        <h3>试卷概览</h3>
        <div class="detail-list">
          <div class="detail-row"><span>状态</span><StatusBadge :stage="task.stage" /></div>
          <div class="detail-row"><span>年份</span><strong>{{ paper.year || '未识别' }}</strong></div>
          <div class="detail-row"><span>年级</span><strong>{{ paper.grade_level || '未识别' }}</strong></div>
          <div class="detail-row"><span>地区</span><strong>{{ paper.region || '未填写' }}</strong></div>
          <div class="detail-row"><span>学期</span><strong>{{ paper.term || '未填写' }}</strong></div>
        </div>

        <div style="height: 18px" />
        <PipelineProgress :percentage="task.progress" />
        <div v-if="task.note" class="surface-note" style="margin-top: 16px">{{ task.note }}</div>
        <div v-if="task.errorSummary" class="surface-note detail-error" style="margin-top: 16px">
          {{ task.errorSummary }}
        </div>
      </section>

      <section class="panel">
        <h3>原始文件</h3>
        <div class="detail-list">
          <div class="detail-block">
            <div class="detail-label">试卷 PDF</div>
            <div class="mono detail-path">{{ paper.paper_pdf_path }}</div>
          </div>
          <div class="detail-block">
            <div class="detail-label">答案 PDF</div>
            <div class="mono detail-path">{{ paper.answer_sheet?.answer_pdf_path || '缺失答案文件' }}</div>
          </div>
          <div class="detail-row"><span>答案状态</span><strong>{{ paper.answer_sheet?.has_answer ? '已匹配' : '缺失答案' }}</strong></div>
          <div class="detail-row"><span>待审核题数</span><strong>{{ paper.pending_review_count }}</strong></div>
          <div class="detail-row"><span>切题数量</span><strong>{{ paper.questions?.length || 0 }}</strong></div>
        </div>
      </section>
    </div>

    <section class="panel">
      <h3>MineU 转换任务</h3>
      <el-table :data="paper.conversion_jobs || []">
        <el-table-column prop="job_type" label="任务类型" width="120" />
        <el-table-column prop="status" label="状态" width="120" />
        <el-table-column prop="markdown_path" label="Markdown 路径" min-width="240" />
        <el-table-column prop="json_path" label="JSON 路径" min-width="240" />
        <el-table-column prop="error_message" label="错误信息" min-width="220" />
      </el-table>
    </section>

    <section class="panel">
      <h3>切片结果</h3>
      <el-table :data="paper.questions || []">
        <el-table-column prop="question_no" label="题号" width="100" />
        <el-table-column prop="question_type" label="题型" width="120" />
        <el-table-column prop="stem_text" label="题干" min-width="380" />
        <el-table-column prop="review_status" label="审核状态" width="140" />
        <el-table-column prop="review_note" label="提示信息" min-width="220" />
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <RouterLink :to="`/questions/${row.id}`"><el-button text>查看</el-button></RouterLink>
            <RouterLink :to="`/review/${row.id}`"><el-button text type="warning">审核</el-button></RouterLink>
          </template>
        </el-table-column>
      </el-table>
    </section>
  </div>
</template>

<style scoped>
.detail-list {
  display: grid;
  gap: 14px;
}

.detail-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  color: var(--mm-text-soft);
}

.detail-row strong {
  color: var(--mm-text);
}

.detail-block {
  padding: 14px 16px;
  background: var(--mm-soft);
  border-radius: 16px;
}

.detail-label {
  color: var(--mm-text-soft);
  font-size: 13px;
  margin-bottom: 8px;
}

.detail-path {
  color: var(--mm-text);
  word-break: break-all;
}

.detail-error {
  color: #b42318;
  background: rgba(254, 242, 242, 0.92);
}
</style>
