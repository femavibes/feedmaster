<template>
  <div v-if="isVisible" class="modal-overlay" @click="closeModal">
    <div class="modal-container" @click.stop>
      <button class="modal-close-btn" @click="closeModal">&times;</button>
      
      <div v-if="loading" class="loading">
        <p>Loading user profile...</p>
      </div>
      
      <div v-else-if="error" class="error-message">
        <p>{{ error }}</p>
        <p v-if="error.includes('not posted to any feeds')" class="error-explanation">
          Users who have never posted to any feeds monitored by this application won't have profile data available.
        </p>
      </div>
      
      <div v-else-if="userProfile">
        <div class="modal-header">
          <img :src="userProfile.avatar_url || 'https://via.placeholder.com/80'" :alt="`${userProfile.handle}'s avatar`">
          <div class="user-details">
            <h3>{{ userProfile.display_name || userProfile.handle }}</h3>
            <a :href="`https://bsky.app/profile/${userProfile.handle}`" target="_blank" class="user-handle">@{{ userProfile.handle }}</a>
            <p class="user-stats">
              <strong>{{ userProfile.followers_count || 0 }}</strong> Followers | 
              <strong>{{ userProfile.following_count || 0 }}</strong> Following
            </p>
          </div>
        </div>
        
        <div class="modal-body">
          <div class="modal-grid">
            <!-- Left Column -->
            <div class="modal-column">
              <div class="modal-section">
                <h4>Stats in this Feed</h4>
                <div v-if="feedStats && feedStats.post_count > 0" class="stats-list">
                  <div class="stat-item">
                    <span>Total Posts:</span>
                    <span class="count">{{ feedStats.post_count || 0 }}</span>
                  </div>
                  <div class="stat-item">
                    <span>Total Likes Received:</span>
                    <span class="count">{{ feedStats.total_likes_received || 0 }}</span>
                  </div>
                  <div class="stat-item">
                    <span>Total Reposts Received:</span>
                    <span class="count">{{ feedStats.total_reposts_received || 0 }}</span>
                  </div>
                  <div class="stat-item">
                    <span>First Post:</span>
                    <span class="count">{{ formatDate(feedStats.first_post_at) }}</span>
                  </div>
                </div>
                <div v-else class="no-stats-message">
                  <p>No stats available for this user in this feed.</p>
                  <p v-if="achievements.length > 0" class="feed-hint">
                    This user has achievements in other feeds. Check their achievements below to see where they're active.
                  </p>
                </div>
              </div>
              
              <div class="modal-section">
                <h4>Recent Posts in this Feed</h4>
                <div class="scrollable-list">
                  <div v-if="recentPosts && recentPosts.length > 0" class="posts-list">
                    <a 
                      v-for="post in recentPosts" 
                      :key="post.uri"
                      :href="getPostUrl(post)"
                      target="_blank"
                      class="post-card"
                    >
                      <div class="post-text">{{ post.text || 'No text content.' }}</div>
                      <div class="post-engagement">
                        <small class="post-date">{{ formatDate(post.created_at) }}</small>
                        <div class="engagement-stats">
                          <span class="icon-heart">{{ post.like_count || 0 }}</span>
                          <span class="icon-repost">{{ post.repost_count || 0 }}</span>
                          <span class="icon-reply">{{ post.reply_count || 0 }}</span>
                          <span class="icon-quote">{{ post.quote_count || 0 }}</span>
                        </div>
                      </div>
                    </a>
                  </div>
                  <p v-else>No recent posts by this user in this feed.</p>
                </div>
              </div>
            </div>
            
            <!-- Right Column -->
            <div class="modal-column">
              <div class="modal-section">
                <h4>Achievements</h4>
                <div v-if="achievements && achievements.length > 0" class="scrollable-list">
                  <div class="achievements-list">
                    <div v-for="userAch in achievements" :key="`${userAch.achievement.name}-${userAch.feed_id}`" class="achievement-item">
                      <div class="achievement-content">
                        <div class="achievement-header">
                          <span class="type-icon" :title="userAch.achievement.type === 'global' ? 'Global Achievement' : 'Feed-Specific Achievement'">
                            {{ userAch.achievement.type === 'global' ? '🌍' : '📰' }}
                          </span>
                          <strong>{{ userAch.achievement.name }}</strong>
                          <span v-if="userAch.feed" class="feed-context">(in {{ userAch.feed.name }})</span>
                        </div>
                        <small class="achievement-description">{{ userAch.achievement.description }}</small>
                      </div>
                      <div class="achievement-rarity">
                        <div class="rarity-info">
                          <span class="rarity-icon">{{ getRarityIcon(userAch.achievement.rarity_tier) }}</span>
                          <span class="rarity-label" :class="`rarity-${(userAch.achievement.rarity_tier || 'bronze').toLowerCase()}`">
                            {{ userAch.achievement.rarity_tier || 'Bronze' }}
                          </span>
                          <button class="share-btn" @click="shareAchievement(userAch)" title="Share this achievement">
                            📤
                          </button>
                        </div>
                        <small class="rarity-percentage">
                          {{ userAch.achievement.rarity_percentage?.toFixed(2) }}% {{ userAch.achievement.type === 'global' ? 'of users globally' : 'of users in this feed' }}
                        </small>
                      </div>
                    </div>
                  </div>
                </div>
                <p v-else>No achievements earned yet.</p>
              </div>
              
              <div class="modal-section">
                <h4>In Progress</h4>
                <div v-if="inProgressAchievements && inProgressAchievements.length > 0" class="scrollable-list">
                  <div class="progress-list">
                    <div v-for="progAch in inProgressAchievements" :key="`${progAch.achievement.name}-${progAch.feed?.id}`" class="progress-item">
                      <div class="progress-header">
                        <div class="achievement-content">
                          <div class="achievement-header">
                            <span class="type-icon" :title="progAch.achievement.type === 'global' ? 'Global Achievement' : 'Feed-Specific Achievement'">
                              {{ progAch.achievement.type === 'global' ? '🌍' : '📰' }}
                            </span>
                            <strong>{{ progAch.achievement.name }}</strong>
                            <span v-if="progAch.feed" class="feed-context">(in {{ progAch.feed.name }})</span>
                          </div>
                          <small class="achievement-description">{{ progAch.achievement.description }}</small>
                        </div>
                        <div class="progress-value">
                          {{ Math.round(progAch.current_value) }} / {{ progAch.required_value }}
                        </div>
                      </div>
                      <div class="progress-bar-container">
                        <div class="progress-bar" :style="{ width: `${progAch.progress_percentage.toFixed(2)}%` }"></div>
                      </div>
                    </div>
                  </div>
                </div>
                <p v-else>No achievements currently in progress.</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <Toast :message="toastMessage" :type="toastType" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import apiService from '@/apiService'
