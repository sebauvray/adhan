<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/api/client'

interface User { id: number; name: string; emoji: string }
interface LeaderboardEntry extends User { count: number; streak: number }

const emit = defineEmits<{ users: [users: User[]] }>()

type Period = 'month' | 'year' | 'all'

const period = ref<Period>('month')
const entries = ref<LeaderboardEntry[]>([])
const error = ref(false)

async function load() {
  error.value = false
  try {
    const data = await api<{ leaderboard: LeaderboardEntry[]; users: User[] }>(`/stats?period=${period.value}`)
    entries.value = data.leaderboard || []
    emit('users', data.users || [])
  } catch {
    error.value = true
  }
}

function setPeriod(p: Period) {
  period.value = p
  load()
}

function rankLabel(i: number): string {
  if (i === 0) return '🥇'
  if (i === 1) return '🥈'
  if (i === 2) return '🥉'
  return String(i + 1)
}

function widthFor(count: number): string {
  const max = entries.value[0]?.count || 1
  return `${(count / max) * 100}%`
}

onMounted(load)
</script>

<template>
  <div class="form-section">
    <h2>Classement</h2>
    <div class="stats-period">
      <button
        :class="['btn', 'btn-sm', 'period-btn', { active: period === 'month' }]"
        @click="setPeriod('month')"
      >Mois</button>
      <button
        :class="['btn', 'btn-sm', 'period-btn', { active: period === 'year' }]"
        @click="setPeriod('year')"
      >Année</button>
      <button
        :class="['btn', 'btn-sm', 'period-btn', { active: period === 'all' }]"
        @click="setPeriod('all')"
      >Tout</button>
    </div>
    <div>
      <p
        v-if="error"
        style="font-size: 0.85rem; color: #c53030"
      >Erreur</p>
      <p
        v-else-if="!entries.length"
        style="font-size: 0.85rem; color: var(--text-dark-muted); margin-top: 1rem"
      >Aucune donnée</p>
      <div v-for="(u, i) in entries" :key="u.id" class="leaderboard-row">
        <span class="lb-rank">{{ rankLabel(i) }}</span>
        <span class="lb-emoji">{{ u.emoji }}</span>
        <div class="lb-info">
          <div class="lb-name">{{ u.name }}</div>
          <div class="lb-bar-track">
            <div class="lb-bar" :style="{ width: widthFor(u.count) }"></div>
          </div>
        </div>
        <div class="lb-stats">
          <span class="lb-count">{{ u.count }}</span>
          <span class="lb-streak" title="Série en cours">
            <template v-if="u.streak > 0">🔥 {{ u.streak }}j</template>
          </span>
        </div>
      </div>
    </div>
  </div>
</template>
