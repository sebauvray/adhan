<script setup lang="ts">
import { ref } from 'vue'
import { api } from '@/api/client'

interface OwntoneOutput { id: string; name: string }
interface PrayerCfg {
  outputs: { id: string; name: string }[]
  volume: number
  alert: { enabled: boolean; delay: number }
}

const props = defineProps<{
  prayer: string
  owntoneOutputs: OwntoneOutput[]
  cfg: PrayerCfg
  isPlaying: boolean
}>()

const emit = defineEmits<{
  play: [prayer: string]
  stop: []
}>()

const justSaved = ref(false)

function flashSaved() {
  justSaved.value = true
  setTimeout(() => (justSaved.value = false), 2000)
}

function isSelected(id: string): boolean {
  return props.cfg.outputs.some((o) => o.id === id)
}

async function save() {
  await api('/prayer-outputs', {
    method: 'POST',
    body: JSON.stringify({
      outputs: { [props.prayer]: props.cfg.outputs },
      volumes: { [props.prayer]: props.cfg.volume },
      alerts: { [props.prayer]: props.cfg.alert },
    }),
  })
  flashSaved()
}

function toggleOutput(o: OwntoneOutput) {
  const idx = props.cfg.outputs.findIndex((x) => x.id === o.id)
  if (idx >= 0) props.cfg.outputs.splice(idx, 1)
  else props.cfg.outputs.push({ id: o.id, name: o.name })
  save()
}

function onTestClick() {
  if (props.isPlaying) emit('stop')
  else emit('play', props.prayer)
}
</script>

<template>
  <div :class="['prayer-config-card', { saved: justSaved }]" :data-prayer="prayer">
    <div class="prayer-config-header">
      <span class="prayer-config-name">{{ prayer }}</span>
      <button
        type="button"
        :class="['prayer-test-btn', { playing: isPlaying }]"
        title="Tester"
        @click="onTestClick"
      >
        <svg v-if="!isPlaying" width="18" height="18" viewBox="0 0 24 24" fill="currentColor" stroke="none">
          <polygon points="5,3 19,12 5,21"/>
        </svg>
        <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="currentColor" stroke="none">
          <rect x="5" y="3" width="4" height="18"/>
          <rect x="15" y="3" width="4" height="18"/>
        </svg>
      </button>
    </div>
    <div class="prayer-config-outputs">
      <label
        v-for="o in owntoneOutputs"
        :key="o.id"
        :class="['output-chip', { selected: isSelected(o.id) }]"
        @click.prevent="toggleOutput(o)"
      >
        <input type="checkbox" :checked="isSelected(o.id)">
        {{ o.name }}
      </label>
    </div>
    <div class="prayer-volume">
      <span>Volume</span>
      <input v-model.number="cfg.volume" type="range" min="0" max="100" @change="save">
      <span class="prayer-volume-value">{{ cfg.volume }}</span>
    </div>
    <div class="prayer-alert">
      <label class="checkbox-label">
        <input v-model="cfg.alert.enabled" type="checkbox" @change="save">
        Alerte iqama
      </label>
      <div :class="['alert-delay', { hidden: !cfg.alert.enabled }]">
        <span>+</span>
        <input v-model.number="cfg.alert.delay" type="number" class="alert-delay-input" min="0" max="60" step="5" @blur="save">
        <span>min</span>
      </div>
    </div>
  </div>
</template>
