<template>
  <div class="stat-card">
    <h3>{{ title }}</h3>
    <div v-if="streaks && streaks.length" class="scrollable-content hide-scrollbar">
      <ul class="streak-list">
        <li v-for="(streak, index) in streaks" :key="streak.did" class="streak-item">
          <span class="rank">{{ index + 1 }}</span>
          <img :src="streak.avatar_url" class="avatar" @error="onAvatarError" />
          <div class="user-info">
            <span class="display-name">{{ streak.display_name || streak.handle }}</span>
            <span class="handle">@{{ streak.handle }}</span>
          </div>
          <span class="streak-count">{{ streak.longest_streak }} days</span>
        </li>
      </ul>
    </div>
    <div v-else class="no-data-message">
      <p>No streaks to display right now.</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { PropType } from 'vue'
import type { Streak } from '@/types/aggregates'

defineProps({
  title: {
    type: String,
    required: true,
  },
  streaks: {
    type: Array as PropType<Streak[]>,
    required: true,
  },
})

const onAvatarError = (event: Event) => {
  const target = event.target as HTMLImageElement
  target.src = new URL('@/assets/fema.jpg', import.meta.url).href
}
</script>

<style scoped>
.stat-card {
  background-color: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 1rem 1.5rem;
  display: flex;
  flex-direction: column;
  height: 100%;
}

h3 {
  font-size: 1.1rem;
  color: var(--text-primary);
  margin: 0 0 1rem 0;
  font-weight: 600;
}

.streak-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.streak-item {
  display: grid;
  grid-template-columns: 30px 40px 1fr auto;
  align-items: center;
  gap: 12px;
}

.rank { font-size: 0.9rem; font-weight: 600; color: var(--text-muted); text-align: center; }
.avatar { width: 40px; height: 40px; border-radius: 50%; object-fit: cover; background-color: var(--hover-bg); }
.user-info { display: flex; flex-direction: column; overflow: hidden; }
.display-name { font-weight: 600; color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.handle { color: var(--text-muted); font-size: 0.9rem; }
.streak-count { font-size: 0.9rem; font-weight: 500; color: var(--text-secondary); white-space: nowrap; }

.scrollable-content {
  flex: 1;
  overflow-y: auto;
}

.hide-scrollbar {
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.hide-scrollbar::-webkit-scrollbar {
  display: none;
}
</style>
