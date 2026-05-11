<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../api/client'

type Provider = {
  id: number
  name: string
  base_url: string
  api_key_masked: string | null
  is_enabled: boolean
  remark: string | null
}

type Scenario = {
  id: number
  scenario_code: string
  scenario_name: string
  primary_provider_id: number | null
  primary_model: string | null
  fallback_provider_id: number | null
  fallback_model: string | null
  temperature: number
  is_enabled: boolean
}

type PromptConfig = {
  id: number
  scenario_code: string
  scenario_name: string
  prompt_content: string
}

const loading = ref(false)
const providers = ref<Provider[]>([])
const scenarios = ref<Scenario[]>([])
const prompts = ref<PromptConfig[]>([])
const activeTab = ref('providers')
const providerDialogVisible = ref(false)
const editingProviderId = ref<number | null>(null)
const testingProvider = ref<Provider | null>(null)
const testDialogVisible = ref(false)
const testResult = ref('')

const providerForm = reactive({
  name: '',
  base_url: '',
  api_key: '',
  is_enabled: true,
  remark: '',
})

const testForm = reactive({
  model: '',
  prompt: '请回复 OK',
})

const enabledProviders = computed(() => providers.value.filter((item) => item.is_enabled))

const providerOptions = computed(() =>
  enabledProviders.value.map((item) => ({
    label: item.name,
    value: item.id,
  }))
)

const loadAll = async () => {
  loading.value = true
  try {
    const [providerResponse, scenarioResponse, promptResponse] = await Promise.all([
      api.get('/admin/llm/providers'),
      api.get('/admin/llm/scenarios'),
      api.get('/admin/llm/prompts'),
    ])
    providers.value = providerResponse.data
    scenarios.value = scenarioResponse.data
    prompts.value = promptResponse.data
  } finally {
    loading.value = false
  }
}

const resetProviderForm = () => {
  editingProviderId.value = null
  providerForm.name = ''
  providerForm.base_url = ''
  providerForm.api_key = ''
  providerForm.is_enabled = true
  providerForm.remark = ''
}

const openCreateProvider = () => {
  resetProviderForm()
  providerDialogVisible.value = true
}

const openEditProvider = (provider: Provider) => {
  editingProviderId.value = provider.id
  providerForm.name = provider.name
  providerForm.base_url = provider.base_url
  providerForm.api_key = ''
  providerForm.is_enabled = provider.is_enabled
  providerForm.remark = provider.remark || ''
  providerDialogVisible.value = true
}

const saveProvider = async () => {
  const payload = {
    name: providerForm.name,
    base_url: providerForm.base_url,
    api_key: providerForm.api_key,
    is_enabled: providerForm.is_enabled,
    remark: providerForm.remark,
  }
  if (editingProviderId.value) {
    await api.patch(`/admin/llm/providers/${editingProviderId.value}`, payload)
  } else {
    await api.post('/admin/llm/providers', payload)
  }
  providerDialogVisible.value = false
  ElMessage.success('供应商配置已保存。')
  await loadAll()
}

const deleteProvider = async (provider: Provider) => {
  await ElMessageBox.confirm(`确认删除供应商「${provider.name}」？`, '删除供应商', { type: 'warning' })
  await api.delete(`/admin/llm/providers/${provider.id}`)
  ElMessage.success('供应商已删除。')
  await loadAll()
}

const openTestProvider = (provider: Provider) => {
  testingProvider.value = provider
  testForm.model = ''
  testForm.prompt = '请回复 OK'
  testResult.value = ''
  testDialogVisible.value = true
}

const runProviderTest = async () => {
  if (!testingProvider.value) return
  const { data } = await api.post(`/admin/llm/providers/${testingProvider.value.id}/test`, {
    model: testForm.model,
    prompt: testForm.prompt,
  })
  testResult.value = data.ok ? data.content || '调用成功，但模型返回为空。' : data.error || '调用失败。'
  if (data.ok) ElMessage.success('测试调用成功。')
  else ElMessage.error('测试调用失败。')
}

const saveScenarios = async () => {
  await api.put('/admin/llm/scenarios', { scenarios: scenarios.value })
  ElMessage.success('场景配置已保存，下一次调用立即生效。')
  await loadAll()
}

const savePrompts = async () => {
  await api.put('/admin/llm/prompts', { prompts: prompts.value })
  ElMessage.success('Prompt 已保存，下一次调用立即生效。')
  await loadAll()
}

onMounted(loadAll)
</script>

