<template>
  <div class="admin-container">
    <div class="admin-auth-bar">
      <div class="auth-section">
        <div v-if="!isAuthenticated" class="auth-form">
          <input 
            v-model="apiKey" 
            type="password" 
            placeholder="Enter your master admin API key"
            @keyup.enter="authenticate"
          >
          <button @click="authenticate" :disabled="loading">Login</button>
        </div>
        <div v-else class="auth-status">
          <span>✅ Authenticated as Master Admin</span>
          <button @click="logout">Logout</button>
        </div>
      </div>
    </div>

    <div v-if="isAuthenticated" class="admin-content">
      <!-- Tab Navigation -->
      <div class="tab-nav">
        <button 
          v-for="tab in tabs" 
          :key="tab.id"
          @click="activeTab = tab.id"
          :class="['tab-btn', { active: activeTab === tab.id }]"
        >
          {{ tab.label }}
        </button>
      </div>

      <!-- Tab Content -->
      <div class="tab-content">
        <!-- API Key Management Tab -->
        <div v-if="activeTab === 'api-keys'" class="tab-panel">
          <section class="api-keys-section">
            <div class="section-header">
              <h2>🔑 API Key Management</h2>
              <button @click="showCreateApiKey = true" class="btn-primary">Generate Key</button>
            </div>
            
            <div v-if="apiKeys.length" class="api-keys-table">
              <table>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Type</th>
                    <th>Owner</th>
                    <th>Expires</th>
                    <th>Status</th>
                    <th>Last Used</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="key in apiKeys" :key="key.id">
                    <td>{{ key.id }}</td>
                    <td>{{ key.key_type }}</td>
                    <td>{{ key.owner_did || 'Master Admin' }}</td>
                    <td>{{ key.expires_at ? new Date(key.expires_at).toLocaleDateString() : 'Never' }}</td>
                    <td>
                      <span :class="`status-badge ${key.is_active ? 'active' : 'inactive'}`">
                        {{ key.is_active ? 'Active' : 'Revoked' }}
                      </span>
                    </td>
                    <td>{{ key.last_used_at ? new Date(key.last_used_at).toLocaleDateString() : 'Never' }}</td>
                    <td class="actions">
                      <button v-if="key.is_active && key.key_type !== 'master_admin'" @click="revokeApiKey(key)" class="btn-small btn-danger">Revoke</button>
                      <span v-else-if="key.key_type === 'master_admin'" class="protected-key">Protected</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </div>

        <!-- Platform Stats & System Health Tab -->
        <div v-if="activeTab === 'stats'" class="tab-panel">
          <section class="stats-section">
            <h2>📊 Platform Statistics</h2>
            <div v-if="stats" class="stats-grid">
              <div class="stat-card">
                <h3>{{ stats.feeds.total }}</h3>
                <p>Total Feeds</p>
              </div>
              <div class="stat-card">
                <h3>{{ stats.users.toLocaleString() }}</h3>
                <p>Users</p>
              </div>
              <div class="stat-card">
                <h3>{{ stats.posts.toLocaleString() }}</h3>
                <p>Posts</p>
              </div>
              <div class="stat-card">
                <h3>{{ stats.achievements.toLocaleString() }}</h3>
                <p>Achievements</p>
              </div>
              <div class="stat-card">
                <h3>{{ stats.pending_applications }}</h3>
                <p>Pending Applications</p>
              </div>
            </div>
          </section>

          <section class="health-section">
            <div class="section-header">
              <h2>🔋 System Health</h2>
              <button @click="refreshHealth" class="btn-small">Refresh</button>
            </div>
            
            <div v-if="health" class="health-grid">
              <div class="health-card">
                <h4>System Status</h4>
                <span :class="`status-badge ${health.system_status === 'healthy' ? 'active' : 'inactive'}`">
                  {{ health.system_status }}
                </span>
              </div>
              <div class="health-card">
                <h4>Posts Last Hour</h4>
                <span class="health-value">{{ health.activity?.posts_last_hour || 0 }}</span>
              </div>
              <div class="health-card">
                <h4>Posts Last Day</h4>
                <span class="health-value">{{ health.activity?.posts_last_day?.toLocaleString() || 0 }}</span>
              </div>
              <div class="health-card">
                <h4>Achievements Today</h4>
                <span class="health-value">{{ health.activity?.achievements_last_day?.toLocaleString() || 0 }}</span>
              </div>
              <div class="health-card">
                <h4>Active Feeds</h4>
                <span class="health-value">{{ health.feeds?.active_count || 0 }}</span>
              </div>
              <div class="health-card">
                <h4>Last Updated</h4>
                <span class="health-time">{{ health.timestamp ? new Date(health.timestamp).toLocaleTimeString() : 'Unknown' }}</span>
              </div>
            </div>
          </section>
        </div>

        <!-- Feed Management Tab -->
        <div v-if="activeTab === 'feeds'" class="tab-panel">
          <section class="feeds-section">
            <div class="section-header">
              <h2>🎯 Feed Management</h2>
              <div class="bulk-actions" v-if="selectedFeeds.length > 0">
                <span>{{ selectedFeeds.length }} selected</span>
                <button @click="bulkUpdateTier" class="btn-small">Change Tier</button>
                <button @click="bulkToggleActive" class="btn-small">Toggle Active</button>
                <button @click="bulkDelete" class="btn-small btn-danger">Delete Selected</button>
              </div>
              <button @click="showCreateFeed = true" class="btn-primary">Add Feed</button>
            </div>
            
            <div v-if="feeds.length" class="feeds-table">
              <table>
                <thead>
                  <tr>
                    <th>
                      <input type="checkbox" @change="toggleAllFeeds" :checked="allFeedsSelected">
                    </th>
                    <th>Feed ID</th>
                    <th>Name</th>
                    <th>Owner</th>
                    <th>Tier</th>
                    <th>Posts</th>
                    <th>Users</th>
                    <th>Achievements</th>
                    <th>7d Activity</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="feed in feeds" :key="feed.id">
                    <td>
                      <input type="checkbox" :value="feed.id" v-model="selectedFeeds">
                    </td>
                    <td><code>{{ feed.id }}</code></td>
                    <td>{{ feed.name }}</td>
                    <td>{{ feed.owner_did || 'None' }}</td>
                    <td>
                      <span :class="`tier-badge tier-${feed.tier}`">
                        {{ feed.tier }}
                      </span>
                    </td>
                    <td>{{ feed.post_count?.toLocaleString() || 0 }}</td>
                    <td>{{ feed.user_count?.toLocaleString() || 0 }}</td>
                    <td>{{ feed.achievement_count?.toLocaleString() || 0 }}</td>
                    <td>{{ feed.recent_posts_7d?.toLocaleString() || 0 }}</td>
                    <td>
                      <span :class="`status-badge ${feed.is_active ? 'active' : 'inactive'}`">
                        {{ feed.is_active ? 'Active' : 'Inactive' }}
                      </span>
                    </td>
                    <td class="actions">
                      <button @click="editFeed(feed)" class="btn-small">Edit</button>
                      <button @click="deleteFeed(feed)" class="btn-small btn-danger">Delete</button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </div>

        <!-- Feed Applications Tab -->
        <div v-if="activeTab === 'applications'" class="tab-panel">
          <section class="applications-section">
            <div class="section-header">
              <h2>📝 Feed Applications</h2>
            </div>
            
            <div v-if="applications.length" class="applications-table">
              <table>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Handle</th>
                    <th>Feed ID</th>
                    <th>Status</th>
                    <th>Applied</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="app in applications" :key="app.id">
                    <td>{{ app.id }}</td>
                    <td>{{ app.applicant_handle ? `@${app.applicant_handle}` : app.applicant_did.substring(0, 20) + '...' }}</td>
                    <td><code>{{ app.feed_id }}</code></td>
                    <td>
                      <span :class="`status-badge status-${app.status}`">{{ app.status }}</span>
                    </td>
                    <td>{{ new Date(app.applied_at).toLocaleDateString() }}</td>
                    <td class="actions">
                      <button v-if="app.status === 'pending'" @click="reviewApplication(app, 'approved')" class="btn-small btn-success">Approve</button>
                      <button v-if="app.status === 'pending'" @click="reviewApplication(app, 'rejected')" class="btn-small btn-danger">Reject</button>
                      <button @click="viewApplicationDetails(app)" class="btn-small">Details</button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-else class="no-applications">
              <p>No applications submitted yet.</p>
            </div>
          </section>
        </div>

        <!-- User Management Tab -->
        <div v-if="activeTab === 'users'" class="tab-panel">
          <section class="users-section">
            <div class="section-header">
              <h2>👥 User Management</h2>
              <div class="search-box">
                <input 
                  v-model="userSearch" 
                  placeholder="Search users by handle or DID"
                  @input="searchUsers"
                >
              </div>
            </div>
            
            <div v-if="users.length" class="users-table">
              <table>
                <thead>
                  <tr>
                    <th>Handle</th>
                    <th>Display Name</th>
                    <th>Posts</th>
                    <th>Followers</th>
                    <th>Achievements</th>
                    <th>Prominent</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="user in users" :key="user.did">
                    <td>@{{ user.handle }}</td>
                    <td>{{ user.display_name || 'N/A' }}</td>
                    <td>{{ user.posts_count?.toLocaleString() || 0 }}</td>
                    <td>{{ user.followers_count?.toLocaleString() || 0 }}</td>
                    <td>{{ user.achievement_count?.toLocaleString() || 0 }}</td>
                    <td>
                      <span :class="`status-badge ${user.is_prominent ? 'active' : 'inactive'}`">
                        {{ user.is_prominent ? 'Yes' : 'No' }}
                      </span>
                    </td>
                    <td class="actions">
                      <button @click="viewUserDetails(user)" class="btn-small">Details</button>
                      <button @click="toggleProminent(user)" :class="`btn-small ${user.is_prominent ? 'btn-danger' : 'btn-success'}`">
                        {{ user.is_prominent ? 'Remove VIP' : 'Make VIP' }}
                      </button>
                      <button @click="manageAchievements(user)" class="btn-small">Achievements</button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </div>

        <!-- Geo Hashtags Config Tab -->
        <div v-if="activeTab === 'geo-config'" class="tab-panel">
          <section class="geo-config-section">
            <div class="section-header">
              <h2>🌍 Geo Hashtags Configuration</h2>
              <button @click="loadGeoConfig" class="btn-small">Refresh</button>
            </div>
            
            <!-- Add New Entry -->
            <div class="add-geo-entry">
              <h3>Add New Hashtag Mapping</h3>
              <div class="geo-form">
                <input v-model="newGeoEntry.hashtag" placeholder="Hashtag (e.g., nyc)" />
                <input v-model="newGeoEntry.city" placeholder="City (optional)" />
                <input v-model="newGeoEntry.region" placeholder="Region/State" />
                <input v-model="newGeoEntry.country" placeholder="Country" />
                <button @click="addGeoEntry" :disabled="!newGeoEntry.hashtag || !newGeoEntry.country" class="btn-primary">Add</button>
              </div>
            </div>
            
            <!-- Existing Entries -->
            <div class="geo-entries">
              <div class="search-box">
                <input v-model="geoSearch" placeholder="Search hashtags, cities, regions, or countries..." />
              </div>
              
              <div class="geo-table">
                <table>
                  <thead>
                    <tr>
                      <th>Hashtag</th>
                      <th>City</th>
                      <th>Region</th>
                      <th>Country</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(entry, hashtag) in filteredGeoEntries" :key="hashtag">
                      <td><code>{{ hashtag }}</code></td>
                      <td>{{ entry.city || '-' }}</td>
                      <td>{{ entry.region || '-' }}</td>
                      <td>{{ entry.country }}</td>
                      <td class="actions">
                        <button @click="deleteGeoEntry(hashtag)" class="btn-small btn-danger">Delete</button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </section>
        </div>

        <!-- News Domains Config Tab -->
        <div v-if="activeTab === 'domains-config'" class="tab-panel">
          <section class="domains-config-section">
            <div class="section-header">
              <h2>📰 News Domains Configuration</h2>
              <button @click="loadDomainsConfig" class="btn-small">Refresh</button>
            </div>
            
            <!-- Add New Domain -->
            <div class="add-domain">
              <h3>Add New News Domain</h3>
              <div class="domain-form">
                <input v-model="newDomain" placeholder="Domain (e.g., example.com)" />
                <button @click="addDomain" :disabled="!newDomain" class="btn-primary">Add</button>
              </div>
            </div>
            
            <!-- Existing Domains -->
            <div class="domains-list">
              <div class="search-box">
                <input v-model="domainSearch" placeholder="Search domains..." />
              </div>
              
              <div class="domains-grid">
                <div v-for="domain in filteredDomains" :key="domain" class="domain-item">
                  <span>{{ domain }}</span>
                  <button @click="deleteDomain(domain)" class="btn-small btn-danger">×</button>
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>

    <!-- Create Feed Modal -->
    <div v-if="showCreateFeed" class="modal-overlay" @click="showCreateFeed = false">
      <div class="modal" @click.stop>
        <h3>Add New Feed</h3>
        <form @submit.prevent="createFeed">
          <div class="form-group">
            <label>Feed ID:</label>
            <input v-model="newFeed.feed_id" required>
          </div>
          <div class="form-group">
            <label>WebSocket URL:</label>
            <input v-model="newFeed.websocket_url" required>
          </div>
          <div class="form-group">
            <label>Owner DID:</label>
            <input v-model="newFeed.owner_did">
          </div>
          <div class="form-group">
            <label>Tier:</label>
            <select v-model="newFeed.tier">
              <option value="bronze">Bronze</option>
              <option value="silver">Silver</option>
              <option value="gold">Gold</option>
              <option value="platinum">Platinum</option>
            </select>
          </div>
          <div class="form-actions">
            <button type="button" @click="showCreateFeed = false">Cancel</button>
            <button type="submit" :disabled="loading">Create Feed</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Create API Key Modal -->
    <div v-if="showCreateApiKey" class="modal-overlay" @click="showCreateApiKey = false">
      <div class="modal" @click.stop>
        <h3>Generate API Key</h3>
        <form @submit.prevent="createApiKey">
          <div class="form-group">
            <label>Owner DID:</label>
            <input v-model="newApiKey.owner_did" required>
          </div>
          <div class="form-group">
            <label>Expires in days (optional):</label>
            <input v-model="newApiKey.expires_days" type="number" min="1">
          </div>
          <div class="form-actions">
            <button type="button" @click="showCreateApiKey = false">Cancel</button>
            <button type="submit" :disabled="loading">Generate Key</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Bulk Tier Change Modal -->
    <div v-if="showBulkTier" class="modal-overlay" @click="showBulkTier = false">
      <div class="modal" @click.stop>
        <h3>Change Tier for {{ selectedFeeds.length }} Feeds</h3>
        <form @submit.prevent="applyBulkTier">
          <div class="form-group">
            <label>New Tier:</label>
            <select v-model="bulkTier">
              <option value="bronze">Bronze</option>
              <option value="silver">Silver</option>
              <option value="gold">Gold</option>
              <option value="platinum">Platinum</option>
            </select>
          </div>
          <div class="form-actions">
            <button type="button" @click="showBulkTier = false">Cancel</button>
            <button type="submit" :disabled="loading">Update {{ selectedFeeds.length }} Feeds</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Edit Feed Modal -->
    <div v-if="showEditFeed" class="modal-overlay" @click="showEditFeed = false">
      <div class="modal" @click.stop>
        <h3>Edit Feed: {{ editingFeed?.id }}</h3>
        <form @submit.prevent="updateFeed">
          <div class="form-group">
            <label>Owner DID:</label>
            <input v-model="editingFeed.owner_did">
          </div>
          <div class="form-group">
            <label>Tier:</label>
            <select v-model="editingFeed.tier">
              <option value="bronze">Bronze</option>
              <option value="silver">Silver</option>
              <option value="gold">Gold</option>
              <option value="platinum">Platinum</option>
            </select>
          </div>
          <div class="form-group">
            <label>
              <input type="checkbox" v-model="editingFeed.is_active">
              Active
            </label>
          </div>
          <div class="form-actions">
            <button type="button" @click="showEditFeed = false">Cancel</button>
            <button type="submit" :disabled="loading">Update Feed</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Generated API Key Display -->
    <div v-if="generatedApiKey" class="modal-overlay" @click="generatedApiKey = null">
      <div class="modal" @click.stop>
        <h3>🔑 API Key Generated</h3>
        <p><strong>⚠️ Save this key - it won't be shown again!</strong></p>
        <div class="api-key-display">
          <code>{{ generatedApiKey }}</code>
          <button @click="copyToClipboard(generatedApiKey)">Copy</button>
        </div>
        <button @click="generatedApiKey = null">Close</button>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, computed } from 'vue'

