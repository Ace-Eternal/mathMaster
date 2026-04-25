import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const componentPath = resolve(scriptDir, '../src/components/MarkdownContent.vue')
const source = readFileSync(componentPath, 'utf-8')

const requiredSnippets = [
  '.markdown-content {\n  max-width: 100%;\n  min-width: 0;\n  overflow-x: hidden;',
  '.markdown-content :deep(p) {\n  max-width: 100%;\n  overflow-x: auto;',
  '.markdown-content :deep(.katex) {\n  max-width: 100%;',
  '.markdown-content :deep(.katex-display > .katex) {\n  overflow-x: auto;',
  '.markdown-content :deep(table) {\n  display: block;\n  max-width: 100%;\n  overflow-x: auto;',
]

const missing = requiredSnippets.filter((snippet) => !source.includes(snippet))

if (missing.length) {
  console.error('Markdown layout guard failed. Missing snippets:')
  for (const snippet of missing) {
    console.error(`- ${snippet.replaceAll('\n', '\\n')}`)
  }
  process.exit(1)
}

console.log('Markdown layout guard passed.')
