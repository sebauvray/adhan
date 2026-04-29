<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { api } from '@/api/client'
import { saveConfigField } from '@/api/config'
import EmojiPicker from '@/components/EmojiPicker.vue'

interface User { id: number; name: string; emoji: string }

const users = ref<User[]>([])
const newUser = reactive({ name: '', emoji: '🙂' })

const multiDay = ref(false)

async function loadUsers() {
  const data = await api<{ users: User[] }>('/users')
  users.value = data.users || []
}

async function loadConfig() {
  const data = await api<{ multi_day_display: string }>('/config')
  multiDay.value = data.multi_day_display === 'true'
}

async function toggleMultiDay() {
  await saveConfigField('config', 'MULTI_DAY_DISPLAY', multiDay.value ? 'true' : 'false')
}

async function addUser() {
  if (!newUser.name.trim()) return
  await api('/users', {
    method: 'POST',
    body: JSON.stringify({ name: newUser.name.trim(), emoji: newUser.emoji }),
  })
  newUser.name = ''
  newUser.emoji = '🙂'
  await loadUsers()
}

async function deleteUser(id: number) {
  if (!confirm('Supprimer cet utilisateur et son historique ?')) return
  await api(`/users/${id}`, { method: 'DELETE' })
  await loadUsers()
}

async function updateEmoji(user: User, emoji: string) {
  user.emoji = emoji
  await api(`/users/${user.id}`, {
    method: 'PUT',
    body: JSON.stringify({ name: user.name, emoji }),
  })
}

onMounted(async () => {
  await Promise.all([loadUsers(), loadConfig()])
})
</script>

<template>
  <div>
    <div class="form-section">
      <h2>Suivi des prières</h2>
      <div class="form-group">
        <label class="checkbox-label">
          <input v-model="multiDay" type="checkbox" @change="toggleMultiDay">
          Afficher plusieurs jours (veille, jour, lendemain)
        </label>
      </div>
    </div>

    <div class="form-section">
      <h2>Utilisateurs</h2>
      <div>
        <p v-if="!users.length" style="font-size: 0.8rem; color: var(--text-dark-muted)">Aucun utilisateur</p>
        <div v-for="u in users" :key="u.id" class="user-item">
          <EmojiPicker :model-value="u.emoji" @update:model-value="(v: string) => updateEmoji(u, v)" />
          <span class="user-name">{{ u.name }}</span>
          <button type="button" class="remove-btn" title="Supprimer" @click="deleteUser(u.id)">&times;</button>
        </div>
      </div>
      <div class="user-add-form">
        <EmojiPicker v-model="newUser.emoji" />
        <input
          v-model="newUser.name"
          type="text"
          placeholder="Nom"
          class="user-name-input"
          @keydown.enter="addUser"
        >
        <button type="button" class="btn btn-action btn-sm" @click="addUser">+</button>
      </div>
    </div>
  </div>
</template>
