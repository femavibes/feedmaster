<template>
  <div class="stat-card">
    <div class="card-header-with-tabs">
      <div class="tab-selector">
        <button
          v-for="tab in tabs"
          :key="tab.value"
          :class="{ active: activeTab === tab.value }"
          @click="activeTab = tab.value"
        >
          {{ tab.label }}
        </button>
      </div>
    </div>

    <div class="scrollable-content hide-scrollbar">
      <!-- Top Videos Tab -->
      <div v-if="activeTab === 'videos'" class="media-grid">
        <div v-if="videos && videos.length">
          <div v-for="(video, index) in videos" :key="video.uri + index" class="media-item">
            <a :href="video.post_url" target="_blank" class="media-thumbnail">
              <img v-if="video.thumbnail_url" :src="proxyImageUrl(video.thumbnail_url)" alt="Video thumbnail" class="thumbnail-img" @error="onThumbnailError" />
              <div v-else class="placeholder-thumbnail">📹</div>
              <span class="media-count">{{ video.like_count.toLocaleString() }}</span>
            </a>
            <div class="media-info">
              <a :href="video.post_url" target="_blank" class="media-title">{{ video.text.slice(0, 50) }}{{ video.text.length > 50 ? '...' : '' }}</a>
              <span class="media-url">{{ video.author }}</span>
            </div>
          </div>
        </div>
        <div v-else class="no-data-message">
          <p>No video data to display right now.</p>
        </div>
      </div>

      <!-- Top Images Tab -->
      <div v-if="activeTab === 'images'" class="media-grid">
        <div v-if="images && images.length">
          <div v-for="(image, index) in images" :key="image.uri + index" class="media-item">
            <a :href="image.post_url" target="_blank" class="media-thumbnail">
              <img v-if="image.images && image.images[0] && image.images[0].url" :src="proxyImageUrl(image.images[0].url)" alt="Image" class="thumbnail-img" @error="onThumbnailError" />
              <div v-else class="placeholder-thumbnail">🖼️</div>
              <span class="media-count">{{ image.like_count.toLocaleString() }}</span>
            </a>
            <div class="media-info">
              <a :href="image.post_url" target="_blank" class="media-title">{{ image.text.slice(0, 50) }}{{ image.text.length > 50 ? '...' : '' }}</a>
              <span class="media-url">{{ image.author }}</span>
            </div>
          </div>
        </div>
        <div v-else class="no-data-message">
          <p>No image data to display right now.</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { PropType } from 'vue'
import { proxyImageUrl } from '@/utils/imageProxy'

interface PostCard {
  uri: string
  text: string
  author: string
  avatar: string
  post_url: string
  created_at: string
  like_count: number
  reply_count: number
  repost_count: number
  quote_count: number
  thumbnail_url?: string
  images?: any[]
}

defineProps({
  videos: {
    type: Array as PropType<PostCard[]>,
    required: true,
  },
  images: {
    type: Array as PropType<PostCard[]>,
    required: true,
  },
})

const activeTab = ref('images')

const tabs = [
  { value: 'images', label: 'Top Images' },
  { value: 'videos', label: 'Top Videos' },
]



const onThumbnailError = (event: Event) => {
  const target = event.target as HTMLImageElement
  target.style.display = 'none'
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
}

.card-header-with-tabs {
  margin-bottom: 1rem;
}

.tab-selector {
  display: flex;
  gap: 4px;
  background-color: var(--bg-tertiary);
  border-radius: 6px;
  padding: 4px;
}

.tab-selector button {
  background-color: transparent;
  border: none;
  color: var(--text-secondary);
  padding: 6px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.85rem;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.tab-selector button.active {
  background-color: var(--bg-secondary);
  color: var(--text-primary);
}

.tab-selector button:hover:not(.active) {
  background-color: var(--hover-bg);
}

.scrollable-content {
  flex: 1;
  overflow-y: auto;
  -ms-overflow-style: none;
  scrollbar-width: none;
}

.scrollable-content::-webkit-scrollbar {
  display: none;
}

.media-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}

.media-item {
  position: relative;
  border-radius: 8px;
  overflow: hidden;
  background-color: var(--bg-tertiary);
  border: 1px solid var(--border-color);
}

.media-thumbnail {
  display: block;
  text-decoration: none;
  position: relative;
  width: 100%;
  height: 160px;
  overflow: hidden;
}

.thumbnail-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.placeholder-thumbnail {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 2rem;
  color: var(--text-muted);
  background-color: var(--hover-bg);
}

.media-count {
  position: absolute;
  bottom: 4px;
  right: 4px;
  background-color: var(--bg-secondary);
  color: var(--text-secondary);
  padding: 4px 6px;
  border-radius: 3px;
  font-size: 0.75rem;
  font-weight: 500;
  border: 1px solid var(--border-color);
}

.media-info {
  padding: 8px;
  margin-left: 0;
}

.media-title {
  font-weight: 600;
  color: var(--text-primary);
  font-size: 0.85rem;
  line-height: 1.2;
  margin-bottom: 4px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-decoration: none;
}

.media-title:hover {
  color: #5865f2;
}

.media-url {
  color: var(--text-muted);
  font-size: 0.75rem;
}

.no-data-message {
  text-align: center;
  padding: 2rem;
  color: var(--text-muted);
}
</style>