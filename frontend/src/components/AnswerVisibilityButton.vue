<script setup lang="ts">
defineProps<{ visible: boolean }>()
defineEmits<{ toggle: [] }>()
</script>

<template>
  <el-button class="answer-visibility-button" @click="$emit('toggle')">
    <svg v-if="visible" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M3 3l18 18" />
      <path d="M10.7 5.2A10.7 10.7 0 0 1 12 5c5.5 0 9 5.1 9 7a5.9 5.9 0 0 1-1.4 2.5" />
      <path d="M6.6 6.8C4.4 8.2 3 10.6 3 12c0 1.9 3.5 7 9 7 1.5 0 2.8-.4 4-1" />
      <path d="M10.5 10.5a2.1 2.1 0 0 0 3 3" />
      <path d="M14.7 9.4a3.2 3.2 0 0 0-4.3 4.3" />
    </svg>
    <svg v-else viewBox="0 0 24 24" aria-hidden="true">
      <path d="M3 12c0-1.9 3.5-7 9-7s9 5.1 9 7-3.5 7-9 7-9-5.1-9-7Z" />
      <circle cx="12" cy="12" r="3.2" />
    </svg>
    <span>{{ visible ? '隐藏答案' : '显示答案' }}</span>
  </el-button>
</template>

<style scoped>
.answer-visibility-button {
  gap: 8px;
}

.answer-visibility-button svg {
  width: 18px;
  height: 18px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2;
  stroke-linecap: round;
  stroke-linejoin: round;
}
</style>
