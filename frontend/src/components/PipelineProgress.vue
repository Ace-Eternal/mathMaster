<script setup lang="ts">
defineProps<{
  percentage: number
}>()
</script>

<template>
  <div class="pipeline-progress">
    <el-progress :percentage="percentage" :stroke-width="8" :show-text="false" />
    <span class="pipeline-progress__text">{{ percentage }}%</span>
  </div>
</template>

<style scoped>
.pipeline-progress {
  display: flex;
  align-items: center;
  gap: 12px;
}

.pipeline-progress :deep(.el-progress) {
  flex: 1;
}

.pipeline-progress__text {
  min-width: 42px;
  color: var(--mm-text-soft);
  font-size: 13px;
  font-weight: 600;
}
</style>
