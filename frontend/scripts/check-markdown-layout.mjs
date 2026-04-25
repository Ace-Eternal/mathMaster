import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const componentPath = resolve(scriptDir, '../src/components/MarkdownContent.vue')
const reviewPagePath = resolve(scriptDir, '../src/pages/ReviewPage.vue')
const questionDetailPagePath = resolve(scriptDir, '../src/pages/QuestionDetailPage.vue')
const markdownSource = readFileSync(componentPath, 'utf-8')
const reviewPageSource = readFileSync(reviewPagePath, 'utf-8')
const questionDetailPageSource = readFileSync(questionDetailPagePath, 'utf-8')

const requiredMarkdownSnippets = [
  '.markdown-content {\n  max-width: 100%;\n  min-width: 0;\n  overflow-x: hidden;',
  '.markdown-content :deep(p) {\n  max-width: 100%;\n  overflow-x: auto;',
  '.markdown-content :deep(.katex) {\n  max-width: 100%;',
  '.markdown-content :deep(.katex-display > .katex) {\n  overflow-x: auto;',
  '.markdown-content :deep(table) {\n  display: block;\n  max-width: 100%;\n  overflow-x: auto;',
]

const requiredReviewSnippets = [
  '.review-content-grid {\n  display: grid;\n  grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr);',
  '.preview-panel,\n.pdf-panel {\n  min-width: 0;\n  max-width: 100%;',
  '.review-edit-form,\n.review-edit-form :deep(.el-form),\n.review-edit-form :deep(.el-form-item),\n.review-edit-form :deep(.el-form-item__content) {\n  min-width: 0;',
  '.review-edit-form :deep(.el-input),\n.review-edit-form :deep(.el-select),\n.review-edit-form :deep(.el-textarea),\n.review-edit-form :deep(.el-input__wrapper),\n.review-edit-form :deep(.el-select__wrapper),\n.review-edit-form :deep(.el-textarea__inner) {\n  width: 100%;',
  '.raw-textarea :deep(.el-textarea__inner) {\n  overflow-x: auto;\n  white-space: pre;',
  '.question-preview-surface,\n.answer-preview-surface {\n  overflow-x: auto;\n  overflow-y: hidden;',
  '.question-preview-surface :deep(.markdown-content),\n.answer-preview-surface :deep(.markdown-content) {\n  width: max-content;\n  min-width: 100%;\n  max-width: none;\n  overflow-x: visible;',
  '.question-preview-surface :deep(.markdown-content .katex-display > .katex),',
  '.answer-preview-surface :deep(.markdown-content .katex-display > .katex) {\n  max-width: none;\n  overflow-x: visible;',
  '.edit-preview-block,\n.surface-note {\n  min-width: 0;\n  max-width: 100%;',
  '@media (max-width: 1280px) {\n  .review-content-grid {\n    grid-template-columns: 1fr;',
]

const requiredQuestionDetailSnippets = [
  '.detail-markdown-surface {\n  min-width: 0;\n  max-width: 100%;\n  overflow-x: auto;\n  overflow-y: hidden;',
  '.detail-markdown-surface :deep(.markdown-content) {\n  width: max-content;\n  min-width: 100%;\n  max-width: none;\n  overflow-x: visible;',
  '.detail-markdown-surface :deep(.markdown-content .katex-display > .katex) {\n  max-width: none;\n  overflow-x: visible;',
]

const missing = [
  ...requiredMarkdownSnippets
    .filter((snippet) => !markdownSource.includes(snippet))
    .map((snippet) => ({ file: componentPath, snippet })),
  ...requiredReviewSnippets
    .filter((snippet) => !reviewPageSource.includes(snippet))
    .map((snippet) => ({ file: reviewPagePath, snippet })),
  ...requiredQuestionDetailSnippets
    .filter((snippet) => !questionDetailPageSource.includes(snippet))
    .map((snippet) => ({ file: questionDetailPagePath, snippet })),
]

if (missing.length) {
  console.error('Markdown layout guard failed. Missing snippets:')
  for (const { file, snippet } of missing) {
    console.error(`File: ${file}`)
    console.error(`- ${snippet.replaceAll('\n', '\\n')}`)
  }
  process.exit(1)
}

console.log('Markdown layout guard passed.')
