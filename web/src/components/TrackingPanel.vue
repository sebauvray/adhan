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
import { ref, computed, watch, onUnmounted, useTemplateRef, nextTick } from 'vue'
import { api } from '@/api/client'
import { useComboQueue, type ComboBatch } from '@/stores/comboQueue'

const comboQueue = useComboQueue()

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

const BUFFER_MS = 2000

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

// Panel dimensions (px) — measured via ResizeObserver so the SVG ring
// can use real pixel coordinates and the stroke stays a clean 1.5px
// regardless of panel aspect ratio.
const panelEl = useTemplateRef<HTMLElement>('panel')
const panelWidth = ref(0)
const panelHeight = ref(0)
let resizeObs: ResizeObserver | null = null

const ringPerimeter = computed(() => {
  const w = Math.max(0, panelWidth.value - 1)
  const h = Math.max(0, panelHeight.value - 1)
  // Approximate rounded-rect perimeter (close enough for dasharray purposes):
  // 4 straight sides minus the rounded corner cutouts plus the arc lengths.
  const r = 20
  return 2 * (w + h) - 8 * r + 2 * Math.PI * r
})

// Progress 0→1 across the 2s buffer. Drives the SVG ring around the panel:
// stroke draws from 0 (nothing visible at tap) to full perimeter at commit.
// Colour goes red → orange → green so a fully-green ring means "validation
// imminent / success on its way".
const progress = computed(() => {
  if (!isDirty.value) return 0
  return Math.max(0, Math.min(1, 1 - timerRemaining.value / BUFFER_MS))
})

const strokeColor = computed(() => {
  if (progress.value < 0.33) return '#e63946' // red — début, on vient de tap
  if (progress.value < 0.66) return '#ff8800' // orange — milieu
  return '#22b14c'                              // green — bientôt validé
})

function resetSelection() {
  selected.value = new Set(props.initialLoggedIds)
}

function observePanel() {
  if (!panelEl.value) return
  if (resizeObs) resizeObs.disconnect()
  const update = () => {
    if (!panelEl.value) return
    panelWidth.value = panelEl.value.offsetWidth
    panelHeight.value = panelEl.value.offsetHeight
  }
  update()
  resizeObs = new ResizeObserver(update)
  resizeObs.observe(panelEl.value)
}

// Reset only when the panel actually transitions from closed → open or when
// the active prayer changes. We deliberately don't watch `initialLoggedIds`:
// the parent rebuilds it on every render, so watching it would wipe the
// in-progress selection on every reactivity tick.
watch(() => props.open, (open) => {
  if (open) {
    resetSelection()
    stopTimer()
    // Measure the panel after the open transition so the ring fits exactly.
    nextTick(() => observePanel())
  } else {
    stopTimer()
    if (resizeObs) {
      resizeObs.disconnect()
      resizeObs = null
    }
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
    const res = await api<{ in_group: boolean; added: number; removed: number; batches: ComboBatch[] }>(
      '/prayer-log/batch',
      {
        method: 'POST',
        body: JSON.stringify({ prayer: props.prayer, date: props.viewDate, add, remove }),
      },
    )
    emit('committed', { prayer: props.prayer, date: props.viewDate, add, remove, in_group: res.in_group })
    if (res.batches?.length) comboQueue.push(res.batches)
  } catch (e) {
    console.error('Erreur commit batch:', e)
  } finally {
    emit('close')
  }
}

function onBackdropClick(e: MouseEvent) {
  // Click outside the panel = "I'm done" → commit if there's anything
  // pending, otherwise just close silently. We check the target manually
  // instead of `.self` because some browsers / backdrop-filter combos can
  // make the modifier flake out.
  if (e.target !== e.currentTarget) return
  if (isDirty.value) {
    stopTimer()
    commit()
  } else {
    emit('close')
  }
}

onUnmounted(() => {
  stopTimer()
  if (resizeObs) resizeObs.disconnect()
})
</script>

<template>
  <div
    v-show="open"
    :class="['tracking-overlay', { open }]"
    style="display: flex"
    @click="onBackdropClick"
  >
    <div ref="panel" class="tracking-panel">
      <svg
        v-show="isDirty && panelWidth > 0"
        class="tracking-progress-ring"
        :width="panelWidth"
        :height="panelHeight"
        :viewBox="`0 0 ${panelWidth} ${panelHeight}`"
      >
        <rect
          x="0.75" y="0.75"
          :width="panelWidth - 1.5"
          :height="panelHeight - 1.5"
          rx="20" ry="20"
          fill="none"
          :stroke-dasharray="ringPerimeter"
          :stroke-dashoffset="ringPerimeter * (1 - progress)"
          :stroke="strokeColor"
          stroke-width="1.5"
          stroke-linecap="round"
        />
      </svg>
      <div v-if="!warningMode" class="tracking-header">
        <span class="tracking-prayer-name">{{ prayer || '' }}</span>
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
/* Progress ring around the panel — draws from 0 (just tapped) to full
 * perimeter (about to commit). Colour goes red → orange → green so "fully
 * green" reads as "success, validation incoming". */
.tracking-progress-ring {
  position: absolute;
  top: 0;
  left: 0;
  pointer-events: none;
  overflow: visible;
}
.tracking-progress-ring rect {
  transition: stroke 250ms ease-out;
}
</style>
