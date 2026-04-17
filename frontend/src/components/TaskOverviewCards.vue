<script setup lang="ts">
const props = defineProps<{
  summary: {
    total: number
    queued: number
    processing: number
    completed: number
    failed: number
    review: number
  }
}>()

const cards = [
  { key: 'total', label: '任务总数', tone: 'neutral' },
  { key: 'queued', label: '待处理', tone: 'soft' },
  { key: 'processing', label: '处理中', tone: 'primary' },
  { key: 'completed', label: '已完成', tone: 'success' },
  { key: 'failed', label: '失败', tone: 'danger' },
  { key: 'review', label: '待审核', tone: 'warning' }
] as const
</script>

<template>
  <div class="overview-grid">
    <article
      v-for="card in cards"
      :key="card.key"
      class="overview-card"
      :data-tone="card.tone"
    >
      <div class="overview-card__label">{{ card.label }}</div>
      <div class="overview-card__value">{{ props.summary[card.key] }}</div>
    </article>
  </div>
</template>

<style scoped>
.overview-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 16px;
}

.overview-card {
  padding: 20px;
  border-radius: 20px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(247, 249, 252, 0.94));
  border: 1px solid var(--mm-border);
  box-shadow: var(--mm-shadow-soft);
}

.overview-card__label {
  color: var(--mm-text-soft);
  font-size: 13px;
  margin-bottom: 12px;
}

.overview-card__value {
  color: var(--mm-text);
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.03em;
}

.overview-card[data-tone='primary'] {
  background: linear-gradient(180deg, rgba(240, 247, 255, 0.98), rgba(235, 243, 255, 0.95));
}

.overview-card[data-tone='success'] {
  background: linear-gradient(180deg, rgba(243, 251, 247, 0.98), rgba(236, 248, 242, 0.95));
}

.overview-card[data-tone='warning'] {
  background: linear-gradient(180deg, rgba(255, 250, 240, 0.98), rgba(255, 246, 230, 0.96));
}

.overview-card[data-tone='danger'] {
  background: linear-gradient(180deg, rgba(255, 245, 245, 0.98), rgba(255, 238, 238, 0.96));
}

@media (max-width: 1280px) {
  .overview-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .overview-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