export default {
  name: 'AdminView',
  setup() {
    const apiKey = ref('')
    const isAuthenticated = ref(false)
    const loading = ref(false)
    const stats = ref(null)
    const feeds = ref([])
    const apiKeys = ref([])
    const applications = ref([])
    const users = ref([])
    const userSearch = ref('')
    const health = ref(null)
    const activeTab = ref('api-keys')
    const geoHashtags = ref({})
    const newsDomains = ref([])
    const newGeoEntry = ref({ hashtag: '', city: '', region: '', country: '' })
    const newDomain = ref('')
    const geoSearch = ref('')
    const domainSearch = ref('')
    
    const tabs = [
      { id: 'api-keys', label: '🔑 API Key Management' },
      { id: 'stats', label: '📊 Platform Statistics & System Health' },
      { id: 'feeds', label: '🎯 Feed Management' },
      { id: 'applications', label: '📝 Feed Applications' },
      { id: 'users', label: '👥 User Management' },
      { id: 'geo-config', label: '🌍 Geo Hashtags Config' },
      { id: 'domains-config', label: '📰 News Domains Config' }
    ]
    
    // Modals
    const showCreateFeed = ref(false)
    const showCreateApiKey = ref(false)
    const showEditFeed = ref(false)
    const showBulkTier = ref(false)
    const generatedApiKey = ref(null)
    const editingFeed = ref(null)
    
    // Bulk operations
    const selectedFeeds = ref([])
    const bulkTier = ref('bronze')
    
    // Forms
    const newFeed = ref({
      feed_id: '',
      websocket_url: '',
      owner_did: '',
      tier: 'bronze'
    })
    
    const newApiKey = ref({
      owner_did: '',
      expires_days: null
    })

    const apiCall = async (endpoint, options = {}) => {
      const response = await fetch(`/api/v1/admin${endpoint}`, {
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
      if (!apiKey.value) return
      
      loading.value = true
      try {
        await apiCall('/stats')
        isAuthenticated.value = true
        localStorage.setItem('admin_api_key', apiKey.value)
        await loadData()
      } catch (error) {
        alert('Authentication failed: ' + error.message)
      } finally {
        loading.value = false
      }
    }

    const logout = () => {
      isAuthenticated.value = false
      apiKey.value = ''
      localStorage.removeItem('admin_api_key')
    }

    const loadData = async () => {
      try {
        const [statsData, feedsData, keysData, appsData, usersData, healthData] = await Promise.all([
          apiCall('/stats'),
          apiCall('/feeds'),
          apiCall('/api-keys'),
          apiCall('/applications'),
          apiCall('/users?limit=20'),
          apiCall('/health')
        ])
        
        stats.value = statsData
        feeds.value = feedsData.feeds
        apiKeys.value = keysData.api_keys
        applications.value = appsData.applications
        users.value = usersData.users
        health.value = healthData
      } catch (error) {
        console.error('Failed to load data:', error)
      }
    }

    const createFeed = async () => {
      loading.value = true
      try {
        await apiCall('/feeds', {
          method: 'POST',
          body: JSON.stringify(newFeed.value)
        })
        
        showCreateFeed.value = false
        newFeed.value = { feed_id: '', websocket_url: '', owner_did: '', tier: 'bronze' }
        await loadData()
        alert('Feed created successfully!')
      } catch (error) {
        alert('Failed to create feed: ' + error.message)
      } finally {
        loading.value = false
      }
    }

    const createApiKey = async () => {
      loading.value = true
      try {
        const result = await apiCall('/api-keys', {
          method: 'POST',
          body: JSON.stringify(newApiKey.value)
        })
        
        generatedApiKey.value = result.api_key
        showCreateApiKey.value = false
        newApiKey.value = { owner_did: '', expires_days: null }
        await loadData()
      } catch (error) {
        alert('Failed to create API key: ' + error.message)
      } finally {
        loading.value = false
      }
    }

    const revokeApiKey = async (key) => {
      if (!confirm(`Revoke API key for ${key.owner_did || 'Master Admin'}?`)) return
      
      try {
        await apiCall(`/api-keys/${key.id}`, { method: 'DELETE' })
        await loadData()
      } catch (error) {
        alert('Failed to revoke API key: ' + error.message)
      }
    }

    const editFeed = (feed) => {
      editingFeed.value = { ...feed }
      showEditFeed.value = true
    }

    const updateFeed = async () => {
      loading.value = true
      try {
        await apiCall(`/feeds/${editingFeed.value.id}`, {
          method: 'PUT',
          body: JSON.stringify({
            owner_did: editingFeed.value.owner_did,
            tier: editingFeed.value.tier,
            is_active: editingFeed.value.is_active
          })
        })
        
        showEditFeed.value = false
        editingFeed.value = null
        await loadData()
        alert('Feed updated successfully!')
      } catch (error) {
        alert('Failed to update feed: ' + error.message)
      } finally {
        loading.value = false
      }
    }

    const deleteFeed = async (feed) => {
      const action = confirm('Choose deletion type:\nOK = Soft delete (deactivate)\nCancel = Hard delete (permanent)')
      const hardDelete = !action
      
      if (!confirm(`${hardDelete ? 'Permanently delete' : 'Deactivate'} feed ${feed.name}?`)) return
      
      try {
        await apiCall(`/feeds/${feed.id}?hard_delete=${hardDelete}`, {
          method: 'DELETE'
        })
        await loadData()
        alert(`Feed ${hardDelete ? 'permanently deleted' : 'deactivated'} successfully!`)
      } catch (error) {
        alert('Failed to delete feed: ' + error.message)
      }
    }

    const copyToClipboard = (text) => {
      navigator.clipboard.writeText(text)
      alert('Copied to clipboard!')
    }

    onMounted(() => {
      const savedKey = localStorage.getItem('admin_api_key')
      if (savedKey) {
        apiKey.value = savedKey
        authenticate()
      }
    })

    return {
      apiKey,
      isAuthenticated,
      loading,
      stats,
      feeds,
      apiKeys,
      applications,
      users,
      userSearch,
      health,
      activeTab,
      tabs,
      showCreateFeed,
      showCreateApiKey,
      showEditFeed,
      generatedApiKey,
      newFeed,
      newApiKey,
      editingFeed,
      authenticate,
      logout,
      createFeed,
      createApiKey,
      updateFeed,
      revokeApiKey,
      editFeed,
      deleteFeed,
      copyToClipboard,
      
      // Bulk operations
      selectedFeeds,
      showBulkTier,
      bulkTier,
      toggleAllFeeds: () => {
        if (selectedFeeds.value.length === feeds.value.length) {
          selectedFeeds.value = []
        } else {
          selectedFeeds.value = feeds.value.map(f => f.id)
        }
      },
      allFeedsSelected: computed(() => selectedFeeds.value.length === feeds.value.length && feeds.value.length > 0),
      bulkUpdateTier: () => { showBulkTier.value = true },
      applyBulkTier: async () => {
        loading.value = true
        try {
          await Promise.all(selectedFeeds.value.map(feedId => 
            apiCall(`/feeds/${feedId}`, {
              method: 'PUT',
              body: JSON.stringify({ tier: bulkTier.value })
            })
          ))
          showBulkTier.value = false
          selectedFeeds.value = []
          await loadData()
        } catch (error) {
          alert('Failed to update feeds: ' + error.message)
        } finally {
          loading.value = false
        }
      },
      bulkToggleActive: async () => {
        if (!confirm(`Toggle active status for ${selectedFeeds.value.length} feeds?`)) return
        loading.value = true
        try {
          await Promise.all(selectedFeeds.value.map(feedId => {
            const feed = feeds.value.find(f => f.id === feedId)
            return apiCall(`/feeds/${feedId}`, {
              method: 'PUT',
              body: JSON.stringify({ is_active: !feed.is_active })
            })
          }))
          selectedFeeds.value = []
          await loadData()
        } catch (error) {
          alert('Failed to toggle feeds: ' + error.message)
        } finally {
          loading.value = false
        }
      },
      bulkDelete: async () => {
        if (!confirm(`Delete ${selectedFeeds.value.length} selected feeds?`)) return
        loading.value = true
        try {
          await Promise.all(selectedFeeds.value.map(feedId => 
            apiCall(`/feeds/${feedId}`, { method: 'DELETE' })
          ))
          selectedFeeds.value = []
          await loadData()
        } catch (error) {
          alert('Failed to delete feeds: ' + error.message)
        } finally {
          loading.value = false
        }
      },
      
      // Application management
      reviewApplication: async (app, status) => {
        const notes = prompt(`${status === 'approved' ? 'Approve' : 'Reject'} application for ${app.feed_id}. Add notes (optional):`) || ''
        try {
          await apiCall(`/applications/${app.id}`, {
            method: 'PUT',
            body: JSON.stringify({ status, notes, tier: 'bronze' })
          })
          await loadData()
          alert(`Application ${status}!`)
        } catch (error) {
          alert('Failed to review application: ' + error.message)
        }
      },
      viewApplicationDetails: (app) => {
        alert(`Application Details:\n\nID: ${app.id}\nDID: ${app.applicant_did}\nHandle: ${app.applicant_handle || 'Not provided'}\nFeed ID: ${app.feed_id}\nWebSocket: ${app.websocket_url}\n\nDescription:\n${app.description}\n\nNotes: ${app.notes || 'None'}`)
      },
      
      // User management
      searchUsers: async () => {
        try {
          const usersData = await apiCall(`/users?limit=50&search=${encodeURIComponent(userSearch.value)}`)
          users.value = usersData.users
        } catch (error) {
          console.error('Failed to search users:', error)
        }
      },
      viewUserDetails: async (user) => {
        try {
          const details = await apiCall(`/users/${encodeURIComponent(user.did)}/details`)
          const achievementText = details.recent_achievements.length > 0 
            ? details.recent_achievements.slice(0, 5).map(a => `- Achievement ${a.achievement_id} in feed ${a.feed_id}`).join('\n')
            : 'No recent achievements'
          
          alert(`User Details:\n\nHandle: @${user.handle}\nDisplay Name: ${user.display_name || 'N/A'}\nDID: ${user.did}\nPosts: ${user.posts_count}\nFollowers: ${user.followers_count}\nAchievements: ${user.achievement_count}\nProminent: ${user.is_prominent ? 'Yes' : 'No'}\n\nRecent Achievements:\n${achievementText}`)
        } catch (error) {
          alert('Failed to load user details: ' + error.message)
        }
      },
      toggleProminent: async (user) => {
        const action = user.is_prominent ? 'remove from VIP' : 'make VIP'
        if (!confirm(`${action.charAt(0).toUpperCase() + action.slice(1)} user @${user.handle}?`)) return
        
        try {
          await apiCall(`/users/${encodeURIComponent(user.did)}/prominent?prominent=${!user.is_prominent}`, {
            method: 'PUT'
          })
          await loadData()
          alert(`User ${user.is_prominent ? 'removed from VIP' : 'marked as VIP'}!`)
        } catch (error) {
          alert('Failed to update user status: ' + error.message)
        }
      },
      manageAchievements: async (user) => {
        const action = prompt(`Achievement Management for @${user.handle}:\n\n1. Type 'clear' to clear all achievements\n2. Type a feed ID to clear achievements for that feed only\n3. Cancel to do nothing\n\nEnter your choice:`)
        
        if (!action) return
        
        if (action.toLowerCase() === 'clear') {
          if (!confirm(`Clear ALL achievements for @${user.handle}? This cannot be undone!`)) return
          
          try {
            const result = await apiCall(`/users/${encodeURIComponent(user.did)}/achievements`, {
              method: 'DELETE'
            })
            await loadData()
            alert(`Cleared ${result.deleted_count} achievements for user!`)
          } catch (error) {
            alert('Failed to clear achievements: ' + error.message)
          }
        } else {
          // Assume it's a feed ID
          if (!confirm(`Clear achievements for @${user.handle} in feed ${action}?`)) return
          
          try {
            const result = await apiCall(`/users/${encodeURIComponent(user.did)}/achievements?feed_id=${action}`, {
              method: 'DELETE'
            })
            await loadData()
            alert(`Cleared ${result.deleted_count} achievements for user in feed ${action}!`)
          } catch (error) {
            alert('Failed to clear achievements: ' + error.message)
          }
        }
      },
      
      // System health
      refreshHealth: async () => {
        try {
          health.value = await apiCall('/health')
        } catch (error) {
          alert('Failed to refresh health data: ' + error.message)
        }
      },
      
      // Configuration management
      loadGeoConfig: async () => {
        try {
          const response = await fetch('/config/geo_hashtags_mapping.json')
          geoHashtags.value = await response.json()
        } catch (error) {
          alert('Failed to load geo config: ' + error.message)
        }
      },
      
      loadDomainsConfig: async () => {
        try {
          const response = await fetch('/config/news_domains.json')
          newsDomains.value = await response.json()
        } catch (error) {
          alert('Failed to load domains config: ' + error.message)
        }
      },
      
      addGeoEntry: async () => {
        const hashtag = newGeoEntry.value.hashtag.toLowerCase().replace(/[^a-z0-9]/g, '')
        if (!hashtag) return
        
        geoHashtags.value[hashtag] = {
          city: newGeoEntry.value.city || null,
          region: newGeoEntry.value.region || null,
          country: newGeoEntry.value.country
        }
        
        await saveGeoConfig()
        newGeoEntry.value = { hashtag: '', city: '', region: '', country: '' }
      },
      
      deleteGeoEntry: async (hashtag) => {
        if (!confirm(`Delete hashtag mapping for "${hashtag}"?`)) return
        delete geoHashtags.value[hashtag]
        await saveGeoConfig()
      },
      
      addDomain: async () => {
        const domain = newDomain.value.toLowerCase().replace(/^https?:\/\//, '').replace(/\/$/, '')
        if (!domain || newsDomains.value.includes(domain)) return
        
        newsDomains.value.push(domain)
        newsDomains.value.sort()
        await saveDomainsConfig()
        newDomain.value = ''
      },
      
      deleteDomain: async (domain) => {
        if (!confirm(`Remove "${domain}" from news domains?`)) return
        newsDomains.value = newsDomains.value.filter(d => d !== domain)
        await saveDomainsConfig()
      },
      
      // Computed properties
      filteredGeoEntries: computed(() => {
        if (!geoSearch.value) return geoHashtags.value
        const search = geoSearch.value.toLowerCase()
        return Object.fromEntries(
          Object.entries(geoHashtags.value).filter(([hashtag, entry]) => 
            hashtag.includes(search) ||
            (entry.city && entry.city.toLowerCase().includes(search)) ||
            (entry.region && entry.region.toLowerCase().includes(search)) ||
            entry.country.toLowerCase().includes(search)
          )
        )
      }),
      
      filteredDomains: computed(() => {
        if (!domainSearch.value) return newsDomains.value
        const search = domainSearch.value.toLowerCase()
        return newsDomains.value.filter(domain => domain.includes(search))
      }),
      
      geoSearch,
      domainSearch,
      geoHashtags,
      newsDomains,
      newGeoEntry,
      newDomain
    }
    

    
    onMounted(() => {
      const savedKey = localStorage.getItem('admin_api_key')
      if (savedKey) {
        apiKey.value = savedKey
        authenticate()
      }
    })

    return {
      apiKey,
      isAuthenticated,
      loading,
      stats,
      feeds,
      apiKeys,
      applications,
      users,
      userSearch,
      health,
      activeTab,
      tabs,
      showCreateFeed,
      showCreateApiKey,
      showEditFeed,
      generatedApiKey,
      newFeed,
      newApiKey,
      editingFeed,
      authenticate,
      logout,
      createFeed,
      createApiKey,
      updateFeed,
      revokeApiKey,
      editFeed,
      deleteFeed,
      copyToClipboard,
      
      // Bulk operations
      selectedFeeds,
      showBulkTier,
      bulkTier,
      toggleAllFeeds: () => {
        if (selectedFeeds.value.length === feeds.value.length) {
          selectedFeeds.value = []
        } else {
          selectedFeeds.value = feeds.value.map(f => f.id)
        }
      },
      allFeedsSelected: computed(() => selectedFeeds.value.length === feeds.value.length && feeds.value.length > 0),
      bulkUpdateTier: () => { showBulkTier.value = true },
      applyBulkTier: async () => {
        loading.value = true
        try {
          await Promise.all(selectedFeeds.value.map(feedId => 
            apiCall(`/feeds/${feedId}`, {
              method: 'PUT',
              body: JSON.stringify({ tier: bulkTier.value })
            })
          ))
          showBulkTier.value = false
          selectedFeeds.value = []
          await loadData()
        } catch (error) {
          alert('Failed to update feeds: ' + error.message)
        } finally {
          loading.value = false
        }
      },
      bulkToggleActive: async () => {
        if (!confirm(`Toggle active status for ${selectedFeeds.value.length} feeds?`)) return
        loading.value = true
        try {
          await Promise.all(selectedFeeds.value.map(feedId => {
            const feed = feeds.value.find(f => f.id === feedId)
            return apiCall(`/feeds/${feedId}`, {
              method: 'PUT',
              body: JSON.stringify({ is_active: !feed.is_active })
            })
          }))
          selectedFeeds.value = []
          await loadData()
        } catch (error) {
          alert('Failed to toggle feeds: ' + error.message)
        } finally {
          loading.value = false
        }
      },
      bulkDelete: async () => {
        if (!confirm(`Delete ${selectedFeeds.value.length} selected feeds?`)) return
        loading.value = true
        try {
          await Promise.all(selectedFeeds.value.map(feedId => 
            apiCall(`/feeds/${feedId}`, { method: 'DELETE' })
          ))
          selectedFeeds.value = []
          await loadData()
        } catch (error) {
          alert('Failed to delete feeds: ' + error.message)
        } finally {
          loading.value = false
        }
      },
      
      // Application management
      reviewApplication: async (app, status) => {
        const notes = prompt(`${status === 'approved' ? 'Approve' : 'Reject'} application for ${app.feed_id}. Add notes (optional):`) || ''
        try {
          await apiCall(`/applications/${app.id}`, {
            method: 'PUT',
            body: JSON.stringify({ status, notes, tier: 'bronze' })
          })
          await loadData()
          alert(`Application ${status}!`)
        } catch (error) {
          alert('Failed to review application: ' + error.message)
        }
      },
      viewApplicationDetails: (app) => {
        alert(`Application Details:\n\nID: ${app.id}\nDID: ${app.applicant_did}\nHandle: ${app.applicant_handle || 'Not provided'}\nFeed ID: ${app.feed_id}\nWebSocket: ${app.websocket_url}\n\nDescription:\n${app.description}\n\nNotes: ${app.notes || 'None'}`)
      },
      
      // User management
      searchUsers: async () => {
        try {
          const usersData = await apiCall(`/users?limit=50&search=${encodeURIComponent(userSearch.value)}`)
          users.value = usersData.users
        } catch (error) {
          console.error('Failed to search users:', error)
        }
      },
      viewUserDetails: async (user) => {
        try {
          const details = await apiCall(`/users/${encodeURIComponent(user.did)}/details`)
          const achievementText = details.recent_achievements.length > 0 
            ? details.recent_achievements.slice(0, 5).map(a => `- Achievement ${a.achievement_id} in feed ${a.feed_id}`).join('\n')
            : 'No recent achievements'
          
          alert(`User Details:\n\nHandle: @${user.handle}\nDisplay Name: ${user.display_name || 'N/A'}\nDID: ${user.did}\nPosts: ${user.posts_count}\nFollowers: ${user.followers_count}\nAchievements: ${user.achievement_count}\nProminent: ${user.is_prominent ? 'Yes' : 'No'}\n\nRecent Achievements:\n${achievementText}`)
        } catch (error) {
          alert('Failed to load user details: ' + error.message)
        }
      },
      toggleProminent: async (user) => {
        const action = user.is_prominent ? 'remove from VIP' : 'make VIP'
        if (!confirm(`${action.charAt(0).toUpperCase() + action.slice(1)} user @${user.handle}?`)) return
        
        try {
          await apiCall(`/users/${encodeURIComponent(user.did)}/prominent?prominent=${!user.is_prominent}`, {
            method: 'PUT'
          })
          await loadData()
          alert(`User ${user.is_prominent ? 'removed from VIP' : 'marked as VIP'}!`)
        } catch (error) {
          alert('Failed to update user status: ' + error.message)
        }
      },
      manageAchievements: async (user) => {
        const action = prompt(`Achievement Management for @${user.handle}:\n\n1. Type 'clear' to clear all achievements\n2. Type a feed ID to clear achievements for that feed only\n3. Cancel to do nothing\n\nEnter your choice:`)
        
        if (!action) return
        
        if (action.toLowerCase() === 'clear') {
          if (!confirm(`Clear ALL achievements for @${user.handle}? This cannot be undone!`)) return
          
          try {
            const result = await apiCall(`/users/${encodeURIComponent(user.did)}/achievements`, {
              method: 'DELETE'
            })
            await loadData()
            alert(`Cleared ${result.deleted_count} achievements for user!`)
          } catch (error) {
            alert('Failed to clear achievements: ' + error.message)
          }
        } else {
          // Assume it's a feed ID
          if (!confirm(`Clear achievements for @${user.handle} in feed ${action}?`)) return
          
          try {
            const result = await apiCall(`/users/${encodeURIComponent(user.did)}/achievements?feed_id=${action}`, {
              method: 'DELETE'
            })
            await loadData()
            alert(`Cleared ${result.deleted_count} achievements for user in feed ${action}!`)
          } catch (error) {
            alert('Failed to clear achievements: ' + error.message)
          }
        }
      },
      
      // System health
      refreshHealth: async () => {
        try {
          health.value = await apiCall('/health')
        } catch (error) {
          alert('Failed to refresh health data: ' + error.message)
        }
      },
      
      // Configuration management
      loadGeoConfig: async () => {
        try {
          const response = await fetch('/config/geo_hashtags_mapping.json')
          geoHashtags.value = await response.json()
        } catch (error) {
          alert('Failed to load geo config: ' + error.message)
        }
      },
      
      loadDomainsConfig: async () => {
        try {
          const response = await fetch('/config/news_domains.json')
          newsDomains.value = await response.json()
        } catch (error) {
          alert('Failed to load domains config: ' + error.message)
        }
      },
      
      addGeoEntry: async () => {
        const hashtag = newGeoEntry.value.hashtag.toLowerCase().replace(/[^a-z0-9]/g, '')
        if (!hashtag) return
        
        geoHashtags.value[hashtag] = {
          city: newGeoEntry.value.city || null,
          region: newGeoEntry.value.region || null,
          country: newGeoEntry.value.country
        }
        
        await saveGeoConfig()
        newGeoEntry.value = { hashtag: '', city: '', region: '', country: '' }
      },
      
      deleteGeoEntry: async (hashtag) => {
        if (!confirm(`Delete hashtag mapping for "${hashtag}"?`)) return
        delete geoHashtags.value[hashtag]
        await saveGeoConfig()
      },
      
      addDomain: async () => {
        const domain = newDomain.value.toLowerCase().replace(/^https?:\/\//, '').replace(/\/$/, '')
        if (!domain || newsDomains.value.includes(domain)) return
        
        newsDomains.value.push(domain)
        newsDomains.value.sort()
        await saveDomainsConfig()
        newDomain.value = ''
      },
      
      deleteDomain: async (domain) => {
        if (!confirm(`Remove "${domain}" from news domains?`)) return
        newsDomains.value = newsDomains.value.filter(d => d !== domain)
        await saveDomainsConfig()
      },
      
      // Computed properties
      filteredGeoEntries: computed(() => {
        if (!geoSearch.value) return geoHashtags.value
        const search = geoSearch.value.toLowerCase()
        return Object.fromEntries(
          Object.entries(geoHashtags.value).filter(([hashtag, entry]) => 
            hashtag.includes(search) ||
            (entry.city && entry.city.toLowerCase().includes(search)) ||
            (entry.region && entry.region.toLowerCase().includes(search)) ||
            entry.country.toLowerCase().includes(search)
          )
        )
      }),
      
      filteredDomains: computed(() => {
        if (!domainSearch.value) return newsDomains.value
        const search = domainSearch.value.toLowerCase()
        return newsDomains.value.filter(domain => domain.includes(search))
      }),
      
      geoSearch,
      domainSearch,
      geoHashtags,
      newsDomains,
      newGeoEntry,
      newDomain
    }
  }
}
</script>

<style scoped>
.admin-container {
  width: 100%;
  min-height: 100vh;
  background: #f8f9fa;
  padding: 0;
  margin: 0;
  color: #333;
}

.admin-auth-bar {
  background: #2c3e50;
  padding: 20px 40px;
  border-bottom: 1px solid #34495e;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.admin-auth-bar::before {
  content: '🛠️ Feedmaster Admin';
  color: white;
  font-size: 1.5em;
  font-weight: bold;
}

.admin-content {
  padding: 40px;
  max-width: 1400px;
  margin: 0 auto;
}

.tab-nav {
  display: flex;
  border-bottom: 2px solid #e0e0e0;
  margin-bottom: 30px;
  gap: 0;
}

.tab-btn {
  padding: 15px 25px;
  border: none;
  background: #f8f9fa;
  color: #666;
  cursor: pointer;
  border-radius: 8px 8px 0 0;
  font-weight: 500;
  transition: all 0.2s;
  border-bottom: 3px solid transparent;
}

.tab-btn:hover {
  background: #e9ecef;
  color: #333;
}

.tab-btn.active {
  background: white;
  color: #2c3e50;
  border-bottom: 3px solid #3498db;
  font-weight: 600;
}

.tab-content {
  min-height: 500px;
}

.tab-panel section {
  background: white;
  border-radius: 8px;
  padding: 30px;
  margin-bottom: 30px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.auth-form {
  display: flex;
  gap: 10px;
}

.auth-form input {
  padding: 10px 15px;
  border: 1px solid #ddd;
  border-radius: 6px;
  width: 350px;
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

.protected-key {
  color: #7f8c8d;
  font-style: italic;
  font-size: 0.9em;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
  margin-bottom: 30px;
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
  flex-wrap: wrap;
  gap: 15px;
}

.bulk-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 15px;
  background: #e3f2fd;
  border-radius: 6px;
  border: 1px solid #2196f3;
}

.bulk-actions span {
  font-weight: 500;
  color: #1976d2;
}

.search-box {
  display: flex;
  align-items: center;
}

.search-box input {
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  width: 300px;
  font-size: 14px;
}

.users-table {
  overflow-x: auto;
}

.health-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 15px;
}

.health-card {
  background: #f8f9fa;
  padding: 15px;
  border-radius: 8px;
  text-align: center;
  border-left: 4px solid #3498db;
}

.health-card h4 {
  margin: 0 0 10px 0;
  color: #2c3e50;
  font-size: 0.9em;
}

.health-value {
  font-size: 1.5em;
  font-weight: bold;
  color: #27ae60;
}

.health-time {
  font-size: 0.9em;
  color: #666;
}

.feeds-table, .api-keys-table {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  background: white;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

th, td {
  padding: 12px;
  text-align: left;
  border-bottom: 1px solid #e0e0e0;
  color: #2c3e50;
}

th {
  background: #ecf0f1;
  font-weight: 600;
  color: #2c3e50;
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

.status-badge {
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 0.8em;
  font-weight: bold;
}

.status-badge.active { background: #d4edda; color: #155724; }
.status-badge.inactive { background: #f8d7da; color: #721c24; }
.status-pending { background: #fff3cd; color: #856404; }
.status-approved { background: #d4edda; color: #155724; }
.status-rejected { background: #f8d7da; color: #721c24; }

.btn-success {
  background: #28a745;
  color: white;
}

.no-applications {
  text-align: center;
  padding: 40px;
  color: #666;
}

.actions {
  display: flex;
  gap: 8px;
}

.btn-primary, .btn-small, .btn-danger {
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 500;
}

.btn-primary {
  background: #007bff;
  color: white;
}

.btn-small {
  padding: 4px 8px;
  font-size: 0.8em;
  background: #6c757d;
  color: white;
}

.btn-danger {
  background: #dc3545;
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
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 5px;
  font-weight: 500;
}

.form-group input, .form-group select {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.form-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

.api-key-display {
  display: flex;
  gap: 10px;
  align-items: center;
  margin: 20px 0;
  padding: 15px;
  background: #f8f9fa;
  border-radius: 4px;
}

.api-key-display code {
  flex: 1;
  font-family: monospace;
  font-size: 0.9em;
  word-break: break-all;
}

/* Configuration tabs styles */
.geo-form, .domain-form {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.geo-form input, .domain-form input {
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
}

.geo-form input:first-child {
  min-width: 120px;
}

.geo-table {
  overflow-x: auto;
}

.domains-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 10px;
  margin-top: 15px;
}

.domain-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #f8f9fa;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  font-family: monospace;
  font-size: 0.9em;
}

.domain-item button {
  margin-left: 10px;
  padding: 2px 6px;
  font-size: 12px;
}

.add-geo-entry, .add-domain {
  background: #f8f9fa;
  padding: 20px;
  border-radius: 8px;
  margin-bottom: 30px;
}

.add-geo-entry h3, .add-domain h3 {
  margin: 0 0 15px 0;
  color: #2c3e50;
}
</style>