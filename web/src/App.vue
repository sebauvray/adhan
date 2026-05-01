<script setup lang="ts">
import { useIdleRedirect } from '@/composables/useIdleRedirect'
import ComboOverlay from '@/components/combo/ComboOverlay.vue'

useIdleRedirect()
</script>

<template>
  <RouterView />
  <ComboOverlay />
</template>

<style>
@import url('https://fonts.googleapis.com/css2?family=Bowlby+One+SC&family=Russo+One&display=swap');
</style>
