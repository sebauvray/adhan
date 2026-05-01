<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, useTemplateRef } from 'vue'
import { api } from '@/api/client'
import PrayerItem from '@/components/PrayerItem.vue'
import TrackingPanel from '@/components/TrackingPanel.vue'

interface Prayer {
  name: string
  arabic: string
  adhan: string
  iqama: string
  status: 'past' | 'current' | 'upcoming'
}
interface NextPrayer extends Prayer {
  seconds_until: number
}
interface PrayersResponse {
  prayers: Prayer[]
  next: NextPrayer | null
  current_salat: string | null
  view_date: string
  today: string
  yesterday: string
  tomorrow: string
  can_view_previous: boolean
  can_view_next: boolean
}
interface User { id: number; name: string; emoji: string }

const WEATHER_ICONS: Record<string, string> = {
  '0_day': 'clear-day', '1_day': 'clear-day',
  '2_day': 'partly-cloudy-day', '3_day': 'overcast',
  '45_day': 'fog-day', '48_day': 'fog-day',
  '51_day': 'partly-cloudy-day-drizzle', '53_day': 'overcast-day-drizzle', '55_day': 'overcast-drizzle',
  '56_day': 'overcast-day-sleet', '57_day': 'overcast-sleet',
  '61_day': 'partly-cloudy-day-rain', '63_day': 'overcast-day-rain', '65_day': 'overcast-rain',
  '66_day': 'overcast-day-sleet', '67_day': 'overcast-sleet',
  '71_day': 'partly-cloudy-day-snow', '73_day': 'overcast-day-snow', '75_day': 'overcast-snow', '77_day': 'snowflake',
  '80_day': 'partly-cloudy-day-rain', '81_day': 'overcast-day-rain', '82_day': 'overcast-rain',
  '95_day': 'thunderstorms-day-rain', '96_day': 'thunderstorms-day-overcast-rain', '99_day': 'thunderstorms-overcast-rain',
  '0_night': 'clear-night', '1_night': 'clear-night',
  '2_night': 'partly-cloudy-night', '3_night': 'overcast',
  '45_night': 'fog-night', '48_night': 'fog-night',
  '51_night': 'partly-cloudy-night-drizzle', '53_night': 'overcast-night-drizzle', '55_night': 'overcast-drizzle',
  '56_night': 'overcast-night-sleet', '57_night': 'overcast-sleet',
  '61_night': 'partly-cloudy-night-rain', '63_night': 'overcast-night-rain', '65_night': 'overcast-rain',
  '66_night': 'overcast-night-sleet', '67_night': 'overcast-sleet',
  '71_night': 'partly-cloudy-night-snow', '73_night': 'overcast-night-snow', '75_night': 'overcast-snow', '77_night': 'snowflake',
  '80_night': 'partly-cloudy-night-rain', '81_night': 'overcast-night-rain', '82_night': 'overcast-rain',
  '95_night': 'thunderstorms-night-rain', '96_night': 'thunderstorms-night-overcast-rain', '99_night': 'thunderstorms-overcast-rain',
}
function weatherIconUrl(code: number, isDay: number) {
  const tag = isDay ? 'day' : 'night'
  const icon = WEATHER_ICONS[`${code}_${tag}`] || 'not-available'
  return `/weather/${icon}.svg`
}

// --- Clock ---
const clockTime = ref('')
const clockDate = ref('')
function updateClock() {
  const now = new Date()
  clockTime.value = now.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  clockDate.value = now.toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
}

// --- Prayers ---
const prayers = ref<Prayer[]>([])
const nextPrayer = ref<NextPrayer | null>(null)
const currentSalat = ref<string | null>(null)
const viewDate = ref('')
const today = ref('')
const yesterday = ref('')
const tomorrow = ref('')
const canViewPrev = ref(false)
const canViewNext = ref(false)

const dayLabel = computed(() => {
  if (!viewDate.value || viewDate.value === today.value) return ''
  const d = new Date(viewDate.value + 'T00:00:00')
  return d.toLocaleDateString('fr-FR', { weekday: 'short', day: 'numeric', month: 'short' })
})

