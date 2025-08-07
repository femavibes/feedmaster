<template>
  <div class="stat-card">
    <h3>Top Link Cards</h3>
    <div v-if="links && links.length" class="scrollable-content hide-scrollbar">
      <div class="links-grid">
        <a v-for="(link, index) in links" :key="link.url + index" :href="link.url" target="_blank" rel="noopener noreferrer" class="link-card-item">
          <div class="link-card-thumbnail">
            <img v-if="link.image" :src="link.image" alt="Thumbnail" class="thumbnail-img" @error="onThumbnailError" />
            <div v-else class="placeholder-thumbnail">🔗</div>
            <span class="link-card-count">{{ link.count.toLocaleString() }}</span>
          </div>
          <div class="link-card-content">
            <div class="link-card-header">
              <img :src="getFavicon(link.url)" class="favicon" @error="onFaviconError" />
              <span class="link-card-title">{{ link.title || getHostname(link.uri) || 'No title available' }}</span>
            </div>
            <p class="link-card-description" v-if="link.description">{{ link.description }}</p>
            <div class="link-card-footer">
              <span class="link-card-url">{{ getHostname(link.url) }}</span>
            </div>
          </div>
        </a>
      </div>
    </div>
    <div v-else class="no-data-message">
      <p>No top links to display right now.</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { PropType } from 'vue'

interface TopLink {
  url: string
  title?: string
  description?: string
  count: number
  image?: string
}

defineProps({
  links: {
    type: Array as PropType<TopLink[]>,
    required: true,
  },
})

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
    // Use a public service to get favicons. This is more reliable than trying to guess the path.
    return `https://www.google.com/s2/favicons?domain=${hostname}&sz=32`
  } catch (e) {
    // Return a transparent pixel as a fallback if the URL is invalid
    return 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'
  }
}

const onFaviconError = (event: Event) => {
  const target = event.target as HTMLImageElement
  // Fallback to a generic link icon if the favicon fails to load
  target.src = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiM5NDliYTQiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj48cGF0aCBkPSJNMTggMTNoNXY1YTIgMiAwIDAgMS0yIDJINVMyIDIgMCAwIDEgMi0yVjhoNSIvPjxwYXRoIGQ9bTE2IDgtNi02LTYgNiIvPjxwYXRoIGQ9Ik0xMiAyN3YzIi8+PC9zdmc+;'
}

const onThumbnailError = (event: Event) => {
  const target = event.target as HTMLImageElement
  target.style.display = 'none'; // Hide the broken thumbnail image
}
</script>

<style scoped>
.stat-card {
  background-color: #2b2d31;
  border: 1px solid #404249;
  border-radius: 8px;
  padding: 1rem 1.5rem;
  grid-column: span 4; /* Widened by 2 units */
  grid-row: span 12;
  display: flex;
  flex-direction: column;
}

.scrollable-content {
  flex-grow: 1;
  overflow-y: auto;
  -ms-overflow-style: none; /* IE and Edge */
  scrollbar-width: none; /* Firefox */
}

.scrollable-content::-webkit-scrollbar {
  display: none; /* Chrome, Safari, Opera*/
}

.no-data-message {
  flex-grow: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #949ba4;
  font-style: italic;
}

h3 {
  font-size: 1.1rem;
  color: #e2e8f0;
  margin: 0 0 1rem 0;
  font-weight: 600;
}

.links-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}

.link-card-item {
  display: flex;
  flex-direction: column;
  background-color: #404249;
  border: 1px solid #5a5d66;
  border-radius: 8px;
  text-decoration: none;
  color: inherit;
  transition: background-color 0.2s ease;
  overflow: hidden;
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
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.favicon {
  width: 16px;
  height: 16px;
  border-radius: 2px;
  flex-shrink: 0;
}

.link-card-title {
  font-weight: 500;
  color: #e2e8f0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex-grow: 1;
}

.link-card-description {
  font-size: 0.85rem;
  color: #b5bac1;
  display: -webkit-box;
  -webkit-line-clamp: 2; /* Show up to 2 lines of description */
  -webkit-box-orient: vertical;
  overflow: hidden;
  margin-bottom: 8px;
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