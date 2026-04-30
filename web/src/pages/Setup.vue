<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api/client'
import CardLayout from '@/layouts/CardLayout.vue'
import EmojiPicker from '@/components/EmojiPicker.vue'
import ProviderFields from '@/components/audio/ProviderFields.vue'
import type { ProviderManifest } from '@/types/audio'

const router = useRouter()

const step = ref(0)
const accountError = ref('')
const passwordConfirm = ref('')
const validating = ref(false)
const installing = ref(false)
const urlPreview = ref<{ city: string; prayers: { name: string; adhan: string }[] } | null>(null)
const urlError = ref('')

const providers = ref<ProviderManifest[]>([])

// Provider start UX
const pendingProvider = ref<ProviderManifest | null>(null)  // shown in confirm modal
const startingProvider = ref<string>('')                    // id of provider being started (drives transition)
const startState = ref<string>('idle')                      // idle | starting | bootstrapping | ready | failed
const startMessage = ref<string>('')
const startError = ref<string>('')
let pollHandle: ReturnType<typeof setInterval> | null = null

const data = reactive({
  username: '',
  password: '',
  emoji: '🙂',
  mosque_url: '',
  sound_enabled: 'false' as 'true' | 'false',
  city: '',
  audio: {
    mode: 'bundled' as 'bundled' | 'external',
    config: {} as Record<string, string>,
  },
})

const redirectSeconds = ref(5)
let redirectInterval: ReturnType<typeof setInterval> | null = null

onMounted(async () => {
  try {
    const res = await api<{ providers: ProviderManifest[] }>('/audio/providers')
    providers.value = res.providers || []
  } catch {
    providers.value = []
  }
})

onUnmounted(() => {
  if (redirectInterval) clearInterval(redirectInterval)
  if (pollHandle) clearInterval(pollHandle)
})

// Whichever provider is "active in the wizard" — the one staying centered
// during the transition. While picking, both cards show; once a card is
// confirmed, only that one stays.
const visibleProviders = computed(() => {
  if (!startingProvider.value) return providers.value
  return providers.value.filter(p => p.id === startingProvider.value)
})

const activeProvider = computed<ProviderManifest | null>(
  () => providers.value.find(p => p.id === startingProvider.value) ?? null,
)

watch(pendingProvider, (p) => {
  if (!p) return
  data.audio.mode = (p.setup_modes[0]?.id as 'bundled' | 'external') ?? 'bundled'
  data.audio.config = Object.fromEntries(p.fields.map(f => [f.key, f.default]))
})

function goToStep(n: number) {
  step.value = n
}

function validateAccount() {
  accountError.value = ''
  if (data.username.trim().length < 3) {
    accountError.value = "L'identifiant doit faire au moins 3 caractères."
    return
  }
  if (data.password.length < 8) {
    accountError.value = 'Le mot de passe doit faire au moins 8 caractères.'
    return
  }
  if (data.password !== passwordConfirm.value) {
    accountError.value = 'Les deux mots de passe ne correspondent pas.'
    return
  }
  data.username = data.username.trim()
  goToStep(1)
}

async function validateUrl() {
  const url = data.mosque_url.trim()
  if (!url) return

  validating.value = true
  urlPreview.value = null
  urlError.value = ''

  try {
    const res = await api<{ valid: boolean; city?: string; prayers?: { name: string; adhan: string }[]; error?: string }>(
      '/validate-url',
      { method: 'POST', body: JSON.stringify({ url }) },
    )
    if (res.valid) {
      urlPreview.value = { city: res.city || '', prayers: res.prayers || [] }
      data.city = res.city || ''
    } else {
      urlError.value = res.error || 'URL invalide'
    }
  } catch {
    urlError.value = 'Erreur de connexion'
  } finally {
    validating.value = false
  }
}

function selectSound(enabled: boolean) {
  data.sound_enabled = enabled ? 'true' : 'false'
}

