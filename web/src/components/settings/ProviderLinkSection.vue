<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { api } from '@/api/client'
import type { ProviderManifest } from '@/types/audio'

// Default web-UI ports per provider, used when the stored config has none.
const DEFAULT_PORTS: Record<string, string> = {
  'music-assistant': '8095',
  owntone: '3689',
}

const provider = ref<string>('')
const config = ref<Record<string, string>>({})
const manifest = ref<ProviderManifest | null>(null)
const loaded = ref(false)

const label = computed(() => manifest.value?.label || provider.value)
const icon = computed(() => manifest.value?.icon || '🔊')

// The provider's web UI runs on the host (network_mode: host), so from the
// browser it lives at the same hostname we're served from — unless an external
// install pointed us at a real address. host.docker.internal is the api
// container's view of the host and means nothing to the browser, so we ignore it.
const url = computed(() => {
  const host = config.value.host
  const browserHost =
    host && !['host.docker.internal', 'localhost', '127.0.0.1', ''].includes(host)
      ? host
      : window.location.hostname
  const port = config.value.port || DEFAULT_PORTS[provider.value] || ''
  return port ? `http://${browserHost}:${port}` : `http://${browserHost}`
})

onMounted(async () => {
  try {
    const [cur, all] = await Promise.all([
      api<{ provider: string; mode: string; config: Record<string, string> }>('/audio/current'),
      api<{ providers: ProviderManifest[] }>('/audio/providers'),
    ])
    provider.value = cur.provider
    config.value = cur.config || {}
    manifest.value = all.providers.find((p) => p.id === cur.provider) || null
  } finally {
    loaded.value = true
  }
})
</script>

<template>
  <div v-if="loaded && provider" class="form-section">
    <h2>Diffusion audio</h2>
    <a :href="url" target="_blank" rel="noopener" class="provider-link">
      <span class="provider-link-icon">{{ icon }}</span>
      <span class="provider-link-text">
        <span class="provider-link-label">Ouvrir {{ label }}</span>
        <span class="provider-link-url">{{ url }}</span>
      </span>
      <span class="provider-link-arrow">↗</span>
    </a>
  </div>
</template>

<style scoped>
.provider-link {
  display: flex;
  align-items: center;
  gap: 0.9rem;
  padding: 0.9rem 1rem;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 10px;
  text-decoration: none;
  color: inherit;
  transition: all 0.2s;
}
.provider-link:hover {
  border-color: var(--accent);
  background: #faf8f3;
}
.provider-link-icon {
  font-size: 1.9rem;
  line-height: 1;
}
.provider-link-text {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
}
.provider-link-label {
  font-weight: 600;
}
.provider-link-url {
  font-size: 0.78rem;
  color: var(--text-dark-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.provider-link-arrow {
  font-size: 1.1rem;
  color: var(--text-dark-muted);
}
</style>
