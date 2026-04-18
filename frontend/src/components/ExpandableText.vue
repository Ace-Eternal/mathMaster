<script setup lang="ts">
import { computed, ref } from 'vue'

const props = withDefaults(
  defineProps<{
    text?: string | null
    limit?: number
    emptyText?: string
    tone?: 'default' | 'error'
  }>(),
  {
    text: '',
    limit: 140,
    emptyText: '暂无内容',
    tone: 'default',
  }
)

const expanded = ref(false)

const normalizedText = computed(() => (props.text || '').trim())
const shouldCollapse = computed(() => normalizedText.value.length > props.limit)
const previewText = computed(() => {
  if (!shouldCollapse.value) return normalizedText.value
  return `${normalizedText.value.slice(0, props.limit).trim()}...`
})
</script>

<template>
  <div class="expandable-text" :class="`tone-${tone}`">
    <div v-if="!normalizedText" class="empty-text">
      {{ emptyText }}
    </div>
    <template v-else>
      <div class="text-body">
        {{ expanded ? normalizedText : previewText }}
      </div>
      <el-button
        v-if="shouldCollapse"
        text
        type="primary"
        class="toggle-button"
        @click="expanded = !expanded"
      >
        {{ expanded ? '收起' : '展开详情' }}
      </el-button>
    </template>
  </div>
</template>

<style scoped>
.expandable-text {
  min-width: 0;
}

.text-body {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.6;
}

.tone-error .text-body {
  color: #c24141;
}

.empty-text {
  color: var(--mm-text-soft);
}

.toggle-button {
  margin-top: 6px;
  padding: 0;
}
</style>