async function persistSetup() {
  // Save admin + mosque + sound flag. Audio provider is handled in step 3.
  await api<{ success: boolean }>('/setup', {
    method: 'POST',
    body: JSON.stringify({
      username: data.username,
      password: data.password,
      emoji: data.emoji,
      mosque_url: data.mosque_url,
      sound_enabled: data.sound_enabled,
    }),
  })
}

async function goToSoundNext() {
  installing.value = true
  try {
    await persistSetup()
    if (data.sound_enabled === 'true') {
      goToStep(3)
    } else {
      finishWithoutAudio()
    }
  } catch (e) {
    alert((e as Error).message || "Erreur d'installation")
  } finally {
    installing.value = false
  }
}

function pickProvider(p: ProviderManifest) {
  pendingProvider.value = p
}

function cancelPick() {
  pendingProvider.value = null
}

async function confirmPick() {
  const p = pendingProvider.value
  if (!p) return
  pendingProvider.value = null

  // Trigger the visual transition: this hides the other card.
  startingProvider.value = p.id
  startState.value = 'starting'
  startMessage.value = `Démarrage de ${p.label}…`
  startError.value = ''

  try {
    await api('/audio/start-provider', {
      method: 'POST',
      body: JSON.stringify({
        provider: p.id,
        mode: data.audio.mode,
        config: data.audio.config,
        admin_username: data.username,
        admin_password: data.password,
      }),
    })
    pollStartStatus()
  } catch (e) {
    startState.value = 'failed'
    startError.value = (e as Error).message || 'Erreur'
  }
}

function pollStartStatus() {
  if (pollHandle) clearInterval(pollHandle)
  pollHandle = setInterval(async () => {
    try {
      const s = await api<{ state: string; message: string; error: string | null }>('/audio/start-status')
      startState.value = s.state
      startMessage.value = s.message || ''
      if (s.state === 'ready') {
        if (pollHandle) clearInterval(pollHandle)
        finishAfterStart()
      } else if (s.state === 'failed') {
        startError.value = s.error || 'Erreur inconnue'
        if (pollHandle) clearInterval(pollHandle)
      }
    } catch {
      /* swallow transient polling errors */
    }
  }, 1500)
}

function retryProvider() {
  startingProvider.value = ''
  startState.value = 'idle'
  startError.value = ''
}

function finishAfterStart() {
  goToStep(4)
  scheduleRedirect()
}

function finishWithoutAudio() {
  goToStep(4)
  scheduleRedirect()
}

function scheduleRedirect() {
  redirectSeconds.value = 5
  redirectInterval = setInterval(() => {
    redirectSeconds.value -= 1
    if (redirectSeconds.value <= 0) {
      if (redirectInterval) clearInterval(redirectInterval)
      router.push('/dashboard')
    }
  }, 1000)
}
</script>

