<template>
  <div class="search-container search-bar">
    <input 
      type="search" 
      v-model="searchQuery" 
      @input="handleSearch"
      @focus="showResults = true"
      @blur="hideResults"
      placeholder="Search users and hashtags..."
      class="search-input"
    />
    <div v-if="showResults && (results.users?.length > 0 || results.hashtags?.length > 0 || loading || error)" class="search-results">
      <div v-if="loading" class="search-loading">Searching...</div>
      <div v-else-if="error" class="search-error">{{ error }}</div>
      <div v-else-if="results.users?.length === 0 && results.hashtags?.length === 0 && searchQuery.length >= 2" class="search-no-results">
        No results found
      </div>
      <div v-else>
        <div 
          v-for="user in results.users" 
          :key="user.did" 
          class="search-result-item"
          @mousedown="openUserModal(user)"
        >
          <img :src="user.avatar_url || 'https://via.placeholder.com/32'" :alt="user.handle" class="result-avatar" />
          <div class="result-info">
            <div class="result-name">{{ user.display_name || user.handle }}</div>
            <div class="result-handle">@{{ user.handle }}</div>
          </div>
        </div>
        <div 
          v-for="hashtag in results.hashtags" 
          :key="hashtag.hashtag" 
          class="search-result-item hashtag-item"
          @mousedown="openHashtagModal(hashtag.hashtag)"
        >
          <div class="hashtag-icon">#</div>
          <div class="result-info">
            <div class="result-name">{{ hashtag.hashtag }}</div>
            <div class="result-handle">{{ hashtag.count }} posts</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'


const searchQuery = ref('')
const results = ref({ users: [], hashtags: [] })
const loading = ref(false)
const error = ref(null)
const showResults = ref(false)
let searchTimeout = null

const emit = defineEmits(['openUserModal', 'openHashtagModal'])

const handleSearch = () => {
  if (searchTimeout) clearTimeout(searchTimeout)
  
  if (searchQuery.value.length < 2) {
    results.value = { users: [], hashtags: [] }
    return
  }
  
  searchTimeout = setTimeout(async () => {
    loading.value = true
    error.value = null
    
    try {
      const response = await fetch(`/api/v1/search?q=${encodeURIComponent(searchQuery.value)}`)
      if (!response.ok) throw new Error('Search failed')
      
      const data = await response.json()
      results.value = {
        users: data.users || [],
        hashtags: data.hashtags || []
      }
    } catch (err) {
      error.value = 'Search failed'
      results.value = { users: [], hashtags: [] }
    } finally {
      loading.value = false
    }
  }, 300)
}

const openUserModal = (user) => {
  emit('openUserModal', {
    did: user.did,
    handle: user.handle,
    display_name: user.display_name,
    avatar_url: user.avatar_url
  })
  showResults.value = false
  searchQuery.value = ''
}

const openHashtagModal = (hashtag) => {
  emit('openHashtagModal', hashtag)
  showResults.value = false
  searchQuery.value = ''
}

const hideResults = () => {
  setTimeout(() => {
    showResults.value = false
  }, 200)
}
</script>

<style scoped>
.search-container {
  position: relative;
  width: 300px;
}

.search-bar {
  z-index: 10000;
}

.search-input {
  width: 100%;
  padding: 8px 12px;
  background-color: #404249;
  border: 1px solid #5a5d66;
  border-radius: 6px;
  color: #dcddde;
  font-size: 0.9rem;
  outline: none;
  transition: border-color 0.2s ease;
}

.search-input:focus {
  border-color: #5865f2;
}

.search-input::placeholder {
  color: #8a8e94;
}

.search-results {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  background-color: #2b2d31;
  border: 1px solid #404249;
  border-radius: 6px;
  margin-top: 4px;
  max-height: 300px;
  overflow-y: auto;
  z-index: 9999;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  scrollbar-width: none;
}

.search-results::-webkit-scrollbar {
  display: none;
}

.search-loading, .search-error, .search-no-results {
  padding: 12px;
  text-align: center;
  color: #8a8e94;
  font-size: 0.9rem;
}

.search-error {
  color: #e57373;
}

.search-result-item {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  cursor: pointer;
  transition: background-color 0.2s ease;
  gap: 8px;
}

.search-result-item:hover {
  background-color: #404249;
}

.result-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  object-fit: cover;
}

.result-info {
  display: flex;
  flex-direction: column;
}

.result-name {
  font-weight: 600;
  color: #dcddde;
  font-size: 0.9rem;
}

.result-handle {
  color: #8a8e94;
  font-size: 0.8rem;
}

.hashtag-item {
  color: #00d4aa;
}

.hashtag-icon {
  width: 32px;
  height: 32px;
  background-color: #00d4aa;
  color: #2b2d31;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 1.2rem;
}
</style>