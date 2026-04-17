<script setup lang="ts">
import { computed } from 'vue'
import { stageTagType, type TaskStage } from '../utils/paperStatus'

const props = defineProps<{
  stage: TaskStage
}>()

const tagType = computed(() => stageTagType(props.stage))
</script>

<template>
  <el-tag :type="tagType" effect="light" round class="status-badge">
    {{ stage }}
  </el-tag>
</template>

<style scoped>
.status-badge {
  font-weight: 600;
  border-radius: 999px;
  padding-inline: 12px;
}
</style>
