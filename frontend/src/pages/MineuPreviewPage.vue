<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api/client'

const props = defineProps<{ id: string }>()
const preview = ref<any>(null)
const activeTab = ref('paper')

const currentOutput = computed(() => preview.value?.outputs?.[activeTab.value] || null)

onMounted(async () => {
  preview.value = (await api.get(`/papers/${props.id}/mineu-preview`)).data
})
</script>

<template>
  <div v-if="preview" class="section-stack">
    <div class="page-header">
      <div>
        <div class="page-title">MineU 结果查看</div>
        <div class="page-subtitle">
          保留 Markdown、JSON、原始返回和图片块信息，便于核对转换质量并定位切题问题。
        </div>
      </div>
    </div>

    <section class="panel">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="试卷" name="paper" />
        <el-tab-pane label="答案" name="answer" />
      </el-tabs>

      <div v-if="currentOutput" class="section-stack">
        <div class="meta-grid">
          <div class="meta-card">
            <div class="meta-label">Markdown 路径</div>
            <div class="mono meta-value">{{ currentOutput.markdown_path }}</div>
          </div>
          <div class="meta-card">
            <div class="meta-label">JSON 路径</div>
            <div class="mono meta-value">{{ currentOutput.json_path }}</div>
          </div>
          <div class="meta-card">
            <div class="meta-label">原始返回路径</div>
            <div class="mono meta-value">{{ currentOutput.raw_response_path }}</div>
          </div>
        </div>

        <div v-if="currentOutput.image_blocks?.length" class="image-preview-grid">
          <article
            v-for="(image, index) in currentOutput.image_blocks"
            :key="`${index}-${image.image_url || image.caption || 'image'}`"
            class="image-preview-card"
          >
            <img
              v-if="image.image_url"
              :src="image.image_url"
              :alt="image.caption || `图片 ${index + 1}`"
              class="image-preview-card__img"
            />
            <div v-else class="surface-note">当前图片块仅返回元数据，暂无独立图片地址。</div>
            <div class="muted" style="margin-top: 8px">页码：{{ image.page || '-' }} ｜ {{ image.caption || '无标题' }}</div>
          </article>
        </div>

        <div class="grid cols-2">
          <section class="panel preview-panel">
            <h3>Markdown 预览</h3>
            <pre class="mono preview-content">{{ currentOutput.markdown_preview }}</pre>
          </section>
          <section class="panel preview-panel">
            <h3>JSON 预览</h3>
            <pre class="mono preview-content">{{ JSON.stringify(currentOutput.json_preview, null, 2) }}</pre>
          </section>
        </div>
      </div>

      <el-empty v-else description="当前类型暂无转换结果" />
    </section>
  </div>
</template>

<style scoped>
.meta-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.meta-card,
.image-preview-card {
  padding: 16px 18px;
  background: var(--mm-soft);
  border-radius: 18px;
}

.meta-label {
  color: var(--mm-text-soft);
  font-size: 13px;
  margin-bottom: 10px;
}

.meta-value {
  color: var(--mm-text);
  word-break: break-all;
}

.image-preview-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.image-preview-card__img {
  width: 100%;
  max-height: 260px;
  object-fit: contain;
  border-radius: 12px;
  background: #fff;
}

.preview-panel {
  padding: 0;
  overflow: hidden;
}

.preview-panel h3 {
  padding: 20px 22px 0;
}

.preview-content {
  min-height: 420px;
  max-height: 720px;
  overflow: auto;
  padding: 18px 22px 22px;
  white-space: pre-wrap;
  line-height: 1.65;
  color: var(--mm-text);
}

@media (max-width: 1024px) {
  .meta-grid,
  .image-preview-grid {
    grid-template-columns: 1fr;
  }
}
</style>
