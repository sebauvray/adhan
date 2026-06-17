<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { api } from '@/api/client'
import { saveConfigField } from '@/api/config'

const enabled = ref(false)
const adhanFilename = ref('')
const alertFilename = ref('')
const adhanStatus = ref('')
const alertStatus = ref('')

const adhanInput = ref<HTMLInputElement | null>(null)
const alertInput = ref<HTMLInputElement | null>(null)

const adhanCustom = computed(() => !!adhanFilename.value)
const alertCustom = computed(() => !!alertFilename.value)

onMounted(async () => {
  const data = await api<{
    sound_enabled: string
    adhan_filename: string
    alert_filename: string
  }>('/config')
  enabled.value = data.sound_enabled === 'true'
  adhanFilename.value = data.adhan_filename || ''
  alertFilename.value = data.alert_filename || ''
})

async function toggleEnabled() {
  await saveConfigField('config', 'SOUND_ENABLED', enabled.value ? 'true' : 'false')
}

async function uploadFile(endpoint: '/upload-adhan' | '/upload-alert', file: File): Promise<string> {
  const fd = new FormData()
  fd.append('file', file)
  const res = await api<{ filename: string; path: string }>(endpoint, { method: 'POST', body: fd })
  return res.filename
}

async function onAdhanChange(e: Event) {
  const input = e.target as HTMLInputElement
  const f = input.files?.[0]
  if (!f) return
  adhanStatus.value = 'Envoi en cours...'
  try {
    adhanFilename.value = await uploadFile('/upload-adhan', f)
    adhanStatus.value = ''
  } catch (err) {
    adhanStatus.value = (err as Error).message || 'Erreur'
  } finally {
    input.value = ''
  }
}

async function removeAdhan() {
  if (!confirm('Supprimer le fichier audio personnalisé ?')) return
  await api('/upload-adhan', { method: 'DELETE' })
  adhanFilename.value = ''
}

async function onAlertChange(e: Event) {
  const input = e.target as HTMLInputElement
  const f = input.files?.[0]
  if (!f) return
  alertStatus.value = 'Envoi en cours...'
  try {
    alertFilename.value = await uploadFile('/upload-alert', f)
    alertStatus.value = ''
  } catch (err) {
    alertStatus.value = (err as Error).message || 'Erreur'
  } finally {
    input.value = ''
  }
}

async function removeAlert() {
  if (!confirm("Supprimer le son d'alerte personnalisé ?")) return
  await api('/upload-alert', { method: 'DELETE' })
  alertFilename.value = ''
}
</script>

<template>
  <div class="form-section">
    <h2>Alertes sonores</h2>
    <div class="form-group">
      <label class="checkbox-label">
        <input v-model="enabled" type="checkbox" @change="toggleEnabled">
        Activer l'appel à la prière sur les enceintes
      </label>
    </div>

    <div v-show="enabled" style="margin-top: 0.8rem">
      <div class="form-group">
        <label>Son adhan</label>
        <input
          ref="adhanInput"
          type="file"
          accept=".mp3,.wav,.ogg,.m4a,.flac"
          style="display: none"
          @change="onAdhanChange"
        >
        <div class="upload-component">
          <div v-if="!adhanCustom">
            <span style="font-size: 0.8rem; color: var(--text-dark-muted)">Fichier par défaut</span>
            <button
              type="button"
              class="btn btn-action"
              style="font-size: 0.75rem; padding: 0.3rem 0.8rem; margin-left: 0.5rem"
              @click="adhanInput?.click()"
            >
              Personnaliser
            </button>
          </div>
          <div v-else style="display: inline-flex">
            <span class="upload-file-tag">
              <span class="filename">{{ adhanFilename }}</span>
              <button type="button" class="remove-btn" title="Supprimer" @click="removeAdhan">&times;</button>
            </span>
          </div>
        </div>
        <div v-if="adhanStatus" style="font-size: 0.75rem; margin-top: 0.3rem">{{ adhanStatus }}</div>
      </div>

      <div class="form-group" style="margin-top: 0.6rem">
        <label>Son alerte iqama</label>
        <input
          ref="alertInput"
          type="file"
          accept=".mp3,.wav,.ogg,.m4a,.flac"
          style="display: none"
          @change="onAlertChange"
        >
        <div class="upload-component">
          <div v-if="!alertCustom">
            <span style="font-size: 0.8rem; color: var(--text-dark-muted)">Fichier par défaut</span>
            <button
              type="button"
              class="btn btn-action"
              style="font-size: 0.75rem; padding: 0.3rem 0.8rem; margin-left: 0.5rem"
              @click="alertInput?.click()"
            >
              Personnaliser
            </button>
          </div>
          <div v-else style="display: inline-flex">
            <span class="upload-file-tag">
              <span class="filename">{{ alertFilename }}</span>
              <button type="button" class="remove-btn" title="Supprimer" @click="removeAlert">&times;</button>
            </span>
          </div>
        </div>
        <div v-if="alertStatus" style="font-size: 0.75rem; margin-top: 0.3rem">{{ alertStatus }}</div>
      </div>

    </div>
  </div>
</template>
