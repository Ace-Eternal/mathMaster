<script setup lang="ts">
const props = defineProps<{ status?: string | null }>()

const statusMap: Record<string, { label: string; tone: string }> = {
  NOT_STARTED: { label: '未解决', tone: 'not-started' },
  IN_PROGRESS: { label: '解决中', tone: 'in-progress' },
  SOLVED: { label: '已解决', tone: 'solved' },
}

const item = () => statusMap[props.status || 'NOT_STARTED'] || statusMap.NOT_STARTED
</script>

<template>
  <span class="practice-status-badge" :class="`practice-status-badge--${item().tone}`">
    <span class="practice-status-badge__dot" />
    <span>{{ item().label }}</span>
  </span>
</template>

<style scoped>
.practice-status-badge {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  white-space: nowrap;
  color: var(--mm-text);
  font-weight: 700;
}

.practice-status-badge__dot {
  width: 11px;
  height: 11px;
  border-radius: 999px;
  background: #fff;
  box-shadow: inset 0 0 0 1.5px rgba(15, 23, 42, 0.24);
}

.practice-status-badge--in-progress .practice-status-badge__dot {
  background: #facc15;
  box-shadow: none;
}

.practice-status-badge--solved .practice-status-badge__dot {
  background: #22c55e;
  box-shadow: none;
}
</style>