<template>
  <CardLayout title="Adhan Home" subtitle="Installation en quelques étapes">
      <div class="steps-indicator">
        <div v-for="i in 5" :key="i" class="dot" :class="{ active: step >= i - 1 }"></div>
      </div>

      <!-- Step 0: Admin account -->
      <div v-show="step === 0" class="step active">
        <div class="form-section">
          <h2>Compte administrateur</h2>
          <p style="font-size: 0.8rem; color: var(--text-dark-muted); margin-bottom: 0.8rem">
            Choisissez un avatar, un identifiant et un mot de passe. L'avatar sera utilisé pour le suivi des prières.
          </p>
          <div class="form-group">
            <label for="setup_username">Identifiant</label>
            <div style="display: flex; gap: 0.5rem; align-items: center">
              <EmojiPicker v-model="data.emoji" />
              <input
                id="setup_username"
                v-model="data.username"
                type="text"
                autocomplete="username"
                placeholder="ex: admin"
                minlength="3"
                required
                style="flex: 1"
              >
            </div>
          </div>
          <div class="form-group">
            <label for="setup_password">Mot de passe (8 caractères minimum)</label>
            <input
              id="setup_password"
              v-model="data.password"
              type="password"
              autocomplete="new-password"
              minlength="8"
              required
            >
          </div>
          <div class="form-group">
            <label for="setup_password_confirm">Confirmer le mot de passe</label>
            <input
              id="setup_password_confirm"
              v-model="passwordConfirm"
              type="password"
              autocomplete="new-password"
              minlength="8"
              required
            >
          </div>
          <div v-if="accountError" class="msg msg-error" style="margin-top: 0.5rem">{{ accountError }}</div>
        </div>
        <div class="actions">
          <span></span>
          <button type="button" class="btn btn-action" @click="validateAccount">Suivant</button>
        </div>
      </div>

      <!-- Step 1: Mosque -->
      <div v-show="step === 1" class="step active">
        <div class="form-section">
          <h2>Votre mosquée</h2>
          <p style="font-size: 0.8rem; color: var(--text-dark-muted); margin-bottom: 0.8rem">
            Rendez-vous sur <a href="https://mawaqit.net" target="_blank" class="link-action">mawaqit.net</a>,
            recherchez votre mosquée et copiez l'URL de sa page.
          </p>
          <div class="form-group">
            <label for="mosque_url">URL mawaqit.net</label>
            <div style="display: flex; gap: 0.5rem">
              <input
                id="mosque_url"
                v-model="data.mosque_url"
                type="url"
                placeholder="https://mawaqit.net/fr/m/votre-mosquee"
                required
                style="flex: 1"
              >
              <button type="button" class="btn btn-secondary" :disabled="validating" @click="validateUrl">
                <template v-if="validating">Vérification<span class="spinner"></span></template>
                <template v-else>Vérifier</template>
              </button>
            </div>
          </div>
          <div v-if="urlPreview" class="preview">
            <div class="preview-city">{{ urlPreview.city }}</div>
            <div class="preview-prayers">
              <div v-for="p in urlPreview.prayers" :key="p.name" class="preview-prayer">
                <span class="name">{{ p.name }}</span> <span class="time">{{ p.adhan }}</span>
              </div>
            </div>
          </div>
          <div v-if="urlError" class="msg msg-error">{{ urlError }}</div>
        </div>
        <div class="actions">
          <button type="button" class="btn btn-secondary" @click="goToStep(0)">Retour</button>
          <button type="button" class="btn btn-action" :disabled="!urlPreview" @click="goToStep(2)">Suivant</button>
        </div>
      </div>

      <!-- Step 2: Sound enabled? -->
      <div v-show="step === 2" class="step active">
        <div class="form-section">
          <h2>Alertes sonores</h2>
          <p style="font-size: 0.8rem; color: var(--text-dark-muted); margin-bottom: 0.8rem">
            Souhaitez-vous que l'adhan soit diffusé sur vos enceintes (HomePod, AirPlay, Sonos, Cast…) aux heures de prière ?
          </p>

          <div class="choice-cards">
            <div
              class="choice-card"
              :class="{ selected: data.sound_enabled === 'true' }"
              @click="selectSound(true)"
            >
              <div class="choice-icon">🔊</div>
              <div class="choice-label">Oui</div>
              <div class="choice-desc">Diffuser l'adhan sur mes enceintes</div>
            </div>
            <div
              class="choice-card"
              :class="{ selected: data.sound_enabled === 'false' && step === 2 }"
              @click="selectSound(false)"
            >
              <div class="choice-icon">🔇</div>
              <div class="choice-label">Non</div>
              <div class="choice-desc">Afficher les horaires uniquement</div>
            </div>
          </div>
        </div>

        <div class="actions" style="margin-top: 1.5rem">
          <button type="button" class="btn btn-secondary" @click="goToStep(1)">Retour</button>
          <button type="button" class="btn btn-action" :disabled="installing" @click="goToSoundNext">
            <template v-if="installing">Installation<span class="spinner"></span></template>
            <template v-else>{{ data.sound_enabled === 'true' ? 'Suivant' : 'Installer' }}</template>
          </button>
        </div>
      </div>

      <!-- Step 3: Audio provider — pick + confirm + start -->
      <div v-show="step === 3" class="step active">
        <div class="form-section">
          <h2>Diffusion audio</h2>
          <p
            v-if="!startingProvider"
            style="font-size: 0.8rem; color: var(--text-dark-muted); margin-bottom: 0.8rem"
          >
            Choisis le service qui pilotera tes enceintes. Tu pourras en changer plus tard.
          </p>

          <!-- Provider cards (transition: other fades out, picked one centers/grows) -->
          <transition-group name="picker" tag="div" class="provider-grid" :class="{ singled: !!startingProvider }">
            <div
              v-for="p in visibleProviders"
              :key="p.id"
              class="provider-card"
              :class="{ active: startingProvider === p.id }"
              @click="!startingProvider && pickProvider(p)"
            >
              <div class="provider-icon">{{ p.icon }}</div>
              <div class="provider-label">{{ p.label }}</div>
              <div class="provider-desc">{{ p.description }}</div>

              <div v-if="startingProvider === p.id" class="provider-progress">
                <div v-if="startState !== 'failed'" class="progress-row">
                  <span class="spinner big"></span>
                  <span>{{ startMessage || 'Démarrage…' }}</span>
                </div>
                <div v-else class="msg msg-error" style="margin-top: 0.6rem">
                  {{ startError }}
                  <button type="button" class="btn btn-secondary" style="margin-top: 0.6rem" @click="retryProvider">
                    Réessayer
                  </button>
                </div>
              </div>
            </div>
          </transition-group>
        </div>

        <div v-if="!startingProvider" class="actions" style="margin-top: 1.5rem">
          <button type="button" class="btn btn-secondary" @click="goToStep(2)">Retour</button>
          <span></span>
        </div>
      </div>

      <!-- Step 4: Done -->
      <div v-show="step === 4" class="step active">
        <div class="form-section">
          <h2>Installation terminée</h2>
          <div class="recap">
            <div class="recap-row">
              <span class="recap-label">Identifiant</span>
              <span class="recap-value">{{ data.username }}</span>
            </div>
            <div class="recap-row">
              <span class="recap-label">Mosquée</span>
              <span class="recap-value">{{ data.city }}</span>
            </div>
            <div class="recap-row">
              <span class="recap-label">Alertes sonores</span>
              <span class="recap-value">{{ data.sound_enabled === 'true' ? 'Activées' : 'Désactivées' }}</span>
            </div>
            <div v-if="data.sound_enabled === 'true' && activeProvider" class="recap-row">
              <span class="recap-label">{{ activeProvider.label }}</span>
              <span class="recap-value">Configuré</span>
            </div>
          </div>
          <p style="margin-top: 1.5rem; font-size: 0.85rem; color: var(--text-dark-muted)">
            Redirection vers le dashboard dans <span>{{ redirectSeconds }}</span> secondes...
          </p>
        </div>
        <div class="actions">
          <span></span>
          <RouterLink to="/dashboard" class="btn btn-action">Accéder au dashboard</RouterLink>
        </div>
      </div>

      <!-- Confirmation modal -->
      <div v-if="pendingProvider" class="modal-backdrop" @click.self="cancelPick">
        <div class="modal">
          <div class="modal-icon">{{ pendingProvider.icon }}</div>
          <h3>Démarrer {{ pendingProvider.label }} ?</h3>
          <p style="font-size: 0.85rem; color: var(--text-dark-muted); margin: 0.6rem 0 1rem">
            On va lancer le service automatiquement, ça peut prendre quelques secondes.
          </p>

          <ProviderFields
            v-if="pendingProvider.fields.length && pendingProvider.fields.some(f => !f.mode_visibility.length || f.mode_visibility.includes(data.audio.mode))"
            v-model="data.audio.config"
            :fields="pendingProvider.fields"
            :mode="data.audio.mode"
          />

          <div class="modal-actions" style="display: flex; gap: 0.8rem; justify-content: flex-end; margin-top: 1rem">
            <button type="button" class="btn btn-secondary" @click="cancelPick">Annuler</button>
            <button type="button" class="btn btn-action" @click="confirmPick">Démarrer</button>
          </div>
        </div>
      </div>
  </CardLayout>
