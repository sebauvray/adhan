<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import SettingsHeader from '@/components/SettingsHeader.vue'

defineProps<{ title: string; subtitle: string }>()

onMounted(() => document.body.classList.add('settings-page'))
onUnmounted(() => document.body.classList.remove('settings-page'))
</script>

<template>
  <div class="settings">
    <SettingsHeader :title="title" :subtitle="subtitle" />
    <slot />
  </div>
</template>
