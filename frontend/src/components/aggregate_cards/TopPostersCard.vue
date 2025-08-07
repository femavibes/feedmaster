<template>
  <div class="card top-posters-card">
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
    <div class="card-body">
      <!-- Top Users Tab -->
      <ul v-if="activeTab === 'users' && topUsers && topUsers.length" class="poster-list">
        <li v-for="user in topUsers" :key="user.did" class="poster-item clickable" @click="openUserModal(user)">
          <div class="poster-info">
            <img :src="user.avatar_url" alt="Avatar" class="avatar" @error="onAvatarError" />
            <div class="poster-details">
              <span class="poster-name">{{ user.display_name || user.handle }}</span>
              <span class="poster-handle">@{{ user.handle }}</span>
            </div>
          </div>
          <span class="poster-count">{{ user.count }} score</span>
        </li>
      </ul>
      
      <!-- Top Posters Tab -->
      <ul v-else-if="activeTab === 'posters' && users && users.length" class="poster-list">
        <li v-for="poster in users" :key="poster.did" class="poster-item clickable" @click="openUserModal(poster)">
          <div class="poster-info">
            <img :src="poster.avatar_url" alt="Avatar" class="avatar" @error="onAvatarError" />
            <div class="poster-details">
              <span class="poster-name">{{ poster.display_name || poster.handle }}</span>
              <span class="poster-handle">@{{ poster.handle }}</span>
            </div>
          </div>
          <span class="poster-count">{{ poster.count }} posts</span>
        </li>
      </ul>
      
      <!-- Top Mentions Tab -->
      <ul v-else-if="activeTab === 'mentions' && topMentions && topMentions.length" class="poster-list">
        <li v-for="mention in topMentions" :key="mention.did" class="poster-item clickable" @click="openUserModal(mention)">
          <div class="poster-info">
            <img :src="mention.avatar_url" alt="Avatar" class="avatar" @error="onAvatarError" />
            <div class="poster-details">
              <span class="poster-name">{{ mention.display_name || mention.handle }}</span>
              <span class="poster-handle">@{{ mention.handle }}</span>
            </div>
          </div>
          <span class="poster-count">{{ mention.count }} mentions</span>
        </li>
      </ul>
      
      <p v-else class="no-data">No data available for this category.</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useAvatar } from '@/composables/useAvatar';

const { onAvatarError } = useAvatar();

defineProps<{
  users: any[];
  topUsers: any[];
  topMentions: any[];
}>();

const emit = defineEmits<{
  openUserModal: [user: any]
}>()

const activeTab = ref('users')

const tabs = [
  { value: 'users', label: 'Top Users' },
  { value: 'posters', label: 'Top Posters' },
  { value: 'mentions', label: 'Top Mentions' },
]

const openUserModal = (user: any) => {
  emit('openUserModal', user)
}
</script>

<style scoped>
.top-posters-card {
  background-color: #2b2d31;
  border: 1px solid #404249;
  border-radius: 8px;
  color: #dcddde;
  font-family: 'Inter', sans-serif;
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
  flex: 1;
}

.tab-selector button.active {
  background-color: #2b2d31;
  color: #fff;
}

.tab-selector button:hover:not(.active) {
  background-color: #3c3e44;
}

.card-body {
  flex: 1;
  overflow-y: auto;
  -ms-overflow-style: none;
  scrollbar-width: none;
}

.card-body::-webkit-scrollbar {
  display: none;
}

.poster-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.poster-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem;
  border-bottom: 1px solid #313338;
  background-color: #404249;
  border: 1px solid #5a5d66;
  border-radius: 8px;
  margin-bottom: 8px;
}

.poster-item.clickable {
  cursor: pointer;
  transition: all 0.2s ease;
}

.poster-item.clickable:hover {
  background-color: #4a4d54;
  border-color: #6a6d76;
  transform: translateY(-1px);
}

.poster-item:last-child {
  margin-bottom: 0;
}

.poster-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  object-fit: cover;
}

.poster-details {
  display: flex;
  flex-direction: column;
}

.poster-name {
  font-weight: 600;
}

.poster-handle {
  color: #8a8e94;
  font-size: 0.9rem;
}

.poster-count {
  font-weight: 500;
  background-color: #2b2d31;
  color: #b5bac1;
  padding: 4px 6px;
  border-radius: 4px;
  font-size: 0.75rem;
  border: 1px solid #404249;
}

.no-data {
  text-align: center;
  color: #8a8e94;
}
</style>
