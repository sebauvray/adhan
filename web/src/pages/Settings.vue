<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api/client'
import SettingsHeader from '@/components/SettingsHeader.vue'
import EmojiPicker from '@/components/EmojiPicker.vue'

const router = useRouter()
const PRAYERS = ['Fajr', 'Dhuhr', 'Asr', 'Maghrib', 'Isha'] as const
type PrayerName = typeof PRAYERS[number]

interface User { id: number; name: string; emoji: string }
interface OwntoneOutput { id: string; name: string; type: string; selected: boolean; volume: number }
interface PrayerOutputCfg {
  outputs: { id: string; name: string }[]
  volume: number
  alert: { enabled: boolean; delay: number }
}
interface Token {
  id: number
  description: string
  scope: string
  user_id: number | null
  user_name?: string
  user_emoji?: string
  created_at?: string
}
interface ConfigResponse {
  mosque_url: string
  city: string
  sound_enabled: string
  log_level: string
  owntone_host: string
  owntone_port: string
  adhan_file: string
  adhan_volume: string
  alert_file: string
  quiet_start: string
  quiet_end: string
  quiet_volume: string
  multi_day_display: string
}

// --- Config (auto-save) ---
const config = reactive({
  mosque_url: '',
  log_level: 'INFO',
  owntone_host: 'host.docker.internal',
  owntone_port: '3689',
  quiet_start: '21:00',
  quiet_end: '07:00',
  quiet_volume: '10',
  sound_enabled: false,
  multi_day_display: false,
  adhan_file: '',
  alert_file: '',
})

const savedFields = ref<Set<string>>(new Set())
function flashSaved(field: string) {
  savedFields.value.add(field)
  savedFields.value = new Set(savedFields.value)
  setTimeout(() => {
    savedFields.value.delete(field)
    savedFields.value = new Set(savedFields.value)
  }, 2000)
}

async function saveField(table: string, key: string, value: string) {
  try {
    await api('/config', {
      method: 'POST',
      body: JSON.stringify({ table, key, value }),
    })
  } catch (e) {
    if ((e as Error).message?.includes('Authentification')) {
      router.push('/login?next=/settings')
    }
  }
}

async function onFieldBlur(field: keyof typeof config, table: string, key: string) {
  await saveField(table, key, String(config[field]))
  flashSaved(field)
}

async function onCheckboxToggle(field: 'sound_enabled' | 'multi_day_display', table: string, key: string) {
  await saveField(table, key, config[field] ? 'true' : 'false')
  flashSaved(field)
}

// --- Users ---
const users = ref<User[]>([])
const newUser = reactive({ name: '', emoji: '🙂' })

async function loadUsers() {
  const data = await api<{ users: User[] }>('/users')
  users.value = data.users || []
}

async function addUser() {
  if (!newUser.name.trim()) return
  await api('/users', {
    method: 'POST',
    body: JSON.stringify({ name: newUser.name.trim(), emoji: newUser.emoji }),
  })
  newUser.name = ''
  newUser.emoji = '🙂'
  await loadUsers()
  await loadTokensUsers()
}

async function deleteUser(id: number) {
  if (!confirm('Supprimer cet utilisateur et son historique ?')) return
  await api(`/users/${id}`, { method: 'DELETE' })
  await loadUsers()
  await loadTokensUsers()
}

async function updateUserEmoji(user: User, emoji: string) {
  user.emoji = emoji
  await api(`/users/${user.id}`, {
    method: 'PUT',
    body: JSON.stringify({ name: user.name, emoji }),
  })
}

// --- Tokens (prayers scope only — admin tokens stay backend-only) ---
const tokens = ref<Token[]>([])
const tokensUsers = ref<User[]>([])
const newToken = reactive({ user_id: '', description: '' })
const newTokenValue = ref('')

async function loadTokensUsers() {
  const data = await api<{ users: User[] }>('/users')
  tokensUsers.value = data.users || []
}

async function loadTokens() {
  try {
    const data = await api<{ tokens: Token[] }>('/tokens')
    tokens.value = (data.tokens || []).filter((t) => t.scope === 'prayers')
  } catch (e) {
    if ((e as Error).message?.includes('Authentification')) {
      router.push('/login?next=/settings')
    }
  }
}

