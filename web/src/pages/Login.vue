<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await auth.login(username.value.trim(), password.value)
    const next = (route.query.next as string) || '/settings'
    router.push(next)
  } catch (e) {
    error.value = (e as Error).message || 'Identifiants invalides'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="page">
    <div class="card">
      <img src="/logo.png" alt="Adhan Home" class="logo">
      <h1>Adhan Home</h1>
      <p class="subtitle">Connexion administrateur</p>

      <form autocomplete="on" @submit.prevent="submit">
        <div class="form-group">
          <label for="username">Identifiant</label>
          <input
            id="username"
            v-model="username"
            type="text"
            autocomplete="username"
            required
          >
        </div>
        <div class="form-group">
          <label for="password">Mot de passe</label>
          <input
            id="password"
            v-model="password"
            type="password"
            autocomplete="current-password"
            required
          >
        </div>
        <div v-if="error" class="msg msg-error" style="margin-top: 0.5rem">{{ error }}</div>
        <div class="actions" style="margin-top: 1.2rem">
          <RouterLink to="/dashboard" class="btn btn-secondary">Retour au tableau</RouterLink>
          <button type="submit" class="btn btn-action" :disabled="loading">
            <template v-if="loading">Connexion<span class="spinner"></span></template>
            <template v-else>Se connecter</template>
          </button>
        </div>
      </form>
    </div>
  </div>
</template>
