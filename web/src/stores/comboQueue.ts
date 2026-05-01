/**
 * Combo queue — the public bus between "something happened that should
 * trigger a combo animation" and the visual `ComboOverlay` component.
 *
 * Anyone (TrackingPanel, devtools, future surfaces) can `push(batches)`;
 * the overlay mounted once in `App.vue` consumes the queue and plays
 * animations sequentially, user by user.
 *
 * Design notes:
 * - One global queue (Pinia store) so the overlay is naturally a singleton.
 * - Queue holds *user batches*, not individual events — playback order
 *   inside a batch is decided by the backend (group → salat → fire → perfect).
 * - `current` is the batch currently playing (or null if idle); the overlay
 *   sets it to null when done, the store auto-advances if more is queued.
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export type TrackerId = 'salat' | 'group' | 'fire' | 'perfect_day'
export type EventAction = 'increment' | 'broken'

export interface TrackerEvent {
  tracker_id: TrackerId
  action: EventAction
  total: number
  combo: number
}

export interface ComboUser {
  id: number
  name: string
  emoji: string
}

export interface ComboBatch {
  user: ComboUser
  events: TrackerEvent[]
}

export const useComboQueue = defineStore('comboQueue', () => {
  const queue = ref<ComboBatch[]>([])
  const current = ref<ComboBatch | null>(null)

  const isIdle = computed(() => current.value === null && queue.value.length === 0)

  function push(batches: ComboBatch[]) {
    if (!batches?.length) return
    queue.value.push(...batches)
    if (current.value === null) advance()
  }

  function advance() {
    const next = queue.value.shift()
    current.value = next ?? null
  }

  function done() {
    advance()
  }

  function clear() {
    queue.value = []
    current.value = null
  }

  return { queue, current, isIdle, push, done, clear }
})