async function fetchPrayers(targetDate?: string) {
  try {
    const url = targetDate ? `/prayers?date=${targetDate}` : '/prayers'
    let data: PrayersResponse
    try {
      data = await api<PrayersResponse>(url)
    } catch (e) {
      // Day rolled over while we were viewing yesterday/tomorrow — reset to today
      if ((e as Error).message?.includes('hors plage') || (e as Error).message?.includes('non disponible')) {
        viewDate.value = ''
        data = await api<PrayersResponse>('/prayers')
      } else {
        throw e
      }
    }
    prayers.value = data.prayers
    nextPrayer.value = data.next
    currentSalat.value = data.current_salat
    viewDate.value = data.view_date
    today.value = data.today
    yesterday.value = data.yesterday
    tomorrow.value = data.tomorrow
    canViewPrev.value = data.can_view_previous
    canViewNext.value = data.can_view_next
    if (data.next) secondsUntilNext.value = data.next.seconds_until
    await fetchTracking()
  } catch (e) {
    console.error('Erreur fetch prayers:', e)
  }
}

function navigateDay(delta: number) {
  let target: string | null = null
  if (delta < 0 && canViewPrev.value) {
    if (viewDate.value === today.value) target = yesterday.value
    else if (viewDate.value === tomorrow.value) target = today.value
  } else if (delta > 0 && canViewNext.value) {
    if (viewDate.value === yesterday.value) target = today.value
    else if (viewDate.value === today.value) target = tomorrow.value
  }
  if (target) fetchPrayers(target)
}

// --- Countdown ---
const secondsUntilNext = ref(0)
const countdownText = computed(() => {
  const s = secondsUntilNext.value
  if (s <= 0) return ''
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  let txt = ''
  if (h > 0) txt += `${h}h `
  if (m > 0 || h > 0) txt += `${m}min `
  txt += `${sec}s`
  return txt
})
function tickCountdown() {
  if (secondsUntilNext.value <= 0) {
    if (viewDate.value === today.value) fetchPrayers()
    return
  }
  secondsUntilNext.value -= 1
}

// --- Weather ---
const weather = ref<{ city: string; temperature: number; weather_code: number; is_day: number } | null>(null)
async function fetchWeather() {
  try {
    weather.value = await api('/weather')
  } catch (e) {
    console.error('Erreur fetch weather:', e)
  }
}

// --- Sunrise (Chourouk) ---
const sunriseTime = ref('')
async function fetchSunrise() {
  try {
    const data = await api<{ time: string }>('/sunrise')
    sunriseTime.value = data.time || ''
  } catch (e) {
    console.error('Erreur fetch sunrise:', e)
  }
}

// --- Jumua ---
const jumuaTimes = ref<string[]>([])
const isFriday = computed(() => new Date().getDay() === 5)
async function fetchJumua() {
  if (!isFriday.value) return
  try {
    const data = await api<{ times: string[] }>('/jumua')
    jumuaTimes.value = data.times || []
  } catch (e) {
    console.error('Erreur fetch jumua:', e)
  }
}

// --- Tracking ---
const trackingUsers = ref<User[]>([])
const logsByDate = reactive<Record<string, Record<string, number[]>>>({})
const trackingOpen = ref(false)
const trackingWarning = ref(false)
const activePrayer = ref<string | null>(null)

function loggedIdsFor(prayer: string): number[] {
  return (logsByDate[viewDate.value] || {})[prayer] || []
}

function badgeFor(prayer: string): string {
  const ids = loggedIdsFor(prayer)
  if (ids.length === 0) return ''
  return trackingUsers.value
    .filter((u) => ids.includes(u.id))
    .map((u) => u.emoji)
    .join('')
}

async function fetchTracking() {
  if (!viewDate.value) return
  try {
    const data = await api<{ users: User[]; logs: Record<string, number[]> }>(`/prayer-logs/${viewDate.value}`)
    trackingUsers.value = data.users || trackingUsers.value
    logsByDate[viewDate.value] = data.logs || {}
  } catch (e) {
    console.error('Erreur fetch tracking:', e)
  }
}

function isPrayerLate(prayer: string): boolean {
  if (prayer === currentSalat.value) return false
  if (prayer === 'Fajr' && sunriseTime.value) {
    const now = new Date()
    const [h, m] = sunriseTime.value.split(':').map(Number)
    if (now.getHours() > h || (now.getHours() === h && now.getMinutes() >= m)) return true
  }
  const p = prayers.value.find((x) => x.name === prayer)
  return p?.status === 'past'
}

