<script setup lang="ts">
import { ref } from 'vue'

defineProps<{
  id: string
  autocomplete?: string
  minlength?: number
  required?: boolean
}>()

const model = defineModel<string>({ required: true })
const visible = ref(false)
</script>

<template>
  <div class="password-input">
    <input
      :id="id"
      v-model="model"
      :type="visible ? 'text' : 'password'"
      :autocomplete="autocomplete"
      :minlength="minlength"
      :required="required"
    >
    <button
      type="button"
      class="password-toggle"
      :aria-label="visible ? 'Masquer le mot de passe' : 'Afficher le mot de passe'"
      :aria-pressed="visible"
      @click="visible = !visible"
    >
      <!-- heroicons: eye -->
      <svg v-if="!visible" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path stroke-linecap="round" stroke-linejoin="round" d="M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178Z" />
        <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
      </svg>
      <!-- heroicons: eye-slash -->
      <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path stroke-linecap="round" stroke-linejoin="round" d="M3.98 8.223A10.477 10.477 0 0 0 1.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.451 10.451 0 0 1 12 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 0 1-4.293 5.774M6.228 6.228 3 3m3.228 3.228 3.65 3.65m7.894 7.894L21 21m-3.228-3.228-3.65-3.65m0 0a3 3 0 1 0-4.243-4.243m4.242 4.242L9.88 9.88" />
      </svg>
    </button>
  </div>
</template>

<style scoped>
.password-input {
  position: relative;
}

.password-input input {
  width: 100%;
  padding-right: 2.6rem;
}

.password-toggle {
  position: absolute;
  top: 50%;
  right: 0.5rem;
  transform: translateY(-50%);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.25rem;
  border: none;
  background: none;
  color: var(--text-dark-muted);
  cursor: pointer;
  transition: color 0.2s;
}

.password-toggle:hover {
  color: var(--accent);
}
</style>