async function createToken() {
  if (!newToken.user_id) {
    alert('Sélectionne un utilisateur')
    return
  }
  try {
    const res = await api<{ token: string }>('/tokens', {
      method: 'POST',
      body: JSON.stringify({
        scope: 'prayers',
        user_id: parseInt(newToken.user_id),
        description: newToken.description.trim() || 'API',
      }),
    })
    newTokenValue.value = res.token
    newToken.description = ''
    newToken.user_id = ''
    await loadTokens()
  } catch (e) {
    alert((e as Error).message || 'Erreur')
  }
}

async function deleteToken(id: number) {
  if (!confirm('Révoquer ce token ?')) return
  await api(`/tokens/${id}`, { method: 'DELETE' })
  await loadTokens()
}

// --- Adhan / Alert file uploads ---
async function uploadFile(endpoint: '/upload-adhan' | '/upload-alert', file: File): Promise<string | null> {
  const fd = new FormData()
  fd.append('file', file)
  try {
    const res = await api<{ filename: string; path: string }>(endpoint, { method: 'POST', body: fd })
    return res.path
  } catch (e) {
    return Promise.reject(e)
  }
}

const adhanUploadStatus = ref('')
const alertUploadStatus = ref('')

async function onAdhanFileChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  adhanUploadStatus.value = 'Envoi en cours...'
  try {
    const path = await uploadFile('/upload-adhan', file)
    if (path) config.adhan_file = path
    adhanUploadStatus.value = ''
  } catch (err) {
    adhanUploadStatus.value = (err as Error).message || 'Erreur'
  }
}

async function removeAdhanFile() {
  if (!confirm('Supprimer le fichier audio personnalisé ?')) return
  await api('/upload-adhan', { method: 'DELETE' })
  config.adhan_file = '/srv/media/adhan.mp3'
}

async function onAlertFileChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  alertUploadStatus.value = 'Envoi en cours...'
  try {
    const path = await uploadFile('/upload-alert', file)
    if (path) config.alert_file = path
    alertUploadStatus.value = ''
  } catch (err) {
    alertUploadStatus.value = (err as Error).message || 'Erreur'
  }
}

async function removeAlertFile() {
  if (!confirm("Supprimer le son d'alerte personnalisé ?")) return
  await api('/upload-alert', { method: 'DELETE' })
  config.alert_file = '/srv/media/alert.mp3'
}

const adhanCustom = computed(() => config.adhan_file && config.adhan_file !== '/srv/media/adhan.mp3')
const alertCustom = computed(() => config.alert_file && config.alert_file !== '/srv/media/alert.mp3')
const adhanFilename = computed(() => config.adhan_file.split('/').pop() || '')
const alertFilename = computed(() => config.alert_file.split('/').pop() || '')

// --- Prayer outputs (cards) ---
const owntoneOutputs = ref<OwntoneOutput[]>([])
const owntoneError = ref('')
const prayerCfg = reactive<Record<PrayerName, PrayerOutputCfg>>({
  Fajr: { outputs: [], volume: 30, alert: { enabled: false, delay: 0 } },
  Dhuhr: { outputs: [], volume: 30, alert: { enabled: false, delay: 0 } },
  Asr: { outputs: [], volume: 30, alert: { enabled: false, delay: 0 } },
  Maghrib: { outputs: [], volume: 30, alert: { enabled: false, delay: 0 } },
  Isha: { outputs: [], volume: 30, alert: { enabled: false, delay: 0 } },
})
const savedPrayer = ref<Set<string>>(new Set())
function flashSavedPrayer(p: string) {
  savedPrayer.value.add(p)
  savedPrayer.value = new Set(savedPrayer.value)
  setTimeout(() => {
    savedPrayer.value.delete(p)
    savedPrayer.value = new Set(savedPrayer.value)
  }, 2000)
}