function openTracking(prayer: string) {
  const p = prayers.value.find((x) => x.name === prayer)
  if (p?.status === 'upcoming' && prayer !== currentSalat.value) {
    trackingWarning.value = true
    trackingOpen.value = true
    setTimeout(() => closeTracking(), 4000)
    return
  }
  activePrayer.value = prayer
  trackingWarning.value = false
  trackingOpen.value = true
}

function closeTracking() {
  trackingOpen.value = false
  setTimeout(() => {
    activePrayer.value = null
    trackingWarning.value = false
  }, 250)
}

const confettiCanvas = useTemplateRef<HTMLCanvasElement>('confetti-canvas')

function onBatchCommitted(payload: { prayer: string; date: string; add: number[]; remove: number[] }) {
  const { prayer, date, add, remove } = payload
  if (!logsByDate[date]) logsByDate[date] = {}
  const current = new Set(logsByDate[date][prayer] || [])
  add.forEach((id) => current.add(id))
  remove.forEach((id) => current.delete(id))
  logsByDate[date][prayer] = [...current]
  if (add.length > 0) launchConfetti()
}

// --- Confetti ---
function launchConfetti() {
  const canvas = confettiCanvas.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  canvas.width = window.innerWidth
  canvas.height = window.innerHeight

  const colors = ['#c8a97e', '#e8d5b7', '#f5f0e8', '#a68a5b', '#FFD700', '#FF6B6B', '#4ECDC4']
  const particles = Array.from({ length: 120 }, () => ({
    x: canvas.width / 2 + (Math.random() - 0.5) * 200,
    y: canvas.height / 2,
    vx: (Math.random() - 0.5) * 15,
    vy: (Math.random() - 1) * 18 - 5,
    w: Math.random() * 8 + 4,
    h: Math.random() * 6 + 3,
    color: colors[Math.floor(Math.random() * colors.length)],
    rotation: Math.random() * 360,
    rotSpeed: (Math.random() - 0.5) * 12,
    life: 1,
  }))

  let frame = 0
  const animate = () => {
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    let alive = false
    particles.forEach((p) => {
      if (p.life <= 0) return
      alive = true
      p.x += p.vx
      p.y += p.vy
      p.vy += 0.4
      p.rotation += p.rotSpeed
      p.life -= 0.012
      p.vx *= 0.99
      ctx.save()
      ctx.translate(p.x, p.y)
      ctx.rotate((p.rotation * Math.PI) / 180)
      ctx.globalAlpha = Math.max(0, p.life)
      ctx.fillStyle = p.color
      ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h)
      ctx.restore()
    })
    frame++
    if (alive && frame < 180) requestAnimationFrame(animate)
    else ctx.clearRect(0, 0, canvas.width, canvas.height)
  }
  animate()
}

// --- Lifecycle ---
let clockTimer: ReturnType<typeof setInterval> | null = null
let countdownTimer: ReturnType<typeof setInterval> | null = null
let prayersTimer: ReturnType<typeof setInterval> | null = null
let weatherTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  document.body.classList.add('dashboard-page')
  updateClock()
  clockTimer = setInterval(updateClock, 1000)
  countdownTimer = setInterval(tickCountdown, 1000)
  fetchPrayers()
  prayersTimer = setInterval(() => fetchPrayers(), 60000)
  fetchWeather()
  weatherTimer = setInterval(fetchWeather, 1800000)
  fetchSunrise()
  fetchJumua()
})

onUnmounted(() => {
  document.body.classList.remove('dashboard-page')
  if (clockTimer) clearInterval(clockTimer)
  if (countdownTimer) clearInterval(countdownTimer)
  if (prayersTimer) clearInterval(prayersTimer)
  if (weatherTimer) clearInterval(weatherTimer)
})
</script>