import Toast from './Toast.vue'

interface User {
  did: string
  handle: string
  display_name?: string
  avatar_url?: string
}

interface UserProfile {
  did: string
  handle: string
  display_name?: string
  description?: string
  avatar_url?: string
  followers_count?: number
  following_count?: number
  posts_count?: number
}

interface FeedStats {
  user_did: string
  feed_id: string
  post_count: number
  total_likes_received: number
  total_reposts_received: number
  total_replies_received: number
  total_quotes_received: number
  first_post_at?: string
  latest_post_at?: string
}

interface Achievement {
  id?: number
  name: string
  description: string
  icon?: string
  rarity_percentage: number
  rarity_label: string
  rarity_tier?: string
  type: 'global' | 'per_feed'
}

interface UserAchievement {
  achievement: Achievement
  earned_at: string
  feed_id?: string
  feed?: { id: string; name: string }
}

interface InProgressAchievement {
  achievement: Achievement
  current_value: number
  required_value: number
  progress_percentage: number
  feed?: { id: string; name: string }
}

interface Post {
  uri: string
  text?: string
  created_at: string
  like_count: number
  repost_count: number
  reply_count: number
  quote_count: number
}

const props = defineProps<{
  isVisible: boolean
  user: User | null
  feedId: string
}>()

const emit = defineEmits<{
  close: []
}>()

const loading = ref(false)
const error = ref<string | null>(null)
const userProfile = ref<UserProfile | null>(null)
const feedStats = ref<FeedStats | null>(null)
const achievements = ref<UserAchievement[]>([])
const inProgressAchievements = ref<InProgressAchievement[]>([])
const recentPosts = ref<Post[]>([])

const closeModal = () => {
  emit('close')
}

const formatDate = (dateString?: string) => {
  if (!dateString) return 'N/A'
  return new Date(dateString).toLocaleDateString()
}

const getPostUrl = (post: Post) => {
  const postRkey = post.uri.split('/').pop()
  const authorIdentifier = props.user?.handle || props.user?.did
  return `https://bsky.app/profile/${authorIdentifier}/post/${postRkey}`
}

const getRarityIcon = (rarityTier?: string) => {
  const icons: Record<string, string> = {
    'Mythic': '✨',
    'Legendary': '👑',
    'Diamond': '💠',
    'Platinum': '💿',
    'Gold': '🥇',
    'Silver': '🥈',
    'Bronze': '🥉',
  }
  return icons[rarityTier || 'Bronze'] || '🏅'
}

const toastMessage = ref('')
const toastType = ref('success')

