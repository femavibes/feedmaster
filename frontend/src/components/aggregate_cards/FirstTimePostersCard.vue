<template>
  <div class="stat-card">
    <h3>First-Time Posters</h3>
    <div class="scrollable-content hide-scrollbar">
      <div v-if="firstTimePosters && firstTimePosters.length">
        <div v-for="poster in firstTimePosters" :key="poster.did" class="poster-item clickable" @click="openUserModal(poster)">
          <img :src="poster.avatar_url" class="avatar" @error="onAvatarError" />
          <div class="poster-info">
            <span class="display-name">{{ poster.display_name || poster.handle }}</span>
            <span class="handle">@{{ poster.handle }}</span>
            <span v-if="poster.first_post_at" class="timestamp">{{ formatTimestamp(poster.first_post_at) }}</span>
          </div>
        </div>
      </div>
      <div v-else class="no-data-message">
        <p>No first-time posters to display right now.</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { PropType } from 'vue'

interface FirstTimePoster {
  did: string
  handle: string
  display_name?: string
  avatar_url: string
  first_post_at?: string
}

defineProps({
  firstTimePosters: {
    type: Array as PropType<FirstTimePoster[]>,
    required: true,
  },
})

const emit = defineEmits<{
  openUserModal: [user: any]
}>()

const openUserModal = (user: any) => {
  emit('openUserModal', user)
}

const onAvatarError = (event: Event) => {
  const target = event.target as HTMLImageElement
  target.src = new URL('@/assets/fema.jpg', import.meta.url).href
}

const formatTimestamp = (timestamp: string) => {
  const date = new Date(timestamp)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
  const diffDays = Math.floor(diffHours / 24)
  
  if (diffHours < 1) {
    const diffMins = Math.floor(diffMs / (1000 * 60))
    return `${diffMins}m ago`
  } else if (diffHours < 24) {
    return `${diffHours}h ago`
  } else if (diffDays < 7) {
    return `${diffDays}d ago`
  } else {
    return date.toLocaleDateString()
  }
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
  height: 100%;
}

h3 {
  font-size: 1.1rem;
  color: #e2e8f0;
  margin: 0 0 1rem 0;
  font-weight: 600;
}

.scrollable-content {
  flex: 1;
  overflow-y: auto;
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.scrollable-content::-webkit-scrollbar {
  display: none;
}

.poster-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid #313338;
}

.poster-item.clickable {
  cursor: pointer;
  transition: all 0.2s ease;
  border-radius: 6px;
  padding: 8px;
  margin: 0 -8px;
}

.poster-item.clickable:hover {
  background-color: #404249;
  transform: translateY(-1px);
}

.poster-item:last-child {
  border-bottom: none;
}

.avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  object-fit: cover;
  background-color: #3c3e44;
}

.poster-info {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.display-name {
  font-weight: 600;
  color: #fff;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.handle {
  color: #949ba4;
  font-size: 0.9rem;
}

.timestamp {
  color: #72767d;
  font-size: 0.8rem;
  font-style: italic;
}

.no-data-message {
  text-align: center;
  padding: 2rem;
  color: #949ba4;
}
</style>