import { createRouter, createWebHistory } from 'vue-router'
import Login from '@/pages/Login.vue'
import Dashboard from '@/pages/Dashboard.vue'
import Setup from '@/pages/Setup.vue'
import Settings from '@/pages/Settings.vue'
import Stats from '@/pages/Stats.vue'
import { api } from '@/api/client'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/dashboard' },
    { path: '/login', component: Login, name: 'login' },
    { path: '/dashboard', component: Dashboard, name: 'dashboard' },
    { path: '/setup', component: Setup, name: 'setup' },
    { path: '/settings', component: Settings, name: 'settings', meta: { requiresAuth: true } },
    { path: '/stats', component: Stats, name: 'stats', meta: { requiresAuth: true } },
  ],
})

router.beforeEach(async (to) => {
  // Setup wizard owns the bootstrap flow: send anonymous users there if no admin exists yet.
  try {
    const status = await api<{ configured: boolean }>('/status')
    if (!status.configured && to.name !== 'setup') {
      return { name: 'setup' }
    }
    if (status.configured && to.name === 'setup') {
      return { name: 'dashboard' }
    }
  } catch {
    // API unreachable — let the page render and surface the error itself.
  }

  if (to.meta.requiresAuth) {
    const auth = await api<{ authenticated: boolean }>('/auth/status').catch(() => ({ authenticated: false }))
    if (!auth.authenticated) {
      return { name: 'login', query: { next: to.fullPath } }
    }
  }
})

export default router
