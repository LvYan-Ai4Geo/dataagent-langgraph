import { createRouter, createWebHistory } from 'vue-router'

// 路由：初次进入登录页（粒子浮动），点击进入后跳转主界面（自然语言2SQL）
const routes = [
  { path: '/', name: 'login', component: () => import('../views/LoginView.vue') },
  { path: '/chat', name: 'chat', component: () => import('../views/ChatView.vue') }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
