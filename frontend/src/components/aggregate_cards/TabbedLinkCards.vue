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
      <!-- Top News Links Tab -->
      <div v-if="activeTab === 'news'" class="links-grid">
        <div v-if="newsLinks && newsLinks.length">
          <a v-for="(link, index) in newsLinks" :key="link.url + index" :href="link.url" target="_blank" rel="noopener noreferrer" class="link-card-item">
            <div class="link-card-thumbnail">
              <img v-if="link.image" :src="link.image" alt="Thumbnail" class="thumbnail-img" @error="onThumbnailError" />
              <div v-else class="placeholder-thumbnail">🔗</div>
              <span class="link-card-count">{{ link.count.toLocaleString() }}</span>
            </div>
            <div class="link-card-content">
              <div class="link-card-header">
                <img :src="getFavicon(link.url)" class="favicon" @error="onFaviconError" />
                <span class="link-card-title">{{ link.title || getHostname(link.url) || 'No title available' }}</span>
              </div>
              <p v-if="link.description" class="link-card-description">{{ link.description }}</p>
              <div class="link-card-footer">
                <span class="link-card-url">{{ getHostname(link.url) }}</span>
              </div>
            </div>
          </a>
        </div>
        <div v-else class="no-data-message">
          <p>No top news links to display right now.</p>
        </div>
      </div>

      <!-- Top Link Cards Tab -->
      <div v-if="activeTab === 'cards'" class="links-grid">
        <div v-if="linkCards && linkCards.length">
          <a v-for="(link, index) in linkCards" :key="link.url + index" :href="link.url" target="_blank" rel="noopener noreferrer" class="link-card-item">
            <div class="link-card-thumbnail">
              <img v-if="link.image" :src="link.image" alt="Thumbnail" class="thumbnail-img" @error="onThumbnailError" />
              <div v-else class="placeholder-thumbnail">🔗</div>
              <span class="link-card-count">{{ link.count.toLocaleString() }}</span>
            </div>
            <div class="link-card-content">
              <div class="link-card-header">
                <img :src="getFavicon(link.url)" class="favicon" @error="onFaviconError" />
                <span class="link-card-title">{{ link.title || getHostname(link.url) || 'No title available' }}</span>
              </div>
              <p v-if="link.description" class="link-card-description">{{ link.description }}</p>
              <div class="link-card-footer">
                <span class="link-card-url">{{ getHostname(link.url) }}</span>
              </div>
            </div>
          </a>
        </div>
        <div v-else class="no-data-message">
          <p>No top links to display right now.</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { PropType } from 'vue'

interface LinkCard {
  uri: string
  url: string
  title: string
  description: string
  image?: string
  count: number
}

defineProps({
  newsLinks: {
    type: Array as PropType<LinkCard[]>,
    required: true,
  },
  linkCards: {
    type: Array as PropType<LinkCard[]>,
    required: true,
  },
})

const activeTab = ref('news')

const tabs = [
  { value: 'news', label: 'Top News Links' },
  { value: 'cards', label: 'Top Link Cards' },
]

const getHostname = (url: string): string => {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch (e) {
    return url
  }
}

const getFavicon = (url: string): string => {
  try {
    const hostname = new URL(url).hostname
    return `https://www.google.com/s2/favicons?domain=${hostname}&sz=32`
  } catch (e) {
    return 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'
  }
}

const onFaviconError = (event: Event) => {
  const target = event.target as HTMLImageElement
  target.src = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiM5NDliYTQiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj48cGF0aCBkPSJNMTggMTNoNXY1YTIgMiAwIDAgMS0yIDJINVMyIDIgMCAwIDEgMi0yVjhoNSIvPjxwYXRoIGQ9Im0xNiA4LTYtNi02IDYiLz48cGF0aCBkPSJNMTIgMjd2MyIvPjwvc3ZnPg=='
}

const onThumbnailError = (event: Event) => {
  const target = event.target as HTMLImageElement
  target.style.display = 'none'
}
</script>

<style scoped>
.stat-card {
  background-color: #2b2d31;
  border: 1px solid #404249;
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
  background-color: #404249;
  border-radius: 6px;
  padding: 4px;
}

.tab-selector button {
  background-color: transparent;
  border: none;
  color: #b5bac1;
  padding: 6px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.85rem;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.tab-selector button.active {
  background-color: #2b2d31;
  color: #fff;
}

.tab-selector button:hover:not(.active) {
  background-color: #3c3e44;
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

.links-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
}

.link-card-item {
  display: flex;
  flex-direction: column;
  background-color: #404249;
  border: 1px solid #5a5d66;
  border-radius: 8px;
  overflow: hidden;
  text-decoration: none;
  transition: background-color 0.2s ease;
}

.link-card-item:hover {
  background-color: #3c3e44;
}

.link-card-thumbnail {
  width: 100%;
  height: 160px;
  position: relative;
  overflow: hidden;
}

.thumbnail-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.link-card-content {
  padding: 8px;
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
}

.link-card-header {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 8px;
}

.favicon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  margin-top: 2px;
}

.link-card-title {
  font-weight: 600;
  color: #e2e8f0;
  font-size: 0.9rem;
  line-height: 1.3;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.link-card-description {
  color: #b5bac1;
  font-size: 0.8rem;
  line-height: 1.4;
  margin: 0 0 8px 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.link-card-footer {
  margin-top: auto;
}

.link-card-url {
  color: #949ba4;
  font-size: 0.75rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.link-card-count {
  position: absolute;
  bottom: 4px;
  right: 4px;
  background-color: #2b2d31;
  color: #b5bac1;
  padding: 4px 6px;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 500;
  border: 1px solid #404249;
  white-space: nowrap;
}

.no-data-message {
  text-align: center;
  padding: 2rem;
  color: #949ba4;
}

.placeholder-thumbnail {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 2rem;
  color: #949ba4;
  background-color: #3c3e44;
}
</style>