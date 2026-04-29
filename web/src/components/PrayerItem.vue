<script setup lang="ts">
defineProps<{
  name: string
  adhan: string
  iqama: string
  status?: 'past' | 'current' | 'upcoming'
  badge?: string
}>()
</script>

<template>
  <div :class="['prayer-item', status]">
    <span class="prayer-name">{{ name }}</span>
    <span class="prayer-time">{{ adhan }}</span>
    <span class="prayer-iqama">
      <svg class="iqm-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
        <circle cx="9" cy="7" r="4"/>
        <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
        <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
      </svg>
      {{ iqama }}
    </span>
    <span v-if="badge" class="prayer-badge">{{ badge }}</span>
  </div>
</template>
