<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()

const logout = async () => {
  auth.logout()
  await router.push('/login')
}
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="topbar__brand">
        <div class="brand">MathMaster</div>
        <div class="brand-subtitle">高中数学试卷整理、切片、审核与分析平台</div>
      </div>

      <nav class="topbar__nav">
        <RouterLink class="nav-link" to="/papers">工作台</RouterLink>
        <RouterLink class="nav-link" to="/paper-management">试卷管理</RouterLink>
        <RouterLink class="nav-link" to="/review">人工审核</RouterLink>
        <RouterLink class="nav-link" to="/practice">随机刷题</RouterLink>
        <RouterLink class="nav-link" to="/search">题库搜索</RouterLink>
        <RouterLink class="nav-link" to="/templates">解题模板</RouterLink>
        <RouterLink class="nav-link" to="/profile">个人中心</RouterLink>
        <RouterLink v-if="auth.isSuperAdmin" class="nav-link" to="/users">用户管理</RouterLink>
        <RouterLink v-if="auth.isSuperAdmin" class="nav-link" to="/settings">系统设置</RouterLink>
      </nav>
      <div class="topbar__user">
        <span>{{ auth.user?.display_name || auth.user?.username }}</span>
        <el-button text @click="logout">退出</el-button>
      </div>
    </header>

    <main class="page">
      <RouterView />
    </main>
  </div>
</template>
