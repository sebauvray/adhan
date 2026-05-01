/**
 * Auto-return to /dashboard after a period of inactivity on any other page.
 *
 * Designed for the family-tablet scenario: someone opens Settings or Stats,
 * walks away, and the screen would otherwise stay stuck on a non-home page
 * forever. The dashboard is the always-on display, so we route back to it.
 *
 * The composable is route-aware: timer only runs when the active route is
 * NOT in the excluded list. Setup wizard is excluded so a half-finished
 * install isn't yanked away.
 */
import { onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const IDLE_DELAY_MS = 90_000
const HOME_ROUTE = 'dashboard'
const EXCLUDED_ROUTES = new Set([HOME_ROUTE, 'setup'])
const ACTIVITY_EVENTS = ['pointerdown', 'keydown', 'wheel', 'touchstart'] as const

export function useIdleRedirect() {
  const route = useRoute()
  const router = useRouter()
  let timerId: ReturnType<typeof setTimeout> | null = null

  function clearTimer() {
    if (timerId !== null) {
      clearTimeout(timerId)
      timerId = null
    }
  }

  function scheduleRedirect() {
    clearTimer()
    timerId = setTimeout(() => {
      // Re-check route at fire time — user may have navigated to home
      // between the last activity and now.
      if (!EXCLUDED_ROUTES.has(route.name as string)) {
        router.push({ name: HOME_ROUTE })
      }
    }, IDLE_DELAY_MS)
  }

  function onActivity() {
    if (EXCLUDED_ROUTES.has(route.name as string)) return
    scheduleRedirect()
  }

  function attach() {
    for (const evt of ACTIVITY_EVENTS) {
      window.addEventListener(evt, onActivity, { passive: true })
    }
  }
  function detach() {
    for (const evt of ACTIVITY_EVENTS) {
      window.removeEventListener(evt, onActivity)
    }
  }

  watch(
    () => route.name,
    (name) => {
      if (EXCLUDED_ROUTES.has(name as string)) {
        clearTimer()
      } else {
        scheduleRedirect()
      }
    },
  )

  onMounted(() => {
    attach()
    if (!EXCLUDED_ROUTES.has(route.name as string)) {
      scheduleRedirect()
    }
  })

  onUnmounted(() => {
    detach()
    clearTimer()
  })
}
