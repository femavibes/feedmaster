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
    const activeTab = ref('api-keys')
    const apiKeys = ref([])
    const geoHashtags = ref({})
    const newsDomains = ref([])
    const newGeoEntry = ref({ hashtag: '', city: '', region: '', country: '' })
    const newDomain = ref('')
    const geoSearch = ref('')
    const domainSearch = ref('')
    const showCreateApiKey = ref(false)
    const generatedApiKey = ref(null)
    const newApiKey = ref({ owner_did: '', expires_days: null })
    
    const tabs = [
      { id: 'api-keys', label: '🔑 API Key Management' },
      { id: 'geo-config', label: '🌍 Geo Hashtags Config' },
      { id: 'domains-config', label: '📰 News Domains Config' }
    ]

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

    const revokeApiKey = async (key) => {
      if (!confirm(`Revoke API key for ${key.owner_did || 'Master Admin'}?`)) return
      
      try {
        await apiCall(`/api-keys/${key.id}`, { method: 'DELETE' })
        const keysData = await apiCall('/api-keys')
        apiKeys.value = keysData.api_keys
      } catch (error) {
        alert('Failed to revoke API key: ' + error.message)
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
        const keysData = await apiCall('/api-keys')
        apiKeys.value = keysData.api_keys
      } catch (error) {
        alert('Failed to create API key: ' + error.message)
      } finally {
        loading.value = false
      }
    }

    // Configuration management
    const loadGeoConfig = async () => {
      try {
        geoHashtags.value = await apiCall('/config/geo-hashtags')
      } catch (error) {
        alert('Failed to load geo config: ' + error.message)
      }
    }
    
    const loadDomainsConfig = async () => {
      try {
        newsDomains.value = await apiCall('/config/news-domains')
      } catch (error) {
        alert('Failed to load domains config: ' + error.message)
      }
    }
    
    const addGeoEntry = async () => {
      const hashtag = newGeoEntry.value.hashtag.toLowerCase().replace(/[^a-z0-9]/g, '')
      if (!hashtag) return
      
      try {
        await apiCall('/config/geo-hashtags', {
          method: 'POST',
          body: JSON.stringify({
            hashtag,
            city: newGeoEntry.value.city || null,
            region: newGeoEntry.value.region || null,
            country: newGeoEntry.value.country
          })
        })
        await loadGeoConfig()
        newGeoEntry.value = { hashtag: '', city: '', region: '', country: '' }
      } catch (error) {
        alert('Failed to add geo entry: ' + error.message)
      }
    }
    
    const deleteGeoEntry = async (hashtag) => {
      if (!confirm(`Delete hashtag mapping for "${hashtag}"?`)) return
      try {
        await apiCall(`/config/geo-hashtags/${hashtag}`, { method: 'DELETE' })
        await loadGeoConfig()
      } catch (error) {
        alert('Failed to delete geo entry: ' + error.message)
      }
    }
    
    const addDomain = async () => {
      const domain = newDomain.value.toLowerCase().replace(/^https?:\/\//, '').replace(/\/$/, '')
      if (!domain || newsDomains.value.includes(domain)) return
      
      try {
        await apiCall('/config/news-domains', {
          method: 'POST',
          body: JSON.stringify({ domain })
        })
        await loadDomainsConfig()
        newDomain.value = ''
      } catch (error) {
        alert('Failed to add domain: ' + error.message)
      }
    }
    
    const deleteDomain = async (domain) => {
      if (!confirm(`Remove "${domain}" from news domains?`)) return
      try {
        await apiCall(`/config/news-domains/${domain}`, { method: 'DELETE' })
        await loadDomainsConfig()
      } catch (error) {
        alert('Failed to delete domain: ' + error.message)
      }
    }

    const filteredGeoEntries = computed(() => {
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
    })
    
    const filteredDomains = computed(() => {
      if (!domainSearch.value) return newsDomains.value
      const search = domainSearch.value.toLowerCase()
      return newsDomains.value.filter(domain => domain.includes(search))
    })

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
      activeTab,
      tabs,
      apiKeys,
      showCreateApiKey,
      generatedApiKey,
      newApiKey,
      geoHashtags,
      newsDomains,
      newGeoEntry,
      newDomain,
      geoSearch,
      domainSearch,
      authenticate,
      logout,
      revokeApiKey,
      createApiKey,
      loadGeoConfig,
      loadDomainsConfig,
      addGeoEntry,
      deleteGeoEntry,
      addDomain,
      deleteDomain,
      filteredGeoEntries,
      filteredDomains
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

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.btn-primary, .btn-small {
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

.search-box input {
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  width: 300px;
  font-size: 14px;
}

.geo-table {
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

.actions {
  display: flex;
  gap: 8px;
}

.status-badge {
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 0.8em;
  font-weight: bold;
}

.status-badge.active { background: #d4edda; color: #155724; }
.status-badge.inactive { background: #f8d7da; color: #721c24; }

.protected-key {
  color: #7f8c8d;
  font-style: italic;
  font-size: 0.9em;
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
</style>