<template>
  <div class="dashboard">
    <div class="dash-header">
      <div class="weather">
        <div class="weather-location">
          <svg class="weather-pin" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/>
            <circle cx="12" cy="10" r="3"/>
          </svg>
          <span>{{ weather?.city || '' }}</span>
        </div>
        <div v-if="weather" class="weather-condition">
          <img class="weather-icon" :src="weatherIconUrl(weather.weather_code, weather.is_day)" alt="">
          <span class="weather-temp">{{ weather.temperature }}°</span>
        </div>
      </div>
      <div class="clock">
        <div class="clock__date">{{ clockDate }}</div>
        <div class="clock__time">{{ clockTime }}</div>
      </div>
      <div style="display: flex; gap: 0.3rem">
        <RouterLink to="/stats" class="icon-btn" title="Statistiques">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <rect x="3" y="12" width="4" height="9" rx="1"/>
            <rect x="10" y="7" width="4" height="14" rx="1"/>
            <rect x="17" y="3" width="4" height="18" rx="1"/>
          </svg>
        </RouterLink>
        <RouterLink to="/settings" class="icon-btn settings-btn" title="Paramètres">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/>
            <circle cx="12" cy="12" r="3"/>
          </svg>
        </RouterLink>
      </div>
    </div>

    <div class="dash-content">
      <div class="dash-prayers">
        <span v-show="dayLabel" class="day-nav-label">{{ dayLabel }}</span>
        <div class="prayers-stage">
          <a
            v-show="canViewPrev"
            href="#"
            class="icon-btn day-nav-arrow day-nav-arrow-prev"
            aria-label="Jour précédent"
            @click.prevent="navigateDay(-1)"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M15.75 19.5 8.25 12l7.5-7.5"/>
            </svg>
          </a>
          <div class="prayers-list">
            <PrayerItem
              v-for="p in prayers"
              :key="p.name"
              :name="p.name"
              :adhan="p.adhan"
              :iqama="p.iqama"
              :status="p.status"
              :badge="badgeFor(p.name)"
              @click="openTracking(p.name)"
            />
          </div>
          <a
            v-show="canViewNext"
            href="#"
            class="icon-btn day-nav-arrow day-nav-arrow-next"
            aria-label="Jour suivant"
            @click.prevent="navigateDay(1)"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="m8.25 4.5 7.5 7.5-7.5 7.5"/>
            </svg>
          </a>
        </div>
      </div>

      <div class="dash-next">
        <div v-if="nextPrayer" class="next-prayer">
          <div class="next-header">
            <div class="next-label">Prochaine Prière</div>
            <div class="countdown">{{ countdownText }}</div>
          </div>
          <div class="next-arabic">{{ nextPrayer.arabic }}</div>
          <div class="next-time">{{ nextPrayer.adhan }}</div>
          <div id="next-iqama">
            <svg class="iqm-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
              <circle cx="9" cy="7" r="4"/>
              <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
              <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
            </svg>
            {{ nextPrayer.iqama || nextPrayer.adhan }}
          </div>
        </div>
      </div>
    </div>

    <div v-if="sunriseTime || (isFriday && jumuaTimes.length)" class="dash-footer">
      <div class="footer-items">
        <div v-if="sunriseTime" class="footer-info">
          <svg class="footer-icon" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 2v4"/><path d="m4.93 4.93 2.83 2.83"/><path d="M2 12h4"/>
            <path d="m19.07 4.93-2.83 2.83"/><path d="M22 12h-4"/>
            <path d="m4 22 4-4"/><path d="m20 22-4-4"/><path d="M2 16h20"/>
            <path d="M12 16a4 4 0 0 0 0-8"/><path d="M12 8a4 4 0 0 1 0 8"/>
          </svg>
          <div class="footer-details">
            <span class="footer-label">Chourouk</span>
            <span class="footer-value">{{ sunriseTime }}</span>
          </div>
        </div>
        <div v-if="isFriday && jumuaTimes.length" class="footer-info">
          <svg class="footer-icon" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 2C10.34 2 9 3.34 9 5s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/>
            <path d="M12 10c-1.1 0-2 .45-2 1v3l-2 6h2l1-3h2l1 3h2l-2-6v-3c0-.55-.9-1-2-1z"/>
          </svg>
          <div class="footer-details">
            <span class="footer-label">Jumu'a</span>
            <span class="footer-value">
              <template v-for="(t, i) in jumuaTimes" :key="i">
                <span v-if="i > 0" class="jumua-sep"> / </span>{{ t }}
              </template>
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>

  <TrackingPanel
    :open="trackingOpen"
    :prayer="activePrayer"
    :users="trackingUsers"
    :initial-logged-ids="loggedIdsFor(activePrayer || '')"
    :view-date="viewDate"
    :warning-mode="trackingWarning"
    :late-reminder="!!activePrayer && isPrayerLate(activePrayer)"
    @close="closeTracking"
    @committed="onBatchCommitted"
  />

  <canvas
    ref="confetti-canvas"
    style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; z-index: 9999"
  />
</template>
