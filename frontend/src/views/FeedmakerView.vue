<template>
  <div class="feedmaker-container">
    <div class="feedmaker-auth-bar">
      <div class="auth-section">
        <div v-if="!isAuthenticated" class="auth-form">
          <input 
            v-model="userDid" 
            placeholder="Enter your DID"
            @keyup.enter="authenticate"
          >
          <input 
            v-model="apiKey" 
            type="password" 
            placeholder="Enter your API key"
            @keyup.enter="authenticate"
          >
          <button @click="authenticate" :disabled="loading">Login</button>
        </div>
        <div v-else class="auth-status">
          <span>✅ Authenticated as {{ userDid }}</span>
          <button @click="logout">Logout</button>
        </div>
      </div>
    </div>

    <div v-if="isAuthenticated" class="feedmaker-content">
      <!-- Profile Overview -->
      <section class="profile-section">
        <h2>📊 Your Feeds Overview</h2>
        <div v-if="profile" class="profile-stats">
          <div class="stat-card">
            <h3>{{ profile.total_feeds }}</h3>
            <p>Active Feeds</p>
          </div>
          <div class="stat-card">
            <h3>{{ totalPosts.toLocaleString() }}</h3>
            <p>Total Posts</p>
          </div>
          <div class="stat-card">
            <h3>{{ totalUsers.toLocaleString() }}</h3>
            <p>Total Users</p>
          </div>
          <div class="stat-card">
            <h3>{{ totalAchievements.toLocaleString() }}</h3>
            <p>Achievements Earned</p>
          </div>
        </div>
      </section>

      <!-- My Feeds -->
      <section class="feeds-section">
        <div class="section-header">
          <h2>🎯 My Feeds</h2>
          <button @click="showNewApplication = true" class="btn-primary">Request New Feed</button>
        </div>
        
        <div v-if="profile?.feeds?.length" class="feeds-grid">
          <div v-for="feed in profile.feeds" :key="feed.id" class="feed-card">
            <div class="feed-header">
              <h3>{{ feed.name }}</h3>
              <span :class="`tier-badge tier-${feed.tier}`">{{ feed.tier }}</span>
            </div>
            <div class="feed-stats">
              <div class="stat">
                <span class="label">Posts:</span>
                <span class="value">{{ feed.post_count.toLocaleString() }}</span>
              </div>
              <div class="stat">
                <span class="label">Users:</span>
                <span class="value">{{ feed.user_count.toLocaleString() }}</span>
              </div>
              <div class="stat">
                <span class="label">Achievements:</span>
                <span class="value">{{ feed.achievement_count.toLocaleString() }}</span>
              </div>
            </div>
            <div class="feed-actions">
              <button @click="viewAnalytics(feed)" class="btn-small">Analytics</button>
              <button @click="viewSettings(feed)" class="btn-small">Settings</button>
            </div>
          </div>
        </div>
        
        <div v-else class="no-feeds">
          <p>You don't have any active feeds yet.</p>
          <button @click="showNewApplication = true" class="btn-primary">Request Your First Feed</button>
        </div>
      </section>

      <!-- Applications Status -->
      <section class="applications-section">
        <h2>📝 Application Status</h2>
        <div v-if="applications.length" class="applications-list">
          <div v-for="app in applications" :key="app.id" class="application-card">
            <div class="app-header">
              <h4>Feed ID: {{ app.feed_id }}</h4>
              <span :class="`status-badge status-${app.status}`">{{ app.status }}</span>
            </div>
            <p v-if="app.description" class="app-description">{{ app.description }}</p>
            <div class="app-meta">
              <span>Applied: {{ new Date(app.applied_at).toLocaleDateString() }}</span>
              <span v-if="app.reviewed_at">
                Reviewed: {{ new Date(app.reviewed_at).toLocaleDateString() }}
              </span>
            </div>
            <p v-if="app.notes" class="app-notes">{{ app.notes }}</p>
          </div>
        </div>
        <div v-else class="no-applications">
          <p>No applications submitted yet.</p>
        </div>
      </section>
    </div>

    <!-- New Application Modal -->
    <div v-if="showNewApplication" class="modal-overlay" @click="showNewApplication = false">
      <div class="modal" @click.stop>
        <h3>Request New Feed</h3>
        <form @submit.prevent="submitApplication">
          <div class="form-group">
            <label>Feed ID:</label>
            <input v-model="newApplication.feed_id" required>
            <small>Unique identifier for your feed</small>
          </div>
          <div class="form-group">
            <label>WebSocket URL:</label>
            <input v-model="newApplication.websocket_url" required>
            <small>Your Contrails WebSocket endpoint</small>
          </div>
          <div class="form-group">
            <label>Description (optional):</label>
            <textarea v-model="newApplication.description" rows="3"></textarea>
            <small>Brief description of your feed</small>
          </div>
          <div class="form-actions">
            <button type="button" @click="showNewApplication = false">Cancel</button>
            <button type="submit" :disabled="loading">Submit Application</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Analytics Modal -->
    <div v-if="showAnalytics" class="modal-overlay" @click="showAnalytics = false">
      <div class="modal large-modal" @click.stop>
        <h3>Analytics: {{ selectedFeed?.name }}</h3>
        <div v-if="analytics" class="analytics-content">
          <div class="analytics-summary">
            <div class="summary-stat">
              <h4>{{ analytics.daily_posts.reduce((sum, day) => sum + day.posts, 0) }}</h4>
              <p>Posts ({{ analytics.period_days }} days)</p>
            </div>
            <div class="summary-stat">
              <h4>{{ analytics.top_users.length }}</h4>
              <p>Active Users</p>
            </div>
          </div>
          
          <div class="top-users">
            <h4>Top Contributors</h4>
            <div class="users-list">
              <div v-for="user in analytics.top_users" :key="user.did" class="user-item">
                <span class="user-name">{{ user.display_name || user.handle }}</span>
                <span class="user-stats">{{ user.post_count }} posts, {{ user.likes_received }} likes</span>
              </div>
            </div>
          </div>
        </div>
        <button @click="showAnalytics = false">Close</button>
      </div>
    </div>

    <!-- Settings Modal -->
    <div v-if="showSettings" class="modal-overlay" @click="showSettings = false">
      <div class="modal" @click.stop>
        <h3>Settings: {{ selectedFeed?.name }}</h3>
        <div v-if="feedSettings" class="settings-content">
          <div class="tier-info">
            <h4>Current Tier: <span :class="`tier-badge tier-${feedSettings.tier}`">{{ feedSettings.tier }}</span></h4>
          </div>
          
          <div class="features-list">
            <h4>Available Features:</h4>
            <div class="feature-item">
              <span>Custom Achievements</span>
              <span :class="feedSettings.available_features.custom_achievements ? 'available' : 'unavailable'">
                {{ feedSettings.available_features.custom_achievements ? '✅ Available' : '❌ Upgrade Required' }}
              </span>
            </div>
            <div class="feature-item">
              <span>Custom Aggregates</span>
              <span :class="feedSettings.available_features.custom_aggregates ? 'available' : 'unavailable'">
                {{ feedSettings.available_features.custom_aggregates ? '✅ Available' : '❌ Upgrade Required' }}
              </span>
            </div>
            <div class="feature-item">
              <span>Advanced Analytics</span>
              <span :class="feedSettings.available_features.advanced_analytics ? 'available' : 'unavailable'">
                {{ feedSettings.available_features.advanced_analytics ? '✅ Available' : '❌ Upgrade Required' }}
              </span>
            </div>
          </div>
          
          <p class="coming-soon">{{ feedSettings.message }}</p>
        </div>
        <button @click="showSettings = false">Close</button>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, computed } from 'vue'

