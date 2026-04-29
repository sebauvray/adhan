import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api/client'

export const useAuthStore = defineStore('auth', () => {
  const authenticated = ref(false)
  const username = ref<string | null>(null)

  async function check() {
    try {
      const res = await api<{ authenticated: boolean; username: string | null }>('/auth/status')
      authenticated.value = res.authenticated
      username.value = res.username
    } catch {
      authenticated.value = false
      username.value = null
    }
  }

  async function login(u: string, p: string) {
    await api('/login', {
      method: 'POST',
      body: JSON.stringify({ username: u, password: p }),
    })
    await check()
  }

  async function logout() {
    await api('/logout', { method: 'POST' })
    authenticated.value = false
    username.value = null
  }

  return { authenticated, username, check, login, logout }
})
