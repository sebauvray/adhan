<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { api } from '@/api/client'
import PrayerOutputCard from './PrayerOutputCard.vue'

const PRAYERS = ['Fajr', 'Dhuhr', 'Asr', 'Maghrib', 'Isha'] as const
type PrayerName = typeof PRAYERS[number]

interface OwntoneOutput { id: string; name: string; type: string; selected: boolean; volume: number }
interface PrayerCfg {
  outputs: { id: string; name: string }[]
  volume: number
  alert: { enabled: boolean; delay: number }
}

const owntoneOutputs = ref<OwntoneOutput[]>([])
const error = ref('')
const playingPrayer = ref<PrayerName | null>(null)

const cfg = reactive<Record<PrayerName, PrayerCfg>>({
  Fajr: { outputs: [], volume: 30, alert: { enabled: false, delay: 0 } },
  Dhuhr: { outputs: [], volume: 30, alert: { enabled: false, delay: 0 } },
  Asr: { outputs: [], volume: 30, alert: { enabled: false, delay: 0 } },
  Maghrib: { outputs: [], volume: 30, alert: { enabled: false, delay: 0 } },
  Isha: { outputs: [], volume: 30, alert: { enabled: false, delay: 0 } },
})

async function load() {
  error.value = ''
  try {
    const [out, c] = await Promise.all([
      api<{ outputs: OwntoneOutput[] }>('/outputs'),
      api<{
        outputs: Record<string, { id: string; name: string }[]>
        volumes: Record<string, number>
        alerts: Record<string, { enabled: boolean; delay: number }>
      }>('/prayer-outputs'),
    ])
    owntoneOutputs.value = out.outputs || []
    PRAYERS.forEach((p) => {
      cfg[p].outputs = c.outputs?.[p] || []
      cfg[p].volume = c.volumes?.[p] ?? 30
      cfg[p].alert = c.alerts?.[p] || { enabled: false, delay: 0 }
    })
  } catch {
    error.value = 'OwnTone inaccessible.'
  }
}

async function play(prayer: string) {
  if (playingPrayer.value) {
    await api('/stop-playback', { method: 'POST' })
  }
  try {
    await api(`/test-prayer/${prayer}`, { method: 'POST' })
    playingPrayer.value = prayer as PrayerName
  } catch (e) {
    alert((e as Error).message || 'Erreur')
  }
}

async function stop() {
  await api('/stop-playback', { method: 'POST' })
  playingPrayer.value = null
}

onMounted(load)
</script>

<template>
  <div class="form-section">
    <h2>Réglage par prière</h2>
    <div v-if="error" style="font-size: 0.8rem; color: #c53030">{{ error }}</div>
    <div v-else>
      <PrayerOutputCard
        v-for="p in PRAYERS"
        :key="p"
        :prayer="p"
        :owntone-outputs="owntoneOutputs"
        :cfg="cfg[p]"
        :is-playing="playingPrayer === p"
        @play="play"
        @stop="stop"
      />
    </div>
  </div>
</template>
