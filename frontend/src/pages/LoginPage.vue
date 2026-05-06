<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const form = reactive({
  username: 'admin',
  password: 'admin123',
})

const submit = async () => {
  if (!form.username.trim() || !form.password) {
    ElMessage.warning('请输入账号和密码。')
    return
  }
  loading.value = true
  try {
    await auth.login(form.username.trim(), form.password)
    ElMessage.success('登录成功。')
    await router.push('/papers')
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '登录失败，请检查账号密码。')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <section class="panel login-panel">
      <div class="page-title">MathMaster</div>
      <p class="page-subtitle">使用本地账号登录。当前版本所有账号默认拥有超级管理员权限，操作会记录到用户审计日志。</p>
      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item label="账号">
          <el-input v-model="form.username" autocomplete="username" @keyup.enter="submit" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" show-password autocomplete="current-password" @keyup.enter="submit" />
        </el-form-item>
        <el-button type="primary" :loading="loading" style="width: 100%" @click="submit">登录</el-button>
      </el-form>
    </section>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
  background: #f5f7fb;
}

.login-panel {
  width: min(100%, 460px);
}
</style>
