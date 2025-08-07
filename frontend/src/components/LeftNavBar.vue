<template>
  <nav class="left-nav-bar">
    <div v-if="feedStore.feedsLoading" class="loading-spinner" title="Loading feeds..."></div>
    <div v-else-if="feedStore.feedsError" class="error-state" :title="feedStore.feedsError">!</div>
    <div v-else class="nav-group">
      <button
        v-for="feed in feedStore.availableFeeds"
        :key="feed.id"
        class="nav-button"
        :class="{ 'is-active': feed.id === feedStore.selectedFeedId }"
        @click="selectFeed(feed.id)"
        :title="feed.name"
      >
        <img v-if="feed.avatar_url" :src="feed.avatar_url" :alt="feed.name" class="feed-avatar" />
        <span v-else class="feed-letter">{{ feed.name[0]?.toUpperCase() }}</span>
      </button>
    </div>
    <button class="nav-button settings-button" @click="openSettings" title="Settings">
      <span class="settings-icon">⚙</span>
    </button>
    
    <SettingsModal :isVisible="showSettingsModal" @close="closeSettings" />
  </nav>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useFeedStore } from '@/stores/useFeedStore'
import SettingsModal from './SettingsModal.vue'

const router = useRouter()
const feedStore = useFeedStore()
const showSettingsModal = ref(false)

const selectFeed = (feedId: string) => {
  feedStore.selectFeed(feedId)
  router.push(`/feed/${feedId}`)
}

const openSettings = () => {
  showSettingsModal.value = true
}

const closeSettings = () => {
  showSettingsModal.value = false
}
</script>

<style scoped>
.left-nav-bar {
  grid-area: nav;
  background-color: #313338;
  padding: 16px 8px;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: space-between;
}

.nav-group {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.nav-button {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background-color: transparent;
  color: #fff;
  font-size: 1.5rem;
  font-weight: bold;
  border: none;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
}

.nav-button::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.1) 0%, rgba(255, 255, 255, 0.05) 100%);
  opacity: 0;
  transition: opacity 0.3s ease;
}

.nav-button:hover::before {
  opacity: 1;
}

.nav-button.is-active {
  transform: scale(1.1);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.5), 0 4px 16px rgba(59, 130, 246, 0.3);
}

.loading-spinner {
  border: 4px solid #404249;
  border-top: 4px solid #5865f2;
  border-radius: 50%;
  width: 24px;
  height: 24px;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.error-state {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background-color: #da373c;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.5rem;
  font-weight: bold;
}

.feed-avatar {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  object-fit: cover;
  z-index: 1;
  position: relative;
}

.feed-letter {
  font-size: 1.5rem;
  font-weight: bold;
  z-index: 1;
  position: relative;
}

.settings-button {
  margin-top: auto;
  background-color: #404249;
  border: 2px solid #5a5d66;
}

.settings-button:hover {
  background-color: #4a4d54;
  border-color: #6a6d76;
}

.settings-icon {
  font-size: 1.5rem;
  color: #dcddde;
  z-index: 1;
  position: relative;
}
</style>
