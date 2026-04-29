<script setup lang="ts">
import { ref } from 'vue'
import AdminLayout from '@/layouts/AdminLayout.vue'
import LeaderboardSection from '@/components/stats/LeaderboardSection.vue'
import HeatmapSection from '@/components/stats/HeatmapSection.vue'

interface User { id: number; name: string; emoji: string }

// The leaderboard fetch returns the canonical user list — feed it to the heatmap
// so its <select> stays in sync (no second /api/users round-trip).
const users = ref<User[]>([])
function onUsers(list: User[]) {
  users.value = list
}
</script>

<template>
  <AdminLayout title="Statistiques" subtitle="Suivi des prières">
    <div class="settings-content">
      <div class="settings-left">
        <LeaderboardSection @users="onUsers" />
      </div>
      <div class="settings-right">
        <HeatmapSection :users="users" />
      </div>
    </div>
  </AdminLayout>
</template>
