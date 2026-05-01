<script setup lang="ts">
/**
 * Tracking panel for the "Tu as prié avec qui ?" question.
 *
 * Behaviour (validated 2026-05-01):
 * - Tap a user → toggles them in a local `selected` set (no immediate API call)
 * - Each tap (re)starts a 3s countdown shown top-right (green → orange → red)
 * - Reverting to the initial state stops the countdown — nothing to commit
 * - Countdown reaches 0 → POST /api/prayer-log/batch with the diff (add/remove)
 *   then closes the panel
 * - Manual close (× or backdrop) cancels the buffered changes silently
 *
 * The combo / animation system (phase 3) will hook on the `committed` event:
 * it receives the response and pushes events to the global ComboOverlay queue.
 */
import { ref, computed, watch, onUnmounted } from 'vue'
import { api } from '@/api/client'

interface User { id: number; name: string; emoji: string }

const props = defineProps<{
  open: boolean
  prayer: string | null
  users: User[]
  initialLoggedIds: number[]
  viewDate: string
  warningMode: boolean
  lateReminder: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'committed', payload: { prayer: string; date: string; add: number[]; remove: number[]; in_group: boolean }): void
}>()

const BUFFER_MS = 3000

const selected = ref<Set<number>>(new Set())
const timerRemaining = ref(0)
let rafHandle: number | null = null
let bufferStartedAt = 0

const isDirty = computed(() => {
  const initial = new Set(props.initialLoggedIds)
  if (selected.value.size !== initial.size) return true
  for (const id of selected.value) if (!initial.has(id)) return true
  return false
})

const timerColor = computed<'green' | 'orange' | 'red' | 'idle'>(() => {
  if (!isDirty.value) return 'idle'
  if (timerRemaining.value > 2000) return 'green'
  if (timerRemaining.value > 1000) return 'orange'
  return 'red'
})

const timerLabel = computed(() => {
  if (!isDirty.value) return ''
  return `${(timerRemaining.value / 1000).toFixed(1)}s`
})

function resetSelection() {
  selected.value = new Set(props.initialLoggedIds)
}

// Reset only when the panel actually transitions from closed → open or when
// the active prayer changes. We deliberately don't watch `initialLoggedIds`:
// the parent rebuilds it on every render, so watching it would wipe the
// in-progress selection on every reactivity tick.
watch(() => props.open, (open) => {
  if (open) {
    resetSelection()
    stopTimer()
  } else {
    stopTimer()
  }
})

watch(() => props.prayer, () => {
  if (props.open) {
    resetSelection()
    stopTimer()
  }
})

function toggle(userId: number) {
  if (selected.value.has(userId)) selected.value.delete(userId)
  else selected.value.add(userId)
  selected.value = new Set(selected.value)

  if (isDirty.value) startOrResetTimer()
  else stopTimer()
}

function startOrResetTimer() {
  bufferStartedAt = performance.now()
  timerRemaining.value = BUFFER_MS
  if (rafHandle !== null) cancelAnimationFrame(rafHandle)
  const tick = (now: number) => {
    const elapsed = now - bufferStartedAt
    const remaining = BUFFER_MS - elapsed
    if (remaining <= 0) {
      timerRemaining.value = 0
      rafHandle = null
      commit()
      return
    }
    timerRemaining.value = remaining
    rafHandle = requestAnimationFrame(tick)
  }
  rafHandle = requestAnimationFrame(tick)
}

function stopTimer() {
  if (rafHandle !== null) cancelAnimationFrame(rafHandle)
  rafHandle = null
  timerRemaining.value = 0
}

async function commit() {
  if (!props.prayer) {
    emit('close')
    return
  }
  const initial = new Set(props.initialLoggedIds)
  const add = [...selected.value].filter((id) => !initial.has(id))
  const remove = [...initial].filter((id) => !selected.value.has(id))
  if (!add.length && !remove.length) {
    emit('close')
    return
  }
  try {
    const res = await api<{ in_group: boolean; added: number; removed: number }>(
      '/prayer-log/batch',
      {
        method: 'POST',
        body: JSON.stringify({ prayer: props.prayer, date: props.viewDate, add, remove }),
      },
    )
    emit('committed', { prayer: props.prayer, date: props.viewDate, add, remove, in_group: res.in_group })
  } catch (e) {
    console.error('Erreur commit batch:', e)
  } finally {
    emit('close')
  }
}

function onBackdropClick() {
  emit('close')
}

onUnmounted(() => stopTimer())
</script>

<template>
  <div
    v-show="open"
    :class="['tracking-overlay', { open }]"
    style="display: flex"
    @click.self="onBackdropClick"
  >
    <div class="tracking-panel">
      <div v-if="!warningMode" class="tracking-header">
        <span class="tracking-prayer-name">{{ prayer || '' }}</span>
        <span
          v-if="isDirty"
          :class="['tracking-timer', `is-${timerColor}`]"
        >{{ timerLabel }}</span>
        <button class="tracking-close" @click="emit('close')">&times;</button>
      </div>

      <template v-if="warningMode">
        <div class="tracking-warning">
          <span style="font-size: 2.5rem">☝️</span>
          <p>Dieu te voit tu sais...</p>
        </div>
      </template>
      <template v-else>
        <div class="tracking-subtitle">{{ $t('tracking.question') }}</div>
        <div class="tracking-users">
          <p
            v-if="!users.length"
            style="font-size: 0.85rem; color: rgba(26, 26, 26, 0.5); margin: 1rem 0"
          >
            Ajoute des utilisateurs dans les
            <RouterLink to="/settings" style="color: #c8a97e">Paramètres</RouterLink>
          </p>
          <template v-else>
            <button
              v-for="(u, i) in users"
              :key="u.id"
              :class="['tracking-avatar', { done: selected.has(u.id) }]"
              :style="{ animationDelay: `${i * 0.07}s` }"
              @click="toggle(u.id)"
            >
              <span class="tracking-avatar-emoji">{{ u.emoji }}</span>
              <span class="tracking-avatar-name">{{ u.name }}</span>
              <span v-if="selected.has(u.id)" class="tracking-avatar-check">&#10003;</span>
            </button>
            <p v-if="lateReminder" class="tracking-reminder">
              Chaque prière a son heure, ne tarde pas la prochaine fois inch'Allah !
            </p>
          </template>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.tracking-timer {
  position: absolute;
  top: 0.7rem;
  right: 2.6rem;
  font-family: 'Russo One', sans-serif;
  font-size: 0.9rem;
  font-weight: 700;
  letter-spacing: 0.5px;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1.5px solid currentColor;
  background: rgba(255, 255, 255, 0.9);
  transition: color 200ms, border-color 200ms;
  pointer-events: none;
}
.tracking-timer.is-green  { color: #22b14c; }
.tracking-timer.is-orange { color: #ff8800; }
.tracking-timer.is-red    {
  color: #e63946;
  animation: timerPulse 600ms ease-in-out infinite alternate;
}
@keyframes timerPulse {
  from { transform: scale(1); }
  to   { transform: scale(1.08); }
}
</style>
