<script setup lang="ts">
defineProps<{ title?: string; subtitle?: string; logoSrc?: string }>()
</script>

<template>
  <div class="page">
    <div class="card">
      <img :src="logoSrc || '/logo.png'" alt="Adhan Home" class="logo">
      <h1 v-if="title">{{ title }}</h1>
      <p v-if="subtitle" class="subtitle">{{ subtitle }}</p>
      <slot />
    </div>
  </div>
</template>