const shareAchievement = async (userAch: UserAchievement) => {
  const achievementId = userAch.achievement.id || encodeURIComponent(userAch.achievement.name)
  const shareUrl = `https://feedmaster.fema.monster/achievement/${props.user?.did}/${achievementId}`
  
  try {
    // Clear any existing toast first
    toastMessage.value = ''
    await new Promise(resolve => setTimeout(resolve, 50))
    
    await navigator.clipboard.writeText(shareUrl)
    toastMessage.value = 'Achievement link copied! Share on Bluesky 🚀'
    toastType.value = 'success'
  } catch (err) {
    console.error('Failed to copy link:', err)
    toastMessage.value = 'Achievement link copied!'
    toastType.value = 'success'
  }
}

const loadUserProfile = async () => {
  if (!props.user || !props.feedId) return
  
  loading.value = true
  error.value = null
  
  try {
    // Load profile details first (required)
    const profileRes = await apiService.get(`/profiles/${props.user.did}/details`)
    userProfile.value = profileRes.data
    
    // Load other data in parallel, but handle failures gracefully
    const [statsRes, achievementsRes, inProgressRes, postsRes] = await Promise.allSettled([
      apiService.get(`/profiles/${props.user.did}/stats/${props.feedId}`),
      apiService.get(`/profiles/${props.user.did}/achievements`),
      apiService.get(`/profiles/${props.user.did}/achievements/in-progress`),
      apiService.get(`/feeds/${props.feedId}/posts/by_author/${props.user.did}?limit=5`)
    ])
    
    // Handle stats (may not exist for this feed)
    if (statsRes.status === 'fulfilled') {
      feedStats.value = statsRes.value.data
    } else {
      feedStats.value = null // Will show "No stats available"
    }
    
    // Handle achievements
    if (achievementsRes.status === 'fulfilled') {
      achievements.value = achievementsRes.value.data.sort((a: UserAchievement, b: UserAchievement) => 
        (a.achievement.rarity_percentage || 100) - (b.achievement.rarity_percentage || 100)
      )
    } else {
      achievements.value = []
    }
    
    // Handle in-progress achievements
    if (inProgressRes.status === 'fulfilled') {
      inProgressAchievements.value = inProgressRes.value.data
    } else {
      inProgressAchievements.value = []
    }
    
    // Handle recent posts
    if (postsRes.status === 'fulfilled') {
      recentPosts.value = postsRes.value.data.posts
    } else {
      recentPosts.value = []
    }
    
  } catch (err: any) {
    console.error('Error loading user profile:', err)
    if (err.response?.status === 404 && err.response?.data?.detail === 'User not found') {
      error.value = 'This user has not posted to any feeds yet, so no profile information is available.'
    } else {
      error.value = err.response?.data?.detail || 'Failed to load user profile'
    }
  } finally {
    loading.value = false
  }
}

