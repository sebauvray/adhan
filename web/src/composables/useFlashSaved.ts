import { ref } from 'vue'

/** Tracks which fields recently saved (for the "Sauvegardé" indicator).
 *  `flash(key)` adds the key for `durationMs`, then auto-removes it. */
export function useFlashSaved(durationMs = 2000) {
  const saved = ref<Set<string>>(new Set())

  function flash(key: string) {
    saved.value.add(key)
    saved.value = new Set(saved.value)
    setTimeout(() => {
      saved.value.delete(key)
      saved.value = new Set(saved.value)
    }, durationMs)
  }

  return { saved, flash }
}
