<script setup lang="ts">
import { reactive, onMounted } from 'vue'
import { api } from '@/api/client'
import { saveConfigField } from '@/api/config'
import { useFlashSaved } from '@/composables/useFlashSaved'

const cfg = reactive({
  log_level: 'INFO',
  owntone_host: 'host.docker.internal',
  owntone_port: '3689',
  quiet_start: '21:00',
  quiet_end: '07:00',
  quiet_volume: '10',
})

const { saved, flash } = useFlashSaved()

onMounted(async () => {
  const data = await api<typeof cfg>('/config')
  Object.assign(cfg, data)
})

async function save(field: keyof typeof cfg, table: string, key: string) {
  await saveConfigField(table, key, String(cfg[field]))
  flash(field)
}
</script>

<template>
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
          <span class="save-indicator" :class="{ visible: saved.has('log_level') }">Sauvegardé</span>
          <select
            id="log_level"
            v-model="cfg.log_level"
            :class="{ saved: saved.has('log_level') }"
            @change="save('log_level', 'config', 'LOG_LEVEL')"
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
          <span class="save-indicator" :class="{ visible: saved.has('owntone_host') }">Sauvegardé</span>
          <input
            id="owntone_host"
            v-model="cfg.owntone_host"
            type="text"
            :class="{ saved: saved.has('owntone_host') }"
            @blur="save('owntone_host', 'owntone', 'HOST')"
          >
        </div>
        <div class="form-group">
          <label for="owntone_port">OwnTone port</label>
          <span class="save-indicator" :class="{ visible: saved.has('owntone_port') }">Sauvegardé</span>
          <input
            id="owntone_port"
            v-model="cfg.owntone_port"
            type="text"
            :class="{ saved: saved.has('owntone_port') }"
            @blur="save('owntone_port', 'owntone', 'PORT')"
          >
        </div>
      </div>
      <div class="form-row" style="margin-top: 0.5rem">
        <div class="form-group">
          <label for="quiet_start">Heures calmes — début</label>
          <span class="save-indicator" :class="{ visible: saved.has('quiet_start') }">Sauvegardé</span>
          <input
            id="quiet_start"
            v-model="cfg.quiet_start"
            type="time"
            :class="{ saved: saved.has('quiet_start') }"
            @blur="save('quiet_start', 'config', 'QUIET_START')"
          >
        </div>
        <div class="form-group">
          <label for="quiet_end">Heures calmes — fin</label>
          <span class="save-indicator" :class="{ visible: saved.has('quiet_end') }">Sauvegardé</span>
          <input
            id="quiet_end"
            v-model="cfg.quiet_end"
            type="time"
            :class="{ saved: saved.has('quiet_end') }"
            @blur="save('quiet_end', 'config', 'QUIET_END')"
          >
        </div>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label for="quiet_volume">Volume max (heures calmes)</label>
          <span class="save-indicator" :class="{ visible: saved.has('quiet_volume') }">Sauvegardé</span>
          <input
            id="quiet_volume"
            v-model="cfg.quiet_volume"
            type="number"
            min="0"
            max="100"
            :class="{ saved: saved.has('quiet_volume') }"
            @blur="save('quiet_volume', 'config', 'QUIET_VOLUME')"
          >
        </div>
      </div>
    </div>
  </details>
</template>
