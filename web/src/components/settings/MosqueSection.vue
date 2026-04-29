<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/api/client'
import { saveConfigField } from '@/api/config'
import { useFlashSaved } from '@/composables/useFlashSaved'

const url = ref('')
const { saved, flash } = useFlashSaved()

onMounted(async () => {
  const data = await api<{ mosque_url: string }>('/config')
  url.value = data.mosque_url || ''
})

let original = ''
function rememberOriginal() {
  original = url.value
}

async function save() {
  if (url.value === original) return
  await saveConfigField('config', 'MOSQUE_URL', url.value)
  flash('mosque_url')
}
</script>

<template>
  <div class="form-section">
    <h2>Mosquée</h2>
    <div class="form-group">
      <label for="mosque_url">URL mawaqit.net</label>
      <span class="save-indicator" :class="{ visible: saved.has('mosque_url') }">Sauvegardé</span>
      <input
        id="mosque_url"
        v-model="url"
        type="url"
        :class="{ saved: saved.has('mosque_url') }"
        @focus="rememberOriginal"
        @blur="save"
      >
    </div>
  </div>
</template>
