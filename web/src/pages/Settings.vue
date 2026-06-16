<script setup lang="ts">
import AdminLayout from '@/layouts/AdminLayout.vue'
import MosqueSection from '@/components/settings/MosqueSection.vue'
import AdvancedSection from '@/components/settings/AdvancedSection.vue'
import TokensSection from '@/components/settings/TokensSection.vue'
import UsersSection from '@/components/settings/UsersSection.vue'
import SoundSection from '@/components/settings/SoundSection.vue'
import PrayerOutputsSection from '@/components/settings/PrayerOutputsSection.vue'
import ProviderLinkSection from '@/components/settings/ProviderLinkSection.vue'
</script>

<template>
  <AdminLayout title="Paramètres" subtitle="Sauvegarde automatique">
    <div class="settings-content">
      <div class="settings-left">
        <MosqueSection />
        <AdvancedSection />
        <TokensSection />
        <UsersSection />
      </div>
      <div class="settings-right">
        <ProviderLinkSection />
        <SoundSection />
        <PrayerOutputsSection />
      </div>
    </div>
  </AdminLayout>
</template>
