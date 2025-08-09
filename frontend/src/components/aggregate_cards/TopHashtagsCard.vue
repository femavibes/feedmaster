<template>
  <div class="card top-hashtags-card">
    <div class="card-header">
      <h3 class="card-title">Top Hashtags</h3>
    </div>
    <div class="card-body">
      <ul v-if="hashtags && hashtags.length" class="hashtag-list">
        <li v-for="hashtag in hashtags" :key="hashtag.hashtag" class="hashtag-item clickable" @click="openHashtagModal(hashtag.hashtag)">
          <span class="hashtag-name">#{{ hashtag.hashtag }}</span>
          <span class="hashtag-count">{{ hashtag.count }}</span>
        </li>
      </ul>
      <p v-else class="no-data">No hashtag data available.</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { TopHashtag } from '@/types/aggregates';

defineProps<{
  hashtags: any[];
}>();

const emit = defineEmits<{
  openHashtagModal: [hashtag: string]
}>()

const openHashtagModal = (hashtag: string) => {
  emit('openHashtagModal', hashtag)
}
</script>

<style scoped>
.top-hashtags-card {
  background-color: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  color: var(--text-primary);
  font-family: 'Inter', sans-serif;
}

.card-header {
  padding: 1rem;
  border-bottom: 1px solid var(--border-color);
}

.card-title {
  margin: 0;
  font-size: 1.2rem;
  font-weight: 600;
}

.card-body {
  padding: 1rem;
}

.hashtag-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.hashtag-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem;
  border-bottom: 1px solid var(--bg-secondary);
  background-color: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  margin-bottom: 8px;
}

.hashtag-item.clickable {
  cursor: pointer;
  transition: all 0.2s ease;
}

.hashtag-item.clickable:hover {
  background-color: var(--hover-bg);
  border-color: var(--border-color);
  transform: translateY(-1px);
}

.hashtag-item:last-child {
  margin-bottom: 0;
}

.hashtag-name {
  font-weight: 500;
  color: var(--text-primary);
}

.hashtag-count {
  font-weight: 500;
  background-color: var(--bg-secondary);
  color: var(--text-secondary);
  padding: 4px 6px;
  border-radius: 4px;
  font-size: 0.75rem;
  border: 1px solid var(--border-color);
}

.no-data {
  text-align: center;
  color: var(--text-muted);
}
</style>