async function loadPrayerOutputs() {
  owntoneError.value = ''
  try {
    const [out, cfg] = await Promise.all([
      api<{ outputs: OwntoneOutput[] }>('/outputs'),
      api<{
        outputs: Record<string, { id: string; name: string }[]>
        volumes: Record<string, number>
        alerts: Record<string, { enabled: boolean; delay: number }>
      }>('/prayer-outputs'),
    ])
    owntoneOutputs.value = out.outputs || []
    PRAYERS.forEach((p) => {
      prayerCfg[p].outputs = cfg.outputs?.[p] || []
      prayerCfg[p].volume = cfg.volumes?.[p] ?? 30
      prayerCfg[p].alert = cfg.alerts?.[p] || { enabled: false, delay: 0 }
    })
  } catch (e) {
    owntoneError.value = 'OwnTone inaccessible.'
  }
}

function isOutputSelected(prayer: PrayerName, id: string): boolean {
  return prayerCfg[prayer].outputs.some((o) => o.id === id)
}

function toggleOutput(prayer: PrayerName, output: OwntoneOutput) {
  const cur = prayerCfg[prayer].outputs
  const idx = cur.findIndex((o) => o.id === output.id)
  if (idx >= 0) cur.splice(idx, 1)
  else cur.push({ id: output.id, name: output.name })
  savePrayerCard(prayer)
}

async function savePrayerCard(prayer: PrayerName) {
  try {
    await api('/prayer-outputs', {
      method: 'POST',
      body: JSON.stringify({
        outputs: { [prayer]: prayerCfg[prayer].outputs },
        volumes: { [prayer]: prayerCfg[prayer].volume },
        alerts: { [prayer]: prayerCfg[prayer].alert },
      }),
    })
    flashSavedPrayer(prayer)
  } catch (e) {
    if ((e as Error).message?.includes('Authentification')) {
      router.push('/login?next=/settings')
    }
  }
}

// --- Test playback ---
const playingPrayer = ref<PrayerName | null>(null)

async function toggleTestPrayer(prayer: PrayerName) {
  if (playingPrayer.value === prayer) {
    await api('/stop-playback', { method: 'POST' })
    playingPrayer.value = null
    return
  }
  if (playingPrayer.value) {
    await api('/stop-playback', { method: 'POST' })
  }
  await savePrayerCard(prayer)
  try {
    await api(`/test-prayer/${prayer}`, { method: 'POST' })
    playingPrayer.value = prayer
  } catch (e) {
    alert((e as Error).message || 'Erreur')
  }
}

// --- Owntone link ---
const owntoneLink = computed(() => `http://${window.location.hostname}:${config.owntone_port || '3689'}`)

// --- Init ---
async function loadConfig() {
  const data = await api<ConfigResponse>('/config')
  config.mosque_url = data.mosque_url || ''
  config.log_level = data.log_level || 'INFO'
  config.owntone_host = data.owntone_host || 'host.docker.internal'
  config.owntone_port = data.owntone_port || '3689'
  config.quiet_start = data.quiet_start || '21:00'
  config.quiet_end = data.quiet_end || '07:00'
  config.quiet_volume = data.quiet_volume || '10'
  config.sound_enabled = data.sound_enabled === 'true'
  config.multi_day_display = data.multi_day_display === 'true'
  config.adhan_file = data.adhan_file || ''
  config.alert_file = data.alert_file || ''
}

onMounted(async () => {
  document.body.classList.add('settings-page')
  await loadConfig()
  await loadUsers()
  await loadTokensUsers()
  await loadTokens()
  await loadPrayerOutputs()
})

onUnmounted(() => {
  document.body.classList.remove('settings-page')
})
</script>

