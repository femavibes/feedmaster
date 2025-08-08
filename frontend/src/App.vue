<script setup lang="ts">
import { onMounted, inject, ref } from 'vue'
import { RouterView } from 'vue-router'
import { useRoute } from 'vue-router'
import TheHeader from './components/TheHeader.vue'
import LeftNavBar from './components/LeftNavBar.vue'
import AggregateData from './components/AggregateData.vue'
import UserModal from './components/UserModal.vue'
import HashtagModal from './components/HashtagModal.vue'

const apiService = inject('apiService');
const route = useRoute()

const showUserModal = ref(false)
const selectedUser = ref(null)
const showHashtagModal = ref(false)
const selectedHashtag = ref(null)

const openUserModal = (user: any) => {
  selectedUser.value = user
  showUserModal.value = true
}

const closeUserModal = () => {
  showUserModal.value = false
  selectedUser.value = null
}

const openHashtagModal = (hashtag: string) => {
  selectedHashtag.value = hashtag
  showHashtagModal.value = true
}

const closeHashtagModal = () => {
  showHashtagModal.value = false
  selectedHashtag.value = null
}

onMounted(() => {
  apiService.fetchFeeds();
})
</script>

<template>
  <!-- Admin, Feedmaker, Apply, and Geo-hashtags pages get full layout -->
  <div v-if="route.name === 'admin' || route.name === 'feedmaker' || route.name === 'apply' || route.name === 'geo-hashtags'" class="admin-layout">
    <RouterView />
  </div>
  
  <!-- Regular app layout for other pages -->
  <div v-else class="app-layout">
    <TheHeader @openUserModal="openUserModal" @openHashtagModal="openHashtagModal" />
    <LeftNavBar />
    <main class="main-content">
      <RouterView @openUserModal="openUserModal" />
    </main>
    <AggregateData @openUserModal="openUserModal" @openHashtagModal="openHashtagModal" />
    
    <UserModal 
      :isVisible="showUserModal" 
      :user="selectedUser" 
      :feedId="route.params.feed_id as string" 
      @close="closeUserModal" 
    />
    
    <HashtagModal 
      :isVisible="showHashtagModal" 
      :hashtag="selectedHashtag" 
      :feedId="route.params.feed_id as string" 
      @close="closeHashtagModal" 
      @openUserModal="openUserModal" 
    />
  </div>
</template>

<style>
/* Global styles to ensure the dark background covers the entire page */
body {
  margin: 0;
  background-color: #2b2d31; /* This is the new home for the dark background */
  color: #e2e8f0; /* A sensible default text color for the dark background */
  font-family: sans-serif;
}
</style>

<style scoped>
.admin-layout {
  width: 100%;
  height: 100vh;
  background: #f5f5f5;
}

.app-layout {
  display: grid;
  /*
    - Left nav: 64px (fixed).
    - Main content: Takes 25% of the flexible space.
    - Right sidebar: Takes the remaining 75% of the flexible space.
  */
  grid-template-columns: 64px minmax(0, 1fr) minmax(0, 4fr);
  grid-template-rows: 64px 1fr;
  grid-template-areas:
    "header header header"
    "nav main sidebar";
  height: 100vh;

  /* The layout now takes up 90% of the viewport width and is centered. */
  width: 90%;
  margin: 0 auto; /* This centers the layout horizontally. */
  box-sizing: border-box; /* Ensures padding is included in the width. */

  gap: 8px; /* This is the key property to create space between all the boxes */
  padding: 8px; /* Adds a small border around the entire application */
  overflow: hidden; /* Prevent page scroll */
}

.main-content {
  grid-area: main;
  overflow-y: auto; /* Allows the content within the view to scroll */
}

.aggregate-data-container {
  grid-area: sidebar;
}
</style>
