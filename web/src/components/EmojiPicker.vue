<script setup lang="ts">
import { ref } from 'vue'

defineProps<{ modelValue: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

const open = ref(false)

const EMOJI_LIST = [
  '😀','😃','😄','😁','😆','😅','🤣','😂','🙂','😊',
  '😇','🥰','😍','🤩','😎','🤓','🧐','🤠','🥳','😏',
  '😺','🐶','🐱','🦁','🐯','🐻','🐼','🐸','🐵','🦊',
  '🦄','🐝','🦋','🐢','🐙','🦈','🐬','🦅','🦉','🐧',
  '🌟','⭐','🌙','☀️','🔥','💧','❄️','🌈','🍀','🌸',
  '🏀','⚽','🎯','🎮','🎸','🎨','📚','💻','🚀','✈️',
  '👨','👩','👦','👧','👶','🧔','👳','👲','🧕','👼',
]

function pick(e: string) {
  emit('update:modelValue', e)
  open.value = false
}
</script>

<template>
  <div>
    <button type="button" class="emoji-pick-btn" @click="open = !open">{{ modelValue }}</button>
    <div v-if="open" class="emoji-picker" style="display: grid">
      <button
        v-for="e in EMOJI_LIST"
        :key="e"
        type="button"
        class="emoji-option"
        @click="pick(e)"
      >{{ e }}</button>
    </div>
  </div>
</template>