<template>
  <div class="settings">
    <SettingsHeader title="Paramètres" subtitle="Sauvegarde automatique" />

    <div class="settings-content">
      <div class="settings-left">
        <!-- Mosque -->
        <div class="form-section">
          <h2>Mosquée</h2>
          <div class="form-group">
            <label for="mosque_url">URL mawaqit.net</label>
            <span class="save-indicator" :class="{ visible: savedFields.has('mosque_url') }">Sauvegardé</span>
            <input
              id="mosque_url"
              v-model="config.mosque_url"
              type="url"
              :class="{ saved: savedFields.has('mosque_url') }"
              @blur="onFieldBlur('mosque_url', 'config', 'MOSQUE_URL')"
            >
          </div>
        </div>

        <!-- Advanced -->
        <details class="form-section">
          <summary
            style="cursor: pointer; font-size: 0.85rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-dark-muted); padding-bottom: 0.4rem; border-bottom: 1px solid rgba(0,0,0,0.06)"
          >
            Avancé
          </summary>
          <div style="margin-top: 0.8rem">
            <div class="form-row">
              <div class="form-group">
                <label for="log_level">Niveau de log</label>
                <span class="save-indicator" :class="{ visible: savedFields.has('log_level') }">Sauvegardé</span>
                <select
                  id="log_level"
                  v-model="config.log_level"
                  :class="{ saved: savedFields.has('log_level') }"
                  @change="onFieldBlur('log_level', 'config', 'LOG_LEVEL')"
                >
                  <option value="DEBUG">DEBUG</option>
                  <option value="INFO">INFO</option>
                  <option value="WARN">WARN</option>
                  <option value="ERROR">ERROR</option>
                </select>
              </div>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label for="owntone_host">OwnTone hôte</label>
                <span class="save-indicator" :class="{ visible: savedFields.has('owntone_host') }">Sauvegardé</span>
                <input
                  id="owntone_host"
                  v-model="config.owntone_host"
                  type="text"
                  :class="{ saved: savedFields.has('owntone_host') }"
                  @blur="onFieldBlur('owntone_host', 'owntone', 'HOST')"
                >
              </div>
              <div class="form-group">
                <label for="owntone_port">OwnTone port</label>
                <span class="save-indicator" :class="{ visible: savedFields.has('owntone_port') }">Sauvegardé</span>
                <input
                  id="owntone_port"
                  v-model="config.owntone_port"
                  type="text"
                  :class="{ saved: savedFields.has('owntone_port') }"
                  @blur="onFieldBlur('owntone_port', 'owntone', 'PORT')"
                >
              </div>
            </div>
            <div class="form-row" style="margin-top: 0.5rem">
              <div class="form-group">
                <label for="quiet_start">Heures calmes — début</label>
                <span class="save-indicator" :class="{ visible: savedFields.has('quiet_start') }">Sauvegardé</span>
                <input
                  id="quiet_start"
                  v-model="config.quiet_start"
                  type="time"
                  :class="{ saved: savedFields.has('quiet_start') }"
                  @blur="onFieldBlur('quiet_start', 'config', 'QUIET_START')"
                >
              </div>
              <div class="form-group">
                <label for="quiet_end">Heures calmes — fin</label>
                <span class="save-indicator" :class="{ visible: savedFields.has('quiet_end') }">Sauvegardé</span>
                <input
                  id="quiet_end"
                  v-model="config.quiet_end"
                  type="time"
                  :class="{ saved: savedFields.has('quiet_end') }"
                  @blur="onFieldBlur('quiet_end', 'config', 'QUIET_END')"
                >
              </div>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label for="quiet_volume">Volume max (heures calmes)</label>
                <span class="save-indicator" :class="{ visible: savedFields.has('quiet_volume') }">Sauvegardé</span>
                <input
                  id="quiet_volume"
                  v-model="config.quiet_volume"
                  type="number"
                  min="0"
                  max="100"
                  :class="{ saved: savedFields.has('quiet_volume') }"
                  @blur="onFieldBlur('quiet_volume', 'config', 'QUIET_VOLUME')"
                >
              </div>
            </div>
          </div>
        </details>

        <!-- API tokens -->
        <div class="form-section">
          <h2>Tokens API externes</h2>
          <p style="font-size: 0.75rem; color: var(--text-dark-muted); margin-bottom: 0.6rem">
            Tokens scope <code>prayers</code> pour valider/lire les prières d'un utilisateur depuis une app externe.
          </p>
          <div>
            <p v-if="!tokens.length" style="font-size: 0.75rem; color: var(--text-dark-muted)">Aucun token externe</p>
            <div v-for="t in tokens" :key="t.id" class="user-item">
              <span class="emoji-pick-btn" style="cursor: default">{{ t.user_emoji || '🔑' }}</span>
              <div style="flex: 1; min-width: 0">
                <div class="user-name">{{ t.description || 'API' }}</div>
                <div style="font-size: 0.7rem; color: var(--text-dark-muted)">
                  {{ t.user_name || '?' }} · {{ t.created_at || '' }}
                </div>
              </div>
              <button type="button" class="remove-btn" title="Révoquer" @click="deleteToken(t.id)">&times;</button>
            </div>
          </div>
          <div class="user-add-form" style="margin-top: 0.6rem">
            <select v-model="newToken.user_id" class="user-name-input" style="flex: 1">
              <option value="">-- Utilisateur --</option>
              <option v-for="u in tokensUsers" :key="u.id" :value="u.id">{{ u.emoji }} {{ u.name }}</option>
            </select>
            <input
              v-model="newToken.description"
              type="text"
              class="user-name-input"
              placeholder="Description (ex: Home Assistant)"
              style="flex: 1.5"
            >
            <button type="button" class="btn btn-action btn-sm" @click="createToken">+</button>
          </div>
          <div v-if="newTokenValue" class="token-display">
            <strong>Token généré (copie-le maintenant, il ne sera plus affiché) :</strong>
            <code>{{ newTokenValue }}</code>
          </div>
        </div>

        <!-- Multi-day display -->
        <div class="form-section">
          <h2>Suivi des prières</h2>
          <div class="form-group">
            <label class="checkbox-label">
              <input
                v-model="config.multi_day_display"
                type="checkbox"
                @change="onCheckboxToggle('multi_day_display', 'config', 'MULTI_DAY_DISPLAY')"
              >
              Afficher plusieurs jours (veille, jour, lendemain)
            </label>
          </div>
        </div>

        <!-- Users -->
        <div class="form-section">
          <h2>Utilisateurs</h2>
          <div>
            <p v-if="!users.length" style="font-size: 0.8rem; color: var(--text-dark-muted)">Aucun utilisateur</p>
            <div v-for="u in users" :key="u.id" class="user-item">
              <EmojiPicker :model-value="u.emoji" @update:model-value="(v: string) => updateUserEmoji(u, v)" />
              <span class="user-name">{{ u.name }}</span>
              <button type="button" class="remove-btn" title="Supprimer" @click="deleteUser(u.id)">&times;</button>
            </div>
          </div>
          <div class="user-add-form">
            <EmojiPicker v-model="newUser.emoji" />
            <input
              v-model="newUser.name"
              type="text"
              placeholder="Nom"
              class="user-name-input"
              @keydown.enter="addUser"
            >
            <button type="button" class="btn btn-action btn-sm" @click="addUser">+</button>
          </div>
        </div>
      </div>

      <div class="settings-right">
        <!-- Sound alerts -->
        <div class="form-section">
          <h2>Alertes sonores</h2>
          <div class="form-group">
            <label class="checkbox-label">
              <input
                v-model="config.sound_enabled"
                type="checkbox"
                @change="onCheckboxToggle('sound_enabled', 'config', 'SOUND_ENABLED')"
              >
              Activer l'appel à la prière sur les enceintes
            </label>
          </div>

          <div v-show="config.sound_enabled" style="margin-top: 0.8rem">
            <div class="form-group">
              <label>Son adhan</label>
              <input
                id="adhan_upload"
                type="file"
                accept=".mp3,.wav,.ogg,.m4a,.flac"
                style="display: none"
                @change="onAdhanFileChange"
              >
              <div class="upload-component">
                <div v-if="!adhanCustom">
                  <span style="font-size: 0.8rem; color: var(--text-dark-muted)">Fichier par défaut</span>
                  <button
                    type="button"
                    class="btn btn-action"
                    style="font-size: 0.75rem; padding: 0.3rem 0.8rem; margin-left: 0.5rem"
                    onclick="document.getElementById('adhan_upload').click()"
                  >
                    Personnaliser
                  </button>
                </div>
                <div v-else style="display: inline-flex">
                  <span class="upload-file-tag">
                    <span class="filename">{{ adhanFilename }}</span>
                    <button type="button" class="remove-btn" title="Supprimer" @click="removeAdhanFile">&times;</button>
                  </span>
                </div>
              </div>
              <div v-if="adhanUploadStatus" style="font-size: 0.75rem; margin-top: 0.3rem">{{ adhanUploadStatus }}</div>
            </div>
            <div class="form-group" style="margin-top: 0.6rem">
              <label>Son alerte iqama</label>
              <input
                id="alert_upload"
                type="file"
                accept=".mp3,.wav,.ogg,.m4a,.flac"
                style="display: none"
                @change="onAlertFileChange"
              >
              <div class="upload-component">
                <div v-if="!alertCustom">
                  <span style="font-size: 0.8rem; color: var(--text-dark-muted)">Fichier par défaut</span>
                  <button
                    type="button"
                    class="btn btn-action"
                    style="font-size: 0.75rem; padding: 0.3rem 0.8rem; margin-left: 0.5rem"
                    onclick="document.getElementById('alert_upload').click()"
                  >
                    Personnaliser
                  </button>
                </div>
                <div v-else style="display: inline-flex">
                  <span class="upload-file-tag">
                    <span class="filename">{{ alertFilename }}</span>
                    <button type="button" class="remove-btn" title="Supprimer" @click="removeAlertFile">&times;</button>
                  </span>
                </div>
              </div>
              <div v-if="alertUploadStatus" style="font-size: 0.75rem; margin-top: 0.3rem">{{ alertUploadStatus }}</div>
            </div>
            <p style="margin-top: 0.5rem; font-size: 0.8rem">
              <a :href="owntoneLink" target="_blank" class="link-action">
                Gérer les enceintes dans OwnTone &rarr;
              </a>
            </p>
          </div>
        </div>

        <!-- Per-prayer config -->
        <div class="form-section">
          <h2>Réglage par prière</h2>
          <div v-if="owntoneError" style="font-size: 0.8rem; color: #c53030">{{ owntoneError }}</div>
          <div v-else>
            <div
              v-for="p in PRAYERS"
              :key="p"
              :class="['prayer-config-card', { saved: savedPrayer.has(p) }]"
              :data-prayer="p"
            >
              <div class="prayer-config-header">
                <span class="prayer-config-name">{{ p }}</span>
                <button
                  type="button"
                  :class="['prayer-test-btn', { playing: playingPrayer === p }]"
                  title="Tester"
                  @click="toggleTestPrayer(p)"
                >
                  <svg
                    v-if="playingPrayer !== p"
                    width="18"
                    height="18"
                    viewBox="0 0 24 24"
                    fill="currentColor"
                    stroke="none"
                  >
                    <polygon points="5,3 19,12 5,21" />
                  </svg>
                  <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="currentColor" stroke="none">
                    <rect x="5" y="3" width="4" height="18" />
                    <rect x="15" y="3" width="4" height="18" />
                  </svg>
                </button>
              </div>
              <div class="prayer-config-outputs">
                <label
                  v-for="o in owntoneOutputs"
                  :key="o.id"
                  :class="['output-chip', { selected: isOutputSelected(p, o.id) }]"
                  @click.prevent="toggleOutput(p, o)"
                >
                  <input type="checkbox" :checked="isOutputSelected(p, o.id)">
                  {{ o.name }}
                </label>
              </div>
              <div class="prayer-volume">
                <span>Volume</span>
                <input
                  v-model.number="prayerCfg[p].volume"
                  type="range"
                  min="0"
                  max="100"
                  @change="savePrayerCard(p)"
                >
                <span class="prayer-volume-value">{{ prayerCfg[p].volume }}</span>
              </div>
              <div class="prayer-alert">
                <label class="checkbox-label">
                  <input
                    v-model="prayerCfg[p].alert.enabled"
                    type="checkbox"
                    @change="savePrayerCard(p)"
                  >
                  Alerte iqama
                </label>
                <div :class="['alert-delay', { hidden: !prayerCfg[p].alert.enabled }]">
                  <span>+</span>
                  <input
                    v-model.number="prayerCfg[p].alert.delay"
                    type="number"
                    class="alert-delay-input"
                    min="0"
                    max="60"
                    step="5"
                    @blur="savePrayerCard(p)"
                  >
                  <span>min</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
