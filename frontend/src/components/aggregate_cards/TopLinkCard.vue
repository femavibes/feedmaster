<template>
  <div class="card top-link-card">
    <div class="card-header">
      <h3 class="card-title">Top Shared Links</h3>
    </div>
    <div class="card-body">
      <ul v-if="item.links && item.links.length" class="link-list">
        <li v-for="link in item.links" :key="link.uri" class="link-item">
          <a :href="link.uri" target="_blank" rel="noopener noreferrer" class="link-content">
            <img v-if="link.image" :src="link.image" alt="Thumbnail" class="thumbnail" @error="onImageError" />
            <div v-else class="thumbnail-placeholder">
              <i class="fas fa-link"></i>
            </div>
            <div class="link-details">
              <span class="link-title">{{ link.title || 'No Title Available' }}</span>
              <p class="link-description">{{ link.description || 'No description available.' }}</p>
              <span class="link-uri">{{ link.uri }}</span>
            </div>
          </a>
          <span class="link-count">{{ link.count }}</span>
        </li>
      </ul>
      <p v-else class="no-data">No link data available.</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { TopLinkCard } from '@/types/aggregates';

defineProps<{
  item: TopLinkCard;
}>();

const onImageError = (event: Event) => {
  const target = event.target as HTMLImageElement;
  target.style.display = 'none'; // Hide broken images
};
</script>

<style scoped>
.top-link-card {
  background-color: #2b2d31;
  border: 1px solid #404249;
  border-radius: 8px;
  color: #dcddde;
  font-family: 'Inter', sans-serif;
}

.card-header {
  padding: 1rem;
  border-bottom: 1px solid #404249;
}

.card-title {
  margin: 0;
  font-size: 1.2rem;
  font-weight: 600;
}

.card-body {
  padding: 1rem;
}

.link-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.link-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: #313338;
  border-radius: 8px;
  padding: 1rem;
  transition: background-color 0.2s;
}

.link-item:hover {
  background-color: #404249;
}

.link-content {
  display: flex;
  align-items: center;
  gap: 1rem;
  text-decoration: none;
  color: inherit;
  flex-grow: 1;
}

.thumbnail {
  width: 80px;
  height: 80px;
  object-fit: cover;
  border-radius: 8px;
  flex-shrink: 0;
}

.thumbnail-placeholder {
  width: 80px;
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #404249;
  border-radius: 8px;
  font-size: 2rem;
  color: #8a8e94;
  flex-shrink: 0;
}

.link-details {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  overflow: hidden;
}

.link-title {
  font-weight: 600;
  font-size: 1rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.link-description {
  font-size: 0.9rem;
  color: #8a8e94;
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.link-uri {
  font-size: 0.8rem;
  color: #5865f2;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.link-count {
  font-weight: bold;
  background-color: #404249;
  padding: 0.3rem 0.6rem;
  border-radius: 12px;
  font-size: 0.9rem;
  flex-shrink: 0;
  margin-left: 1rem;
}

.no-data {
  text-align: center;
  color: #8a8e94;
}
</style>