watch(() => [props.isVisible, props.user, props.feedId], () => {
  if (props.isVisible && props.user) {
    loadUserProfile()
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
  max-width: 1200px;
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

.error-explanation {
  color: #b5bac1 !important;
  font-weight: normal !important;
  font-size: 0.9rem;
  margin-top: 0.5rem !important;
  font-style: italic;
}

.modal-header {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  border-bottom: 1px solid #404249;
  padding-bottom: 1.5rem;
  margin-bottom: 1.5rem;
}

.modal-header img {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  object-fit: cover;
  border: 2px solid #404249;
}

.user-details h3 {
  margin: 0;
  font-size: 1.5rem;
  color: #fff;
  font-weight: 600;
}

.user-details p {
  margin: 0.25rem 0 0;
  color: #949ba4;
  font-size: 1rem;
}

.user-handle {
  color: #5865f2 !important;
  text-decoration: none;
  font-size: 1rem;
  margin-top: 0.25rem;
  display: block;
  transition: color 0.2s ease;
}

.user-handle:hover {
  color: #7289da !important;
  text-decoration: underline;
}

.user-stats {
  font-size: 0.85rem !important;
  color: #72767d !important;
}

.modal-body {
  overflow-y: auto;
  padding-right: 1rem;
  scrollbar-width: thin;
  scrollbar-color: #404249 transparent;
}

.modal-body::-webkit-scrollbar {
  width: 6px;
}

.modal-body::-webkit-scrollbar-track {
  background: transparent;
}

.modal-body::-webkit-scrollbar-thumb {
  background-color: #404249;
  border-radius: 3px;
}

.modal-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 2rem;
  align-items: start;
}

.modal-column {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.modal-section {
  background-color: #313338;
  border: 1px solid #404249;
  border-radius: 8px;
  padding: 1.5rem;
}

.modal-section h4 {
  color: #fff;
  margin: 0 0 1rem 0;
  font-size: 1.1rem;
  font-weight: 600;
}

.stats-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.stat-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: #404249;
  border: 1px solid #5a5d66;
  padding: 0.75rem 1rem;
  border-radius: 6px;
}

.count {
  background-color: #2b2d31;
  color: #b5bac1;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-weight: 500;
  font-size: 0.75rem;
  border: 1px solid #404249;
}

.no-stats-message {
  color: #949ba4;
  font-style: italic;
}

.feed-hint {
  font-size: 0.85rem;
  color: #72767d;
  margin-top: 0.5rem;
}

.scrollable-list {
  max-height: 300px;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: #404249 transparent;
}

.scrollable-list::-webkit-scrollbar {
  width: 4px;
}

.scrollable-list::-webkit-scrollbar-thumb {
  background-color: #404249;
  border-radius: 2px;
}

.posts-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.post-card {
  display: block;
  background-color: #404249;
  border: 1px solid #5a5d66;
  border-radius: 6px;
  padding: 1rem;
  text-decoration: none;
  color: #dcddde;
  cursor: pointer;
  transition: all 0.2s ease;
}

.post-card:hover {
  background-color: #4a4d54;
  border-color: #6a6d76;
  transform: translateY(-1px);
}

.post-text {
  margin-bottom: 0.75rem;
  line-height: 1.4;
  color: #dcddde;
}

.post-engagement {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.8rem;
  border-top: 1px solid #5a5d66;
  padding-top: 0.5rem;
}

.post-date {
  color: #72767d;
}

.engagement-stats {
  display: flex;
  gap: 1rem;
  color: #949ba4;
}

.engagement-stats span {
  display: inline-flex;
  align-items: center;
}

.icon-heart::before { content: '❤️ '; }
.icon-repost::before { content: '🔄 '; }
.icon-reply::before { content: '💬 '; }
.icon-quote::before { content: '🗨️ '; }

.achievements-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.achievement-item {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  background-color: #404249;
  border: 1px solid #5a5d66;
  padding: 1rem;
  border-radius: 6px;
}

.achievement-content {
  flex-grow: 1;
  margin-right: 1rem;
}

.achievement-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.25rem;
}

.type-icon {
  cursor: help;
  font-size: 1rem;
}

.feed-context {
  font-style: italic;
  color: #72767d;
  font-weight: normal;
  font-size: 0.9rem;
}

.achievement-description {
  display: block;
  color: #949ba4;
  font-size: 0.85rem;
  padding-left: 1.5rem;
}

.achievement-rarity {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  text-align: right;
  white-space: nowrap;
}

.rarity-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.25rem;
}

.share-btn {
  background: none;
  border: 1px solid #5a5d66;
  color: #949ba4;
  padding: 0.25rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.8rem;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
}

.share-btn:hover {
  background-color: #404249;
  border-color: #6a6d76;
  color: #dcddde;
  transform: scale(1.1);
}

.rarity-icon {
  font-size: 1.2rem;
}

.rarity-label {
  display: inline-block;
  padding: 0.125rem 0.5rem;
  border-radius: 8px;
  font-size: 0.7rem;
  font-weight: bold;
  color: white;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.rarity-bronze { background-color: #cd7f32; }
.rarity-silver { background-color: #c0c0c0; color: #333; }
.rarity-gold { background-color: #ffd700; color: #333; }
.rarity-platinum { background-color: #e5e4e2; color: #333; }
.rarity-diamond { background-color: #b9f2ff; color: #333; }
.rarity-legendary { background-color: #9400d3; }
.rarity-mythic {
  background: linear-gradient(45deg, #ff00ff, #ff9900, #ffff00, #00ff00, #00ffff, #0000ff, #ff00ff);
  background-size: 400% 400%;
  animation: gradient 5s ease infinite;
}

.rarity-percentage {
  color: #72767d;
  font-size: 0.75rem;
  font-style: italic;
}

.progress-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.progress-item {
  background-color: #404249;
  border: 1px solid #5a5d66;
  padding: 1rem;
  border-radius: 6px;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 0.5rem;
}

.progress-value {
  white-space: nowrap;
  font-weight: 500;
  color: #b5bac1;
  font-size: 0.85rem;
}

.progress-bar-container {
  width: 100%;
  background-color: #2b2d31;
  border-radius: 8px;
  height: 8px;
  overflow: hidden;
  border: 1px solid #404249;
}

.progress-bar {
  height: 100%;
  background: linear-gradient(90deg, #5865f2, #7289da);
  border-radius: 8px;
  transition: width 0.4s ease-in-out;
}

@keyframes gradient {
  0% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}
</style>