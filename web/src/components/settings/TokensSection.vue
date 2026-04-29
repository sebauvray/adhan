<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api/client'

interface User { id: number; name: string; emoji: string }
interface Token {
  id: number
  description: string
  scope: string
  user_id: number | null
  user_name?: string
  user_emoji?: string
  created_at?: string
}

const router = useRouter()
const tokens = ref<Token[]>([])
const users = ref<User[]>([])
const newToken = reactive({ user_id: '', description: '' })
const newTokenValue = ref('')

async function loadTokens() {
  try {
    const data = await api<{ tokens: Token[] }>('/tokens')
    tokens.value = (data.tokens || []).filter((t) => t.scope === 'prayers')
  } catch (e) {
    if ((e as Error).message?.includes('Authentification')) {
      router.push('/login?next=/settings')
    }
  }
}

async function loadUsers() {
  const data = await api<{ users: User[] }>('/users')
  users.value = data.users || []
}

async function createToken() {
  if (!newToken.user_id) {
    alert('Sélectionne un utilisateur')
    return
  }
  try {
    const res = await api<{ token: string }>('/tokens', {
      method: 'POST',
      body: JSON.stringify({
        scope: 'prayers',
        user_id: parseInt(newToken.user_id),
        description: newToken.description.trim() || 'API',
      }),
    })
    newTokenValue.value = res.token
    newToken.description = ''
    newToken.user_id = ''
    await loadTokens()
  } catch (e) {
    alert((e as Error).message || 'Erreur')
  }
}

async function deleteToken(id: number) {
  if (!confirm('Révoquer ce token ?')) return
  await api(`/tokens/${id}`, { method: 'DELETE' })
  await loadTokens()
}

onMounted(async () => {
  await Promise.all([loadUsers(), loadTokens()])
})
</script>

<template>
  <div class="form-section">
    <h2>Tokens API externes</h2>
    <p style="font-size: 0.75rem; color: var(--text-dark-muted); margin-bottom: 0.6rem">
      Tokens scope <code>prayers</code> pour valider/lire les prières d'un utilisateur depuis une app externe.
    </p>
    <div>
      <p v-if="!tokens.length" style="font-size: 0.75rem; color: var(--text-dark-muted)">Aucun token externe</p>
      <div v-for="t in tokens" :key="t.id" class="user-item">
        <span class="emoji-pick-btn" style="cursor: default">{{ t.user_emoji || '🔑' }}</span>
        <div style="flex: 1; min-width: 0">
          <div class="user-name">{{ t.description || 'API' }}</div>
          <div style="font-size: 0.7rem; color: var(--text-dark-muted)">
            {{ t.user_name || '?' }} · {{ t.created_at || '' }}
          </div>
        </div>
        <button type="button" class="remove-btn" title="Révoquer" @click="deleteToken(t.id)">&times;</button>
      </div>
    </div>
    <div class="user-add-form" style="margin-top: 0.6rem">
      <select v-model="newToken.user_id" class="user-name-input" style="flex: 1">
        <option value="">-- Utilisateur --</option>
        <option v-for="u in users" :key="u.id" :value="u.id">{{ u.emoji }} {{ u.name }}</option>
      </select>
      <input
        v-model="newToken.description"
        type="text"
        class="user-name-input"
        placeholder="Description (ex: Home Assistant)"
        style="flex: 1.5"
      >
      <button type="button" class="btn btn-action btn-sm" @click="createToken">+</button>
    </div>
    <div v-if="newTokenValue" class="token-display">
      <strong>Token généré (copie-le maintenant, il ne sera plus affiché) :</strong>
      <code>{{ newTokenValue }}</code>
    </div>
  </div>
</template>