</template>

<style scoped>
.step { display: none; }
.step.active { display: block; }

.steps-indicator {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 2rem;
}
.steps-indicator .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.12);
  transition: background 0.3s;
}
.steps-indicator .dot.active {
  background: var(--accent);
}

.choice-cards {
  display: flex;
  gap: 1rem;
  margin-top: 0.8rem;
}
.choice-card {
  flex: 1;
  padding: 1.2rem;
  border: 2px solid rgba(0, 0, 0, 0.08);
  border-radius: 10px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
}
.choice-card:hover { border-color: rgba(0, 0, 0, 0.15); }
.choice-card.selected {
  border-color: var(--accent);
  background: rgba(200, 169, 126, 0.06);
}
.choice-card .choice-icon { font-size: 2rem; margin-bottom: 0.5rem; }
.choice-card .choice-label { font-weight: 500; font-size: 0.9rem; }
.choice-card .choice-desc { font-size: 0.75rem; color: var(--text-dark-muted); margin-top: 0.3rem; }

.provider-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  margin-top: 0.8rem;
  transition: all 0.4s ease;
}
.provider-grid.singled {
  grid-template-columns: 1fr;
  justify-items: center;
}
.provider-card {
  padding: 1.6rem 1.2rem;
  border: 2px solid rgba(0, 0, 0, 0.08);
  border-radius: 12px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s ease;
  background: white;
  width: 100%;
  max-width: 360px;
}
.provider-card:hover { border-color: rgba(0, 0, 0, 0.15); transform: translateY(-2px); }
.provider-card.active {
  border-color: var(--accent);
  background: rgba(200, 169, 126, 0.08);
  cursor: default;
  transform: scale(1.02);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
}
.provider-card.active:hover { transform: scale(1.02); }
.provider-icon { font-size: 2.4rem; margin-bottom: 0.6rem; }
.provider-label { font-weight: 600; font-size: 1rem; }
.provider-desc { font-size: 0.78rem; color: var(--text-dark-muted); margin-top: 0.4rem; line-height: 1.4; }

