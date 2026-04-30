<script setup lang="ts">
import type { ProviderManifest } from '@/types/audio'

defineProps<{
  modelValue: string
  providers: ProviderManifest[]
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

function select(id: string) {
  emit('update:modelValue', id)
}
</script>

<template>
  <div class="choice-cards">
    <div
      v-for="p in providers"
      :key="p.id"
      class="choice-card"
      :class="{ selected: modelValue === p.id }"
      @click="select(p.id)"
    >
      <div class="choice-icon">{{ p.icon }}</div>
      <div class="choice-label">{{ p.label }}</div>
      <div class="choice-desc">{{ p.description }}</div>
    </div>
  </div>
</template>

<style scoped>
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
</style>