export default {
  name: 'FeedmakerView',
  setup() {
    const userDid = ref('')
    const apiKey = ref('')
    const isAuthenticated = ref(false)
    const loading = ref(false)
    const profile = ref(null)
    const applications = ref([])
    
    // Modals
    const showNewApplication = ref(false)
    const showAnalytics = ref(false)
    const showSettings = ref(false)
    const selectedFeed = ref(null)
    const analytics = ref(null)
    const feedSettings = ref(null)
    
    // Forms
    const newApplication = ref({
      feed_id: '',
      websocket_url: '',
      description: ''
    })

    const apiCall = async (endpoint, options = {}) => {
      const response = await fetch(`/api/v1/feedmaker${endpoint}`, {
        headers: {
          'Authorization': `Bearer ${apiKey.value}`,
          'Content-Type': 'application/json',
          ...options.headers
        },
        ...options
      })
      
      if (!response.ok) {
        throw new Error(`API call failed: ${response.statusText}`)
      }
      
      return response.json()
    }

    const authenticate = async () => {
      if (!userDid.value || !apiKey.value) return
      
      loading.value = true
      try {
        await apiCall('/profile')
        isAuthenticated.value = true
        localStorage.setItem('feedmaker_did', userDid.value)
        localStorage.setItem('feedmaker_api_key', apiKey.value)
        await loadData()
      } catch (error) {
        alert('Authentication failed: ' + error.message)
      } finally {
        loading.value = false
      }
    }

    const logout = () => {
      isAuthenticated.value = false
      userDid.value = ''
      apiKey.value = ''
      localStorage.removeItem('feedmaker_did')
      localStorage.removeItem('feedmaker_api_key')
    }

    const loadData = async () => {
      try {
        const [profileData, applicationsData] = await Promise.all([
          apiCall('/profile'),
          apiCall('/applications')
        ])
        
        profile.value = profileData
        applications.value = applicationsData.applications
      } catch (error) {
        console.error('Failed to load data:', error)
      }
    }

    const submitApplication = async () => {
      loading.value = true
      try {
        await apiCall('/applications', {
          method: 'POST',
          body: JSON.stringify(newApplication.value)
        })
        
        showNewApplication.value = false
        newApplication.value = { feed_id: '', websocket_url: '', description: '' }
        await loadData()
        alert('Application submitted successfully!')
      } catch (error) {
        alert('Failed to submit application: ' + error.message)
      } finally {
        loading.value = false
      }
    }

    const viewAnalytics = async (feed) => {
      selectedFeed.value = feed
      loading.value = true
      try {
        analytics.value = await apiCall(`/feeds/${feed.id}/analytics`)
        showAnalytics.value = true
      } catch (error) {
        alert('Failed to load analytics: ' + error.message)
      } finally {
        loading.value = false
      }
    }

    const viewSettings = async (feed) => {
      selectedFeed.value = feed
      loading.value = true
      try {
        feedSettings.value = await apiCall(`/feeds/${feed.id}/settings`)
        showSettings.value = true
      } catch (error) {
        alert('Failed to load settings: ' + error.message)
      } finally {
        loading.value = false
      }
    }

    // Computed totals
    const totalPosts = computed(() => 
      profile.value?.feeds?.reduce((sum, feed) => sum + feed.post_count, 0) || 0
    )
    const totalUsers = computed(() => 
      profile.value?.feeds?.reduce((sum, feed) => sum + feed.user_count, 0) || 0
    )
    const totalAchievements = computed(() => 
      profile.value?.feeds?.reduce((sum, feed) => sum + feed.achievement_count, 0) || 0
    )

    onMounted(() => {
      const savedDid = localStorage.getItem('feedmaker_did')
      const savedKey = localStorage.getItem('feedmaker_api_key')
      if (savedDid && savedKey) {
        userDid.value = savedDid
        apiKey.value = savedKey
        authenticate()
      }
    })

    return {
      userDid,
      apiKey,
      isAuthenticated,
      loading,
      profile,
      applications,
      showNewApplication,
      showAnalytics,
      showSettings,
      selectedFeed,
      analytics,
      feedSettings,
      newApplication,
      totalPosts,
      totalUsers,
      totalAchievements,
      authenticate,
      logout,
      submitApplication,
      viewAnalytics,
      viewSettings
    }
  }
}
</script>