.provider-progress {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
}
.progress-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.6rem;
  font-size: 0.85rem;
  color: var(--text-dark-muted);
}
.spinner.big {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(0, 0, 0, 0.12);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Vue transition-group for the provider cards */
.picker-leave-active {
  transition: all 0.4s ease;
  position: absolute;
}
.picker-leave-to {
  opacity: 0;
  transform: scale(0.8) translateY(20px);
}
.picker-move {
  transition: all 0.4s ease;
}

/* Modal */
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  animation: fadeIn 0.2s ease;
}
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
.modal {
  background: white;
  border-radius: 14px;
  padding: 1.8rem;
  width: 90%;
  max-width: 420px;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.25);
  animation: slideUp 0.25s ease;
}
@keyframes slideUp {
  from { transform: translateY(20px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}
.modal-icon { font-size: 2.4rem; text-align: center; }
.modal h3 { text-align: center; margin: 0.5rem 0 0; font-size: 1.1rem; }

.recap {
  background: #f0ede5;
  border-radius: 8px;
  padding: 1rem;
  font-size: 0.85rem;
}
.recap-row {
  display: flex;
  justify-content: space-between;
  padding: 0.3rem 0;
}
.recap-label { color: var(--text-dark-muted); }
.recap-value { font-weight: 500; }
</style>
