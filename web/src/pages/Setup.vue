<script setup lang="ts">
import { ref, reactive, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api/client'
import EmojiPicker from '@/components/EmojiPicker.vue'

const router = useRouter()

const step = ref(0)
const accountError = ref('')
const passwordConfirm = ref('')
const validating = ref(false)
const installing = ref(false)
const urlPreview = ref<{ city: string; prayers: { name: string; adhan: string }[] } | null>(null)
const urlError = ref('')

const data = reactive({
  username: '',
  password: '',
  emoji: '🙂',
  mosque_url: '',
  sound_enabled: 'false' as 'true' | 'false',
  owntone_mode: 'local' as 'local' | 'external',
  owntone_host: 'host.docker.internal',
  owntone_port: '3689',
  city: '',
})

const redirectSeconds = ref(5)
let redirectInterval: ReturnType<typeof setInterval> | null = null

onUnmounted(() => {
  if (redirectInterval) clearInterval(redirectInterval)
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

function goToSoundNext() {
  if (data.sound_enabled === 'true') goToStep(3)
  else finishSetup()
}

function selectOwntoneMode(mode: 'local' | 'external') {
  data.owntone_mode = mode
}

async function finishSetup() {
  installing.value = true
  if (data.owntone_mode === 'external') {
    data.owntone_host = data.owntone_host.trim() || 'host.docker.internal'
    data.owntone_port = data.owntone_port.trim() || '3689'
  }
  try {
    await api<{ success: boolean }>('/setup', {
      method: 'POST',
      body: JSON.stringify({ ...data }),
    })
    goToStep(4)
    redirectSeconds.value = 5
    redirectInterval = setInterval(() => {
      redirectSeconds.value -= 1
      if (redirectSeconds.value <= 0) {
        if (redirectInterval) clearInterval(redirectInterval)
        router.push('/dashboard')
      }
    }, 1000)
  } catch (e) {
    alert((e as Error).message || "Erreur d'installation")
    installing.value = false
  }
}
</script>

<template>
  <div class="page">
    <div class="card">
      <img src="/logo.png" alt="Adhan Home" class="logo">
      <h1>Adhan Home</h1>
      <p class="subtitle">Installation en quelques étapes</p>

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

      <!-- Step 2: Sound -->
      <div v-show="step === 2" class="step active">
        <div class="form-section">
          <h2>Alertes sonores</h2>
          <p style="font-size: 0.8rem; color: var(--text-dark-muted); margin-bottom: 0.8rem">
            Souhaitez-vous que l'adhan soit diffusé sur vos enceintes (HomePod, AirPlay) aux heures de prière ?
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

          <p
            v-if="data.sound_enabled === 'true'"
            style="font-size: 0.75rem; color: var(--text-dark-muted); margin-top: 0.8rem"
          >
            Vous pourrez personnaliser les enceintes et le fichier audio dans les paramètres.
          </p>
        </div>

        <div class="actions" style="margin-top: 1.5rem">
          <button type="button" class="btn btn-secondary" @click="goToStep(1)">Retour</button>
          <button type="button" class="btn btn-action" :disabled="installing" @click="goToSoundNext">
            <template v-if="installing && data.sound_enabled === 'false'">Installation<span class="spinner"></span></template>
            <template v-else>{{ data.sound_enabled === 'true' ? 'Suivant' : 'Installer' }}</template>
          </button>
        </div>
      </div>

      <!-- Step 3: OwnTone install mode -->
      <div v-show="step === 3" class="step active">
        <div class="form-section">
          <h2>Diffusion audio</h2>
          <p style="font-size: 0.8rem; color: var(--text-dark-muted); margin-bottom: 0.8rem">
            Comment souhaites-tu jouer l'adhan sur tes enceintes ?
          </p>

          <div class="choice-cards">
            <div
              class="choice-card"
              :class="{ selected: data.owntone_mode === 'local' }"
              @click="selectOwntoneMode('local')"
            >
              <div class="choice-icon">🚀</div>
              <div class="choice-label">Installation simple</div>
              <div class="choice-desc">On installe OwnTone pour toi (recommandé)</div>
            </div>
            <div
              class="choice-card"
              :class="{ selected: data.owntone_mode === 'external' }"
              @click="selectOwntoneMode('external')"
            >
              <div class="choice-icon">⚙️</div>
              <div class="choice-label">J'ai déjà OwnTone</div>
              <div class="choice-desc">Je connecte à mon serveur existant</div>
            </div>
          </div>

          <div v-if="data.owntone_mode === 'external'" style="margin-top: 1rem">
            <div class="form-group">
              <label for="setup_owntone_host">Adresse OwnTone</label>
              <input
                id="setup_owntone_host"
                v-model="data.owntone_host"
                type="text"
                placeholder="host.docker.internal"
              >
            </div>
            <div class="form-group" style="margin-top: 0.6rem">
              <label for="setup_owntone_port">Port</label>
              <input
                id="setup_owntone_port"
                v-model="data.owntone_port"
                type="text"
                placeholder="3689"
                style="max-width: 8rem"
              >
            </div>
          </div>
        </div>

        <div class="actions" style="margin-top: 1.5rem">
          <button type="button" class="btn btn-secondary" @click="goToStep(2)">Retour</button>
          <button type="button" class="btn btn-action" :disabled="installing" @click="finishSetup">
            <template v-if="installing">Installation<span class="spinner"></span></template>
            <template v-else>Installer</template>
          </button>
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
            <div v-if="data.sound_enabled === 'true'" class="recap-row">
              <span class="recap-label">OwnTone</span>
              <span class="recap-value">
                {{ data.owntone_mode === 'local'
                  ? 'Installation simple'
                  : `Externe (${data.owntone_host}:${data.owntone_port})` }}
              </span>
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
    </div>
  </div>
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
