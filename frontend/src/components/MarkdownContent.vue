<script setup lang="ts">
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'
import texmath from 'markdown-it-texmath'
import katex from 'katex'
import 'katex/dist/katex.min.css'

const props = defineProps<{
  content?: string | null
}>()

const markdown = new MarkdownIt({
  html: false,
  breaks: true,
  linkify: true,
  typographer: false,
})

markdown.use(texmath, {
  engine: katex,
  delimiters: ['dollars', 'brackets', 'beg_end'],
  katexOptions: {
    throwOnError: false,
    strict: 'ignore',
  },
})

const normalizeMathContent = (rawContent: string) =>
  rawContent
    .replace(/(^|[\r\n])\\\[\s*([\s\S]*?)\s*\\\](?=[\r\n]|$)/g, (_, prefix: string, formula: string) => {
      const normalizedFormula = String(formula || '').trim()
      return `${prefix}\n$$\n${normalizedFormula}\n$$\n`
    })
    .replace(/\\\((.+?)\\\)/g, (_, formula: string) => `$${String(formula || '').trim()}$`)
    .replace(/(^|[\r\n])(\\begin\{[a-zA-Z*]+\}[\s\S]*?\\end\{[a-zA-Z*]+\})(?=[\r\n]|$)/g, (_, prefix: string, block: string) => {
      const normalizedBlock = String(block || '').trim()
      return `${prefix}\n$$\n${normalizedBlock}\n$$\n`
    })

const renderedHtml = computed(() => {
  const content = props.content?.trim()
  if (!content) {
    return ''
  }
  return markdown.render(normalizeMathContent(content))
})
</script>

<template>
  <div v-if="renderedHtml" class="markdown-content" v-html="renderedHtml"></div>
  <div v-else class="muted">暂无内容。</div>
</template>

<style scoped>
.markdown-content {
  max-width: 100%;
  min-width: 0;
  overflow-x: hidden;
  line-height: 1.8;
  color: var(--mm-ink);
  word-break: break-word;
  overflow-wrap: anywhere;
}

.markdown-content :deep(p) {
  max-width: 100%;
  overflow-x: auto;
  overflow-y: hidden;
  margin: 0 0 12px;
  padding-bottom: 2px;
}

.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  max-width: 100%;
  overflow-x: auto;
  margin: 0 0 12px;
  padding-left: 22px;
}

.markdown-content :deep(li) {
  margin-bottom: 6px;
}

.markdown-content :deep(blockquote) {
  margin: 12px 0;
  padding: 10px 14px;
  border-left: 4px solid rgba(15, 23, 42, 0.2);
  background: rgba(15, 23, 42, 0.04);
  border-radius: 12px;
}

.markdown-content :deep(pre) {
  max-width: 100%;
  overflow-x: auto;
  margin: 12px 0;
  padding: 12px 14px;
  border-radius: 14px;
  background: #0f172a;
  color: #f8fafc;
}

.markdown-content :deep(code) {
  font-family: 'Consolas', 'Courier New', monospace;
}

.markdown-content :deep(table) {
  display: block;
  max-width: 100%;
  overflow-x: auto;
  border-collapse: collapse;
}

.markdown-content :deep(img) {
  max-width: 100%;
  border-radius: 12px;
}

.markdown-content :deep(.katex) {
  max-width: 100%;
}

.markdown-content :deep(.katex-display) {
  max-width: 100%;
  overflow-x: auto;
  overflow-y: hidden;
  padding: 6px 0;
}

.markdown-content :deep(.katex-display > .katex) {
  overflow-x: auto;
  overflow-y: hidden;
}
</style>