<style scoped>
.feedmaker-container {
  width: 100%;
  min-height: 100vh;
  background: #f8f9fa;
  color: #333;
}

.feedmaker-auth-bar {
  background: #34495e;
  padding: 20px 40px;
  border-bottom: 1px solid #2c3e50;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.feedmaker-auth-bar::before {
  content: '🏢 Feedmaker Dashboard';
  color: white;
  font-size: 1.5em;
  font-weight: bold;
}

.auth-form {
  display: flex;
  gap: 10px;
}

.auth-form input {
  padding: 10px 15px;
  border: 1px solid #ddd;
  border-radius: 6px;
  width: 200px;
  font-size: 14px;
}

.auth-form button, .auth-status button {
  padding: 10px 20px;
  background: #3498db;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}

.auth-status {
  display: flex;
  align-items: center;
  gap: 15px;
  color: #27ae60;
  font-weight: 500;
}

.feedmaker-content {
  padding: 40px;
  max-width: 1400px;
  margin: 0 auto;
}

.feedmaker-content section {
  background: white;
  border-radius: 8px;
  padding: 30px;
  margin-bottom: 30px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.profile-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
  margin-top: 20px;
}

.stat-card {
  background: #f8f9fa;
  padding: 20px;
  border-radius: 8px;
  text-align: center;
}

.stat-card h3 {
  font-size: 2em;
  margin: 0 0 10px 0;
  color: #2c3e50;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.feeds-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 20px;
}

.feed-card {
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 20px;
  background: #fafafa;
}

.feed-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.feed-stats {
  margin-bottom: 15px;
}

.stat {
  display: flex;
  justify-content: space-between;
  margin-bottom: 5px;
}

.feed-actions {
  display: flex;
  gap: 10px;
}

.tier-badge {
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 0.8em;
  font-weight: bold;
  text-transform: uppercase;
}

.tier-bronze { background: #cd7f32; color: white; }
.tier-silver { background: #c0c0c0; color: #333; }
.tier-gold { background: #ffd700; color: #333; }
.tier-platinum { background: #e5e4e2; color: #333; }

.applications-list {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.application-card {
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 20px;
  background: #fafafa;
}

.app-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.status-badge {
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 0.8em;
  font-weight: bold;
  text-transform: uppercase;
}

.status-pending { background: #fff3cd; color: #856404; }
.status-approved { background: #d4edda; color: #155724; }
.status-rejected { background: #f8d7da; color: #721c24; }

.btn-primary, .btn-small {
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 500;
}

.btn-primary {
  background: #3498db;
  color: white;
}

.btn-small {
  padding: 6px 12px;
  font-size: 0.9em;
  background: #6c757d;
  color: white;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  background: white;
  padding: 30px;
  border-radius: 8px;
  max-width: 500px;
  width: 90%;
  max-height: 80vh;
  overflow-y: auto;
}

.large-modal {
  max-width: 800px;
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 5px;
  font-weight: 500;
}

.form-group input, .form-group textarea, .form-group select {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.form-group small {
  color: #666;
  font-size: 0.9em;
}

.form-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

.analytics-summary {
  display: flex;
  gap: 20px;
  margin-bottom: 20px;
}

.summary-stat {
  text-align: center;
  padding: 15px;
  background: #f8f9fa;
  border-radius: 8px;
  flex: 1;
}

.users-list {
  max-height: 300px;
  overflow-y: auto;
}

.user-item {
  display: flex;
  justify-content: space-between;
  padding: 10px;
  border-bottom: 1px solid #eee;
}

.feature-item {
  display: flex;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1px solid #eee;
}

.available { color: #27ae60; }
.unavailable { color: #e74c3c; }

.coming-soon {
  text-align: center;
  color: #666;
  font-style: italic;
  margin-top: 20px;
}

.no-feeds, .no-applications {
  text-align: center;
  padding: 40px;
  color: #666;
}
</style>