<template>
  <div class="page-header">
    <div>
      <div class="page-title">系统设置</div>
      <div class="page-subtitle">管理 LLM 供应商、场景模型和 Prompt，保存后立即影响下一次模型调用。</div>
    </div>
  </div>

  <section v-loading="loading" class="panel settings-panel">
    <el-tabs v-model="activeTab">
      <el-tab-pane label="供应商" name="providers">
        <div class="toolbar">
          <el-button type="primary" @click="openCreateProvider">新增供应商</el-button>
        </div>
        <el-table :data="providers" border>
          <el-table-column prop="name" label="名称" min-width="140" />
          <el-table-column prop="base_url" label="Base URL" min-width="260" />
          <el-table-column prop="api_key_masked" label="API Key" min-width="160" />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="row.is_enabled ? 'success' : 'info'">{{ row.is_enabled ? '启用' : '停用' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="remark" label="备注" min-width="180" />
          <el-table-column label="操作" width="220" fixed="right">
            <template #default="{ row }">
              <el-button text type="primary" @click="openEditProvider(row)">编辑</el-button>
              <el-button text type="primary" @click="openTestProvider(row)">测试</el-button>
              <el-button text type="danger" @click="deleteProvider(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="场景模型" name="scenarios">
        <div class="toolbar">
          <el-button type="primary" @click="saveScenarios">保存场景配置</el-button>
        </div>
        <el-table :data="scenarios" border>
          <el-table-column prop="scenario_name" label="场景" min-width="160" />
          <el-table-column label="主供应商" min-width="180">
            <template #default="{ row }">
              <el-select v-model="row.primary_provider_id" clearable style="width: 100%">
                <el-option v-for="item in providerOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="主模型" min-width="180">
            <template #default="{ row }">
              <el-input v-model="row.primary_model" placeholder="如 deepseek-chat" />
            </template>
          </el-table-column>
          <el-table-column label="备用供应商" min-width="180">
            <template #default="{ row }">
              <el-select v-model="row.fallback_provider_id" clearable style="width: 100%">
                <el-option v-for="item in providerOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="备用模型" min-width="180">
            <template #default="{ row }">
              <el-input v-model="row.fallback_model" placeholder="可留空" />
            </template>
          </el-table-column>
          <el-table-column label="温度" width="140">
            <template #default="{ row }">
              <el-input-number v-model="row.temperature" :min="0" :max="2" :step="0.1" controls-position="right" style="width: 100%" />
            </template>
          </el-table-column>
          <el-table-column label="启用" width="90">
            <template #default="{ row }"><el-switch v-model="row.is_enabled" /></template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="Prompt" name="prompts">
        <div class="toolbar">
          <el-button type="primary" @click="savePrompts">保存 Prompt</el-button>
        </div>
        <el-collapse>
          <el-collapse-item v-for="prompt in prompts" :key="prompt.scenario_code" :title="prompt.scenario_name" :name="prompt.scenario_code">
            <el-input v-model="prompt.prompt_content" type="textarea" :autosize="{ minRows: 12, maxRows: 28 }" class="prompt-editor" />
          </el-collapse-item>
        </el-collapse>
      </el-tab-pane>
    </el-tabs>
  </section>

  <el-dialog v-model="providerDialogVisible" :title="editingProviderId ? '编辑供应商' : '新增供应商'" width="640px" destroy-on-close>
    <el-form label-width="100px">
      <el-form-item label="名称"><el-input v-model="providerForm.name" /></el-form-item>
      <el-form-item label="Base URL"><el-input v-model="providerForm.base_url" placeholder="https://api.deepseek.com/v1" /></el-form-item>
      <el-form-item label="API Key">
        <el-input v-model="providerForm.api_key" type="password" show-password :placeholder="editingProviderId ? '留空则不修改' : '请输入 API Key'" />
      </el-form-item>
      <el-form-item label="启用"><el-switch v-model="providerForm.is_enabled" /></el-form-item>
      <el-form-item label="备注"><el-input v-model="providerForm.remark" type="textarea" :rows="3" /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="providerDialogVisible = false">取消</el-button>
      <el-button type="primary" @click="saveProvider">保存</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="testDialogVisible" title="测试供应商" width="640px" destroy-on-close>
    <el-form label-width="100px">
      <el-form-item label="供应商"><el-input :model-value="testingProvider?.name" disabled /></el-form-item>
      <el-form-item label="模型"><el-input v-model="testForm.model" placeholder="如 deepseek-chat" /></el-form-item>
      <el-form-item label="Prompt"><el-input v-model="testForm.prompt" type="textarea" :rows="4" /></el-form-item>
      <el-form-item v-if="testResult" label="结果"><pre class="test-result">{{ testResult }}</pre></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="testDialogVisible = false">关闭</el-button>
      <el-button type="primary" @click="runProviderTest">运行测试</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.settings-panel {
  overflow-x: auto;
}

.toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 16px;
}

.prompt-editor :deep(textarea) {
  font-family: ui-monospace, SFMono-Regular, Consolas, 'Liberation Mono', monospace;
  line-height: 1.55;
}

.test-result {
  width: 100%;
  max-height: 240px;
  overflow: auto;
  padding: 12px;
  margin: 0;
  border-radius: 6px;
  background: #f7f8fa;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
