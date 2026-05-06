import { createRouter, createWebHistory } from 'vue-router'
import { ElMessage } from 'element-plus'

import AppLayout from '../layouts/AppLayout.vue'
import LoginPage from '../pages/LoginPage.vue'
import PaperListPage from '../pages/PaperListPage.vue'
import PaperManagePage from '../pages/PaperManagePage.vue'
import PaperDetailPage from '../pages/PaperDetailPage.vue'
import MineuPreviewPage from '../pages/MineuPreviewPage.vue'
import ReviewPage from '../pages/ReviewPage.vue'
import DictionaryPage from '../pages/DictionaryPage.vue'
import SearchPage from '../pages/SearchPage.vue'
import QuestionDetailPage from '../pages/QuestionDetailPage.vue'
import SettingsPage from '../pages/SettingsPage.vue'
import SolutionTemplatePage from '../pages/SolutionTemplatePage.vue'
import PracticePage from '../pages/PracticePage.vue'
import ProfilePage from '../pages/ProfilePage.vue'
import UserManagePage from '../pages/UserManagePage.vue'
import { useAuthStore } from '../stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: LoginPage },
    {
      path: '/',
      component: AppLayout,
      children: [
        { path: '', redirect: '/papers' },
        { path: '/papers', component: PaperListPage },
        { path: '/paper-management', component: PaperManagePage },
        { path: '/papers/:id', component: PaperDetailPage, props: true },
        { path: '/papers/:id/mineu', component: MineuPreviewPage, props: true },
        { path: '/review', component: ReviewPage },
        { path: '/review/:questionId', component: ReviewPage, props: true },
        { path: '/dictionary', component: DictionaryPage },
        { path: '/templates', component: SolutionTemplatePage },
        { path: '/practice', component: PracticePage },
        { path: '/profile', component: ProfilePage },
        { path: '/users', component: UserManagePage },
        { path: '/search', component: SearchPage },
        { path: '/questions/:id', component: QuestionDetailPage, props: true },
        { path: '/settings', component: SettingsPage }
      ]
    }
  ]
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.initialized) {
    await auth.loadMe()
  }
  if (to.path !== '/login' && !auth.isAuthenticated) {
    return '/login'
  }
  if (to.path === '/login' && auth.isAuthenticated) {
    return '/papers'
  }
  if (to.path === '/users' && !auth.isSuperAdmin) {
    ElMessage.warning('无权限访问用户管理。')
    return '/profile'
  }
  return true
})

export default router
