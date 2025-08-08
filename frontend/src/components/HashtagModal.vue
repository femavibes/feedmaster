<template>
  <div v-if="isVisible" class="modal-overlay" @click="closeModal">
    <div class="modal-container" @click.stop>
      <button class="modal-close-btn" @click="closeModal">&times;</button>
      
      <div class="modal-header">
        <h3>Posts with #{{ hashtag }}</h3>
        <div v-if="analytics" class="hashtag-stats">
          <div class="stat-item">
            <span class="stat-label">Total Posts:</span>
            <span class="stat-value">{{ analytics.total_posts }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">Avg Engagement:</span>
            <span class="stat-value">{{ analytics.avg_likes }}❤️ {{ analytics.avg_reposts }}🔄</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">Total Engagement:</span>
            <span class="stat-value">{{ analytics.total_engagement }}</span>
          </div>
        </div>
        <div v-if="analytics?.top_users?.length" class="top-users">
          <h4>Top Users:</h4>
          <div class="users-list">
            <span v-for="user in analytics.top_users.slice(0, 3)" :key="user.did" 
                  class="user-tag clickable" @click="openUserModal(user)">
              @{{ user.handle }} ({{ user.usage_count }})
            </span>
          </div>
        </div>
      </div>
      
      <div v-if="loading" class="loading">Loading posts...</div>
      <div v-else-if="error" class="error-message">{{ error }}</div>
      
      <div v-else class="modal-body">
        <div v-if="posts.length" class="posts-list">
          <div v-for="post in posts" :key="post.uri" class="post-card">
            <div class="post-author clickable" @click="openUserModal(post.author)">
              <img :src="post.author.avatar_url" alt="avatar" class="avatar" @error="onAvatarError" />
              <div class="author-info">
                <span class="display-name">{{ post.author.display_name || post.author.handle }}</span>
                <span class="handle">@{{ post.author.handle }}</span>
              </div>
            </div>
            <div class="post-text" v-html="formatPostText(post.text)"></div>
            <div class="post-meta">
              <span>❤️ {{ post.like_count }}</span>
              <span>🔄 {{ post.repost_count }}</span>
              <span class="post-time">{{ new Date(post.created_at).toLocaleString() }}</span>
            </div>
          </div>
        </div>
        <p v-else>No posts found with this hashtag.</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import apiService from '@/apiService'

interface Post {
  uri: string
  text: string
  created_at: string
  like_count: number
  repost_count: number
  author: {
    did: string
    handle: string
    display_name?: string
    avatar_url?: string
  }
}

const props = defineProps<{
  isVisible: boolean
  hashtag: string | null
  feedId: string
  count?: number
}>()

const emit = defineEmits<{
  close: []
  openUserModal: [user: any]
}>()

const loading = ref(false)
const error = ref<string | null>(null)
const posts = ref<Post[]>([])
const analytics = ref<any>(null)

const closeModal = () => {
  emit('close')
}

const openUserModal = (user: any) => {
  emit('openUserModal', user)
}

const onAvatarError = (event: Event) => {
  const target = event.target as HTMLImageElement
  target.src = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxIDEiPjwvc3ZnPg=='
}

const formatPostText = (text: string) => {
  if (!text) return ''
  return text
    .replace(/(#[a-zA-Z0-9_]+)/g, '<strong style="color: #00d4aa; font-weight: bold;">$1</strong>')
    .replace(/(@([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63})/g, '<span style="color: #5865f2; font-weight: bold;">$1</span>')
}

const fetchHashtagPosts = async () => {
  if (!props.hashtag || !props.feedId) return
  
  loading.value = true
  error.value = null
  
  try {
    const [postsResponse, analyticsResponse] = await Promise.all([
      apiService.get(`/feeds/${props.feedId}/posts/by_hashtag/${props.hashtag}?limit=20`),
      apiService.get(`/feeds/${props.feedId}/hashtag/${props.hashtag}/analytics`)
    ])
    posts.value = postsResponse.data.posts
    analytics.value = analyticsResponse.data
  } catch (err: any) {
    console.error('Error loading hashtag data:', err)
    error.value = 'Failed to load posts for this hashtag'
  } finally {
    loading.value = false
  }
}

watch(() => [props.isVisible, props.hashtag], () => {
  if (props.isVisible && props.hashtag) {
    fetchHashtagPosts()
  }
}, { immediate: true })
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.8);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

.modal-container {
  background-color: #2b2d31;
  border: 1px solid #404249;
  padding: 2rem;
  border-radius: 12px;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
  width: 95%;
  max-width: 800px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
  color: #dcddde;
}

.modal-close-btn {
  position: absolute;
  top: 1rem;
  right: 1rem;
  font-size: 1.5rem;
  color: #949ba4;
  cursor: pointer;
  border: none;
  background: none;
  line-height: 1;
  padding: 0.5rem;
  border-radius: 6px;
  transition: all 0.2s ease;
}

.modal-close-btn:hover {
  color: #fff;
  background-color: #404249;
}

.modal-header {
  border-bottom: 1px solid #404249;
  padding-bottom: 1.5rem;
  margin-bottom: 1.5rem;
}

.modal-header h3 {
  margin: 0;
  font-size: 1.5rem;
  color: #fff;
  font-weight: 600;
}

.modal-header p {
  margin: 0.5rem 0 0;
  color: #949ba4;
  font-size: 0.9rem;
}

.loading {
  text-align: center;
  padding: 3rem;
  font-size: 1.1rem;
  color: #949ba4;
}

.error-message {
  color: #e57373;
  background-color: #3c1f1f;
  padding: 1rem;
  border-radius: 8px;
  border: 1px solid #5c2e2e;
  font-weight: 500;
  text-align: center;
  margin: 1rem 0;
}

.modal-body {
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: #404249 transparent;
}

.modal-body::-webkit-scrollbar {
  width: 6px;
}

.modal-body::-webkit-scrollbar-thumb {
  background-color: #404249;
  border-radius: 3px;
}

.posts-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.post-card {
  background-color: #313338;
  border: 1px solid #404249;
  border-radius: 8px;
  padding: 1rem;
}

.post-author {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.post-author.clickable {
  cursor: pointer;
  transition: all 0.2s ease;
  border-radius: 6px;
  padding: 8px;
  margin: -8px -8px 0.75rem -8px;
}

.post-author.clickable:hover {
  background-color: #404249;
  transform: translateY(-1px);
}

.avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  object-fit: cover;
}

.author-info {
  display: flex;
  flex-direction: column;
}

.display-name {
  font-weight: bold;
  color: #fff;
}

.handle {
  color: #949ba4;
  font-size: 0.9rem;
}

.post-text {
  white-space: pre-wrap;
  word-break: break-word;
  margin-bottom: 0.75rem;
  color: #dcddde;
}

.post-meta {
  display: flex;
  gap: 1rem;
  font-size: 0.85rem;
  color: #949ba4;
  border-top: 1px solid #404249;
  padding-top: 0.75rem;
}

.post-time {
  margin-left: auto;
}

.hashtag-stats {
  display: flex;
  gap: 1.5rem;
  margin: 1rem 0;
  flex-wrap: wrap;
}

.stat-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.stat-label {
  font-size: 0.8rem;
  color: #949ba4;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.stat-value {
  font-size: 1.1rem;
  font-weight: 600;
  color: #fff;
}

.top-users {
  margin-top: 1rem;
}

.top-users h4 {
  margin: 0 0 0.5rem 0;
  font-size: 0.9rem;
  color: #949ba4;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.users-list {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.user-tag {
  background-color: #404249;
  color: #dcddde;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.8rem;
  border: 1px solid #5a5d66;
}

.user-tag.clickable {
  cursor: pointer;
  transition: all 0.2s ease;
}

.user-tag.clickable:hover {
  background-color: #5a5d66;
  transform: translateY(-1px);
}
</style>