import { createRouter, createWebHistory } from 'vue-router'

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
        { path: '/search', component: SearchPage },
        { path: '/questions/:id', component: QuestionDetailPage, props: true },
        { path: '/settings', component: SettingsPage }
      ]
    }
  ]
})

export default router
