<script setup lang="ts">
import { useIdleRedirect } from '@/composables/useIdleRedirect'

useIdleRedirect()
</script>

<template>
  <RouterView />
</template>
