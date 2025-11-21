import { createRouter, createWebHistory } from 'vue-router'
import AiModule from '../views/ai/AiModule.vue'

const routes = [
  {
    path: '/',
    redirect: '/ai/test-case-generator'
  },
  {
    path: '/ai',
    component: AiModule,
    children: [
      { path: '', redirect: '/ai/test-case-generator' },
      {
        path: 'test-case-generator',
        name: 'AITestCaseGenerate',
        component: () => import('../views/ai/AITestCaseGenerate.vue'),
        meta: { title: 'AI测试用例生成' }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
