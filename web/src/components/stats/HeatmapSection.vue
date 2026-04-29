<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { api } from '@/api/client'

interface User { id: number; name: string; emoji: string }
interface HeatmapData { heatmap: Record<string, number>; streak: number }
interface DayCell { date: string; count: number; day: number }
interface Week { days: DayCell[] }

const props = defineProps<{ users: User[] }>()

const userId = ref<string>('')
const heatmapData = ref<HeatmapData | null>(null)
const error = ref(false)

const MONTHS = ['Jan', 'Fev', 'Mar', 'Avr', 'Mai', 'Jun', 'Jul', 'Aou', 'Sep', 'Oct', 'Nov', 'Dec']
const DAY_LABELS = ['', 'L', '', 'M', '', 'V', '']

const weeks = computed<Week[]>(() => {
  if (!heatmapData.value) return []
  const heatmap = heatmapData.value.heatmap

  const today = new Date()
  const start = new Date(today)
  start.setDate(start.getDate() - 363)
  while (start.getDay() !== 1) start.setDate(start.getDate() - 1)

  const days: DayCell[] = []
  const d = new Date(start)
  while (d <= today) {
    const key = d.toISOString().slice(0, 10)
    days.push({ date: key, count: heatmap[key] || 0, day: d.getDay() })
    d.setDate(d.getDate() + 1)
  }

  const ws: Week[] = []
  let week: DayCell[] = []
  for (const day of days) {
    week.push(day)
    if (day.day === 0) {
      ws.push({ days: week })
      week = []
    }
  }
  if (week.length) ws.push({ days: week })
  return ws
})

const monthLabels = computed(() => {
  const labels: { col: number; label: string }[] = []
  let lastMonth = -1
  weeks.value.forEach((w, i) => {
    const m = new Date(w.days[0].date).getMonth()
    if (m !== lastMonth) {
      labels.push({ col: i + 2, label: MONTHS[m] })
      lastMonth = m
    }
  })
  return labels
})

function cellLevel(count: number): number {
  if (count === 0) return 0
  if (count <= 1) return 1
  if (count <= 2) return 2
  if (count <= 3) return 3
  return 4
}

function cellAt(week: Week, targetDay: number): DayCell | undefined {
  return week.days.find((d) => d.day === targetDay)
}

async function load() {
  if (!userId.value) {
    heatmapData.value = null
    return
  }
  error.value = false
  try {
    heatmapData.value = await api<HeatmapData>(`/stats?period=year&user_id=${userId.value}`)
  } catch {
    error.value = true
  }
}

watch(userId, load)
// Reset selection if the user vanishes from the list (e.g. deleted in Settings)
watch(
  () => props.users,
  (list) => {
    if (userId.value && !list.some((u) => String(u.id) === userId.value)) {
      userId.value = ''
      heatmapData.value = null
    }
  },
)
</script>

<template>
  <div class="form-section">
    <h2>Activité</h2>
    <div class="stats-user-select">
      <select v-model="userId">
        <option value="">Choisir un utilisateur...</option>
        <option v-for="u in users" :key="u.id" :value="u.id">{{ u.emoji }} {{ u.name }}</option>
      </select>
    </div>

    <div>
      <p
        v-if="!userId"
        style="font-size: 0.85rem; color: var(--text-dark-muted); margin-top: 1rem"
      >Sélectionne un utilisateur</p>
      <p
        v-else-if="error"
        style="font-size: 0.85rem; color: #c53030"
      >Erreur</p>
      <template v-else-if="heatmapData">
        <div class="heatmap-streak">
          Série en cours :
          <strong>🔥 {{ heatmapData.streak }} jour{{ heatmapData.streak > 1 ? 's' : '' }}</strong>
        </div>
        <div
          class="heatmap-grid"
          :style="{ gridTemplateColumns: `20px repeat(${weeks.length}, 12px)` }"
        >
          <div
            class="heatmap-months"
            :style="{ gridColumn: '2 / -1', display: 'grid', gridTemplateColumns: 'subgrid' }"
          >
            <span v-for="m in monthLabels" :key="m.col" :style="{ gridColumn: m.col }">{{ m.label }}</span>
          </div>
          <template v-for="(label, row) in DAY_LABELS" :key="row">
            <span class="heatmap-day-label">{{ label }}</span>
            <span
              v-for="(w, wi) in weeks"
              :key="`${row}-${wi}`"
              :class="
                cellAt(w, row < 6 ? row + 1 : 0)
                  ? `heatmap-cell level-${cellLevel(cellAt(w, row < 6 ? row + 1 : 0)!.count)}`
                  : 'heatmap-cell empty'
              "
            >
              <span v-if="cellAt(w, row < 6 ? row + 1 : 0)" class="heatmap-tooltip">
                {{ cellAt(w, row < 6 ? row + 1 : 0)!.count }}/5 prières — {{ cellAt(w, row < 6 ? row + 1 : 0)!.date }}
              </span>
            </span>
          </template>
        </div>
      </template>
    </div>

    <div class="heatmap-legend">
      <span class="legend-label">Moins</span>
      <span class="legend-cell" style="background: var(--heatmap-0)"></span>
      <span class="legend-cell" style="background: var(--heatmap-1)"></span>
      <span class="legend-cell" style="background: var(--heatmap-2)"></span>
      <span class="legend-cell" style="background: var(--heatmap-3)"></span>
      <span class="legend-cell" style="background: var(--heatmap-4)"></span>
      <span class="legend-label">Plus</span>
    </div>
  </div>
</template>
