<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import MarkdownContent from '../components/MarkdownContent.vue'
import { templatesApi, type SolutionTemplate } from '../api/templates'

const loading = ref(false)
const saving = ref(false)
const keyword = ref('')
const dialogVisible = ref(false)
const activeTab = ref('edit')
const templates = ref<SolutionTemplate[]>([])
const editingTemplate = ref<SolutionTemplate | null>(null)

const form = reactive({
  name: '',
  description: '',
  content: '',
  tags: [] as string[],
})

const dialogTitle = computed(() => (editingTemplate.value ? '编辑解题模板' : '新建解题模板'))

const splitTags = (value?: string | null) =>
  (value || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)

const joinTags = (items: string[]) => {
  const uniqueTags = Array.from(new Set(items.map((item) => item.trim()).filter(Boolean)))
  return uniqueTags.length ? uniqueTags.join(',') : null
}

const formatTime = (value?: string | null) => {
  if (!value) return '暂无时间'
  return new Date(value).toLocaleString()
}

const previewContent = (content: string) => {
  const normalized = content.trim()
  if (normalized.length <= 360) return normalized
  return `${normalized.slice(0, 360)}...`
}

const resetForm = () => {
  editingTemplate.value = null
  activeTab.value = 'edit'
  form.name = ''
  form.description = ''
  form.content = ''
  form.tags = []
}

const loadTemplates = async () => {
  loading.value = true
  try {
    templates.value = await templatesApi.list(keyword.value.trim() || undefined)
  } finally {
    loading.value = false
  }
}

const openCreate = () => {
  resetForm()
  dialogVisible.value = true
}

const openEdit = (item: SolutionTemplate) => {
  editingTemplate.value = item
  activeTab.value = 'edit'
  form.name = item.name
  form.description = item.description || ''
  form.content = item.content || ''
  form.tags = splitTags(item.tags)
  dialogVisible.value = true
}

const saveTemplate = async () => {
  if (!form.name.trim()) {
    ElMessage.warning('请填写模板名称。')
    return
  }
  saving.value = true
  try {
    const payload = {
      name: form.name.trim(),
      description: form.description.trim() || null,
      content: form.content,
      tags: joinTags(form.tags),
    }
    if (editingTemplate.value) {
      await templatesApi.update(editingTemplate.value.id, payload)
      ElMessage.success('解题模板已更新。')
    } else {
      await templatesApi.create(payload)
      ElMessage.success('解题模板已创建。')
    }
    dialogVisible.value = false
    resetForm()
    await loadTemplates()
  } finally {
    saving.value = false
  }
}

const deleteTemplate = async (item: SolutionTemplate) => {
  await ElMessageBox.confirm(`确认删除解题模板“${item.name}”吗？对应 Markdown 文件也会被删除。`, '删除解题模板', {
    type: 'warning',
  })
  await templatesApi.delete(item.id)
  ElMessage.success('解题模板已删除。')
  await loadTemplates()
}

onMounted(loadTemplates)
</script>

<template>
  <div class="section-stack">
    <div class="page-header">
      <div>
        <div class="page-title">解题模板</div>
        <div class="page-subtitle">维护常用解题结构、评分步骤和讲解格式，模板正文会同步保存为 Markdown 文档。</div>
      </div>
      <div class="action-row">
        <el-button :loading="loading" @click="loadTemplates">刷新</el-button>
        <el-button type="primary" @click="openCreate">新建模板</el-button>
      </div>
    </div>

    <section class="panel">
      <div class="template-toolbar">
        <el-input
          v-model="keyword"
          clearable
          placeholder="搜索名称、简介或标签"
          @keyup.enter="loadTemplates"
          @clear="loadTemplates"
        />
        <el-button type="primary" :loading="loading" @click="loadTemplates">搜索</el-button>
      </div>
    </section>

    <section v-loading="loading" class="template-grid">
      <article v-for="item in templates" :key="item.id" class="template-card">
        <div class="template-card__header">
          <div class="template-card__meta">
            <h3>{{ item.name }}</h3>
            <div class="muted template-card__time">更新于 {{ formatTime(item.updated_at) }}</div>
          </div>
        </div>

        <p v-if="item.description" class="template-description">{{ item.description }}</p>
        <div v-if="splitTags(item.tags).length" class="tag-row">
          <el-tag v-for="tag in splitTags(item.tags)" :key="tag" effect="plain">{{ tag }}</el-tag>
        </div>

        <div class="template-actions">
          <el-button text type="primary" @click="openEdit(item)">编辑</el-button>
          <el-button text type="danger" @click="deleteTemplate(item)">删除</el-button>
        </div>

        <div class="template-preview">
          <MarkdownContent :content="previewContent(item.content)" />
        </div>
      </article>

      <el-empty v-if="!loading && templates.length === 0" description="暂无解题模板" />
    </section>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="860px" destroy-on-close @closed="resetForm">
      <el-form label-position="top">
        <div class="grid cols-2">
          <el-form-item label="名称">
            <el-input v-model="form.name" placeholder="例如：函数导数压轴题模板" />
          </el-form-item>
          <el-form-item label="标签">
            <el-select
              v-model="form.tags"
              multiple
              filterable
              allow-create
              default-first-option
              style="width: 100%"
              placeholder="输入后回车创建标签"
            />
          </el-form-item>
        </div>
        <el-form-item label="简介">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="说明模板适用场景" />
        </el-form-item>
        <el-form-item label="内容">
          <el-tabs v-model="activeTab" class="template-editor-tabs">
            <el-tab-pane label="编辑" name="edit">
              <el-input
                v-model="form.content"
                type="textarea"
                :rows="16"
                resize="vertical"
                placeholder="编写 Markdown 模板，支持 $LaTeX$ 公式"
              />
            </el-tab-pane>
            <el-tab-pane label="预览" name="preview">
              <div class="dialog-preview">
                <MarkdownContent :content="form.content" />
              </div>
            </el-tab-pane>
          </el-tabs>
        </el-form-item>
      </el-form>

      <template #footer>
        <div class="action-row" style="justify-content: flex-end">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="saving" @click="saveTemplate">保存</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.template-toolbar {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) auto;
  gap: 12px;
}

.template-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 18px;
  min-height: 180px;
}

.template-card {
  display: grid;
  gap: 14px;
  min-width: 0;
  padding: 20px;
  border: 1px solid var(--mm-border);
  border-radius: var(--mm-radius-md);
  background: rgba(255, 255, 255, 0.96);
  box-shadow: var(--mm-shadow-soft);
}

.template-card__header {
  display: grid;
  gap: 10px;
}

.template-card__meta {
  min-width: 0;
}

.template-card__time {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.template-actions {
  display: inline-flex;
  align-items: center;
  justify-content: flex-start;
  flex: 0 0 auto;
  gap: 8px;
  white-space: nowrap;
}

.template-card h3 {
  margin: 0 0 6px;
  font-size: 18px;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.template-description {
  margin: 0;
  color: var(--mm-text-soft);
  line-height: 1.7;
}

.template-preview,
.dialog-preview {
  min-height: 160px;
  max-height: 360px;
  overflow: auto;
  padding: 16px;
  border: 1px solid var(--mm-border);
  border-radius: var(--mm-radius-md);
  background: var(--mm-soft);
}

.template-editor-tabs {
  width: 100%;
}

@media (max-width: 768px) {
  .template-toolbar,
  .template-grid {
    grid-template-columns: 1fr;
  }
}
</style>
