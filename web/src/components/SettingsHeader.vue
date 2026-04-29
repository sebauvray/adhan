<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

defineProps<{ title: string; subtitle: string }>()

const router = useRouter()
const auth = useAuthStore()

async function logout() {
  await auth.logout()
  router.push('/login')
}
</script>

<template>
  <div class="settings-header">
    <div class="header-left">
      <RouterLink to="/dashboard">
        <img
          src="/logo-without-background.png"
          alt="Adhan Home"
          class="logo"
          style="height: 120px; margin: 0"
        >
      </RouterLink>
    </div>
    <div class="header-center">
      <h1 style="font-size: 2.2rem; font-weight: 700">{{ title }}</h1>
      <p style="font-size: 0.9rem; color: var(--text-dark-muted); font-style: italic">{{ subtitle }}</p>
    </div>
    <div class="header-right" style="display: flex; flex-direction: column; align-items: flex-end; gap: 0.4rem">
      <RouterLink to="/dashboard" class="link-action">&larr; Dashboard</RouterLink>
      <a href="#" class="link-action" @click.prevent="logout">Déconnexion</a>
    </div>
  </div>
</template>
