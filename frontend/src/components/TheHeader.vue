<template>
  <header class="app-header">
    <div class="feed-info" v-if="feedStore.selectedFeed">
      <div class="feed-header">
        <img v-if="feedStore.selectedFeed.avatar_url" :src="feedStore.selectedFeed.avatar_url" :alt="feedStore.selectedFeed.name" class="feed-avatar" />
        <div class="feed-details">
          <div class="feed-title-row">
            <h2 class="feed-name">{{ feedStore.selectedFeed.name }}</h2>
            <span v-if="feedStore.selectedFeed.like_count" class="like-count">
              <svg class="heart-icon" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
              </svg>
              {{ formatNumber(feedStore.selectedFeed.like_count) }}
            </span>
          </div>
          <div v-if="feedStore.selectedFeed.bluesky_description" class="feed-description">
            {{ feedStore.selectedFeed.bluesky_description }}
          </div>
        </div>
      </div>
    </div>
    <div class="header-content">
      <img src="/src/assets/fema.jpg" alt="FEMA Logo" class="fema-logo" />
      <h1 class="logo">feedmaster</h1>
    </div>
    <div class="header-right">
      <div class="search-dropdown-group">
        <SearchBar @openUserModal="openUserModal" @openHashtagModal="openHashtagModal" />
        <div class="dropdown" @click="toggleDropdown" ref="dropdown">
        <button class="dropdown-button">☰</button>
        <div class="dropdown-menu" :class="{ show: showDropdown }">
          <a href="/apply" class="dropdown-item">Apply for Feed</a>
          <a href="/dashboard" class="dropdown-item">Dashboard</a>
          <a href="/geo-hashtags" class="dropdown-item">Location Hashtags</a>
        </div>
        </div>
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import { useFeedStore } from '@/stores/useFeedStore';
import SearchBar from './SearchBar.vue';

const feedStore = useFeedStore();
const showDropdown = ref(false);
const dropdown = ref(null);

const emit = defineEmits(['openUserModal', 'openHashtagModal'])

const openUserModal = (user: any) => {
  emit('openUserModal', user)
}

const openHashtagModal = (hashtag: string) => {
  emit('openHashtagModal', hashtag)
}

const formatNumber = (num: number): string => {
  if (num >= 1000000) {
    return (num / 1000000).toFixed(1) + 'M';
  } else if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'K';
  }
  return num.toString();
};

const toggleDropdown = () => {
  showDropdown.value = !showDropdown.value;
};

const closeDropdown = (event: Event) => {
  if (dropdown.value && !dropdown.value.contains(event.target)) {
    showDropdown.value = false;
  }
};

onMounted(() => {
  document.addEventListener('click', closeDropdown);
});

onUnmounted(() => {
  document.removeEventListener('click', closeDropdown);
});
</script>

<style scoped>
.app-header {
  grid-area: header;
  background-color: var(--bg-secondary);
  color: var(--text-primary);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 1.5rem 0 8px;
  border-radius: 8px;
}

.feed-info {
  flex: 1;
}

.feed-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.feed-avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  object-fit: cover;
}

.feed-details {
  display: flex;
  flex-direction: column;
  gap: 0px;
}

.feed-title-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.feed-name {
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.like-count {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #ef4444;
  font-size: 0.9rem;
  font-weight: 500;
}

.heart-icon {
  width: 16px;
  height: 16px;
}

.feed-description {
  color: var(--text-secondary);
  font-size: 0.85rem;
  line-height: 1.2;
  max-width: 60%;
  margin-top: -8px;
}

.header-content {
  display: flex;
  align-items: center;
  gap: 1rem;
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.search-dropdown-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.fema-logo {
  height: 40px;
  width: 40px;
  border-radius: 8px;
  object-fit: cover;
}

.logo {
  font-size: 1.75rem;
  font-weight: 600;
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  margin-left: 1rem;
  color: var(--text-primary);
}

.dropdown {
  position: relative;
}

.dropdown-button {
  background: var(--bg-tertiary);
  border: none;
  color: var(--text-primary);
  padding: 8px 12px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 1.2rem;
  transition: background-color 0.2s;
}

.dropdown-button:hover {
  background: var(--hover-bg);
}

.dropdown-menu {
  position: absolute;
  top: 100%;
  right: 0;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  min-width: 180px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  opacity: 0;
  visibility: hidden;
  transform: translateY(-10px);
  transition: all 0.2s ease;
  z-index: 1000;
  margin-top: 8px;
}

.dropdown-menu.show {
  opacity: 1;
  visibility: visible;
  transform: translateY(0);
}

.dropdown-item {
  display: block;
  padding: 12px 16px;
  color: var(--text-secondary);
  text-decoration: none;
  transition: background-color 0.2s;
  border-bottom: 1px solid var(--border-color);
}

.dropdown-item:last-child {
  border-bottom: none;
}

.dropdown-item:hover {
  background: var(--bg-tertiary);
  color: var(--text-primary);
}


</style>
