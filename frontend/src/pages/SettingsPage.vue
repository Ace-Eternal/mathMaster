<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api/client'

const settings = ref<any>(null)

onMounted(async () => {
  settings.value = (await api.get('/settings')).data
})
</script>

<template>
  <div class="page-header">
    <div>
      <div class="page-title">系统设置</div>
      <div class="page-subtitle">
        当前页面用于查看运行模式、存储后端、数据库和模型配置，便于本地联调和部署排查。
      </div>
    </div>
  </div>

  <section class="panel">
    <pre class="mono" style="white-space: pre-wrap">{{ JSON.stringify(settings, null, 2) }}</pre>
  </section>
</template>
