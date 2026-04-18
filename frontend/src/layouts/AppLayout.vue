<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="topbar__brand">
        <div class="brand">MathMaster</div>
        <div class="brand-subtitle">高中数学试卷整理、切片、审核与分析平台</div>
      </div>

      <nav class="topbar__nav">
        <RouterLink class="nav-link" to="/papers">工作台</RouterLink>
        <RouterLink class="nav-link" to="/review">人工审核</RouterLink>
        <RouterLink class="nav-link" to="/search">题库搜索</RouterLink>
        <RouterLink class="nav-link" to="/settings">系统设置</RouterLink>
      </nav>
    </header>

    <main class="page">
      <RouterView />
    </main>
  </div>
</template>
