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
              <button @click="openCreateApiKey" class="btn-primary">Generate Key</button>
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
                      <button v-if="key.key_type === 'feed_owner'" @click="editApiKeyPermissions(key)" class="btn-small">Edit Permissions</button>
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
              <button @click="openCreateFeed" class="btn-primary">Add Feed</button>
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
                      <button v-if="feed.is_active" @click="toggleFeedActive(feed, false)" class="btn-small btn-warning">Deactivate</button>
                      <button v-else @click="toggleFeedActive(feed, true)" class="btn-small btn-success">Activate</button>
                      <button @click="hardDeleteFeed(feed)" class="btn-small btn-danger">Delete Forever</button>
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
              <div class="header-controls">
                <div class="view-toggle">
                  <button @click="geoViewMode = 'tree'" :class="['btn-small', { active: geoViewMode === 'tree' }]">🌳 Tree View</button>
                  <button @click="geoViewMode = 'table'" :class="['btn-small', { active: geoViewMode === 'table' }]">📋 Table View</button>
                </div>
                <button @click="loadGeoConfig" class="btn-small">Refresh</button>
                <button @click="copyPublicUrl" class="btn-small">📋 Copy Public URL</button>
              </div>
            </div>
            
            <!-- Stats Bar -->
            <div class="geo-stats">
              <div class="stat-item">
                <strong>{{ Object.keys(geoHashtags).length }}</strong> hashtags
              </div>
              <div class="stat-item">
                <strong>{{ geoHierarchy.countries.length }}</strong> countries
              </div>
              <div class="stat-item">
                <strong>{{ Object.values(geoHierarchy.regions).reduce((sum, regions) => sum + regions.length, 0) }}</strong> regions
              </div>
              <div class="stat-item">
                <strong>{{ Object.values(geoHierarchy.cities).reduce((sum, cities) => sum + cities.length, 0) }}</strong> cities
              </div>
            </div>
            
            <!-- Add New Entry -->
            <div class="add-geo-entry">
              <h3>Add New Hashtag Mapping</h3>
              <div class="geo-form">
                <input v-model="newGeoEntry.hashtag" placeholder="Hashtag (e.g., nyc)" />
                <input v-model="newGeoEntry.city" placeholder="City (optional)" />
                <input v-model="newGeoEntry.region" placeholder="Region/State (optional)" />
                <input v-model="newGeoEntry.country" placeholder="Country" />
                <button @click="addGeoEntry" :disabled="!newGeoEntry.hashtag || !newGeoEntry.country" class="btn-primary">Add</button>
              </div>
              <div class="form-help">
                <small>Leave city blank for region-level hashtags. Leave both city and region blank for country-level hashtags.</small>
              </div>
            </div>
            
            <!-- Search and Filter -->
            <div class="geo-controls">
              <div class="search-box">
                <input v-model="geoSearch" placeholder="Search hashtags, cities, regions, or countries..." />
              </div>
              <div class="bulk-actions" v-if="selectedHashtags.length > 0">
                <span>{{ selectedHashtags.length }} selected</span>
                <button @click="bulkDeleteHashtags" class="btn-small btn-danger">Delete Selected</button>
                <button @click="selectedHashtags = []" class="btn-small">Clear Selection</button>
              </div>
            </div>
            
            <!-- Tree View -->
            <div v-if="geoViewMode === 'tree'" class="geo-tree">
              <div v-for="country in filteredHierarchy.countries" :key="country" class="country-node">
                <div class="node-header" @click="toggleCountry(country)" style="cursor: pointer;">
                  <span class="expand-icon">{{ expandedCountries.includes(country) ? '▼' : '▶' }}</span>
                  <span class="flag">{{ getCountryFlag(country) }}</span>
                  <strong>{{ country }}</strong>
                  <span class="count">({{ getCountryHashtagCount(country) }} hashtags)</span>
                  <div class="node-actions">
                    <button @click.stop="selectAllInCountry(country)" class="btn-tiny">Select All</button>
                  </div>
                </div>
                
                <div v-if="expandedCountries.includes(country)" class="country-content">
                  <!-- Country-level hashtags -->
                  <div class="hashtags-section">
                    <div v-if="getCountryOnlyHashtags(country).length > 0">
                      <div class="section-title">Country-level hashtags:</div>
                      <div class="hashtags-list">
                        <div v-for="hashtag in getCountryOnlyHashtags(country)" :key="hashtag" class="hashtag-item">
                          <input type="checkbox" :value="hashtag" v-model="selectedHashtags" />
                          <code>{{ hashtag }}</code>
                          <button @click="deleteGeoEntry(hashtag)" class="btn-tiny btn-danger">×</button>
                        </div>
                      </div>
                    </div>
                    <div class="add-inline">
                      <input v-model="inlineAdd.country[country]" :placeholder="`Add hashtag for ${country}`" @keyup.enter="addInlineHashtag(country, null, null)" />
                      <button @click="addInlineHashtag(country, null, null)" class="btn-tiny">+</button>
                    </div>
                  </div>
                  
                  <!-- Regions -->
                  <div v-for="region in getCountryRegions(country)" :key="region" class="region-node">
                    <div class="node-header" @click.prevent="toggleRegion(country, region)">
                      <span class="expand-icon">{{ expandedRegions.includes(`${country}:${region}`) ? '▼' : '▶' }}</span>
                      <span class="region-name">{{ region }}</span>
                      <span class="count">({{ getRegionHashtagCount(country, region) }} hashtags)</span>
                      <div class="node-actions">
                        <button @click.stop="selectAllInRegion(country, region)" class="btn-tiny">Select All</button>
                      </div>
                    </div>
                    
                    <div v-if="expandedRegions.includes(`${country}:${region}`)" class="region-content">
                      <!-- Region-level hashtags -->
                      <div class="hashtags-section">
                        <div v-if="getRegionOnlyHashtags(country, region).length > 0">
                          <div class="section-title">Region-level hashtags:</div>
                          <div class="hashtags-list">
                            <div v-for="hashtag in getRegionOnlyHashtags(country, region)" :key="hashtag" class="hashtag-item">
                              <input type="checkbox" :value="hashtag" v-model="selectedHashtags" />
                              <code>{{ hashtag }}</code>
                              <button @click="deleteGeoEntry(hashtag)" class="btn-tiny btn-danger">×</button>
                            </div>
                          </div>
                        </div>
                        <div class="add-inline">
                          <input v-model="inlineAdd.region[`${country}:${region}`]" :placeholder="`Add hashtag for ${region}`" @keyup.enter="addInlineHashtag(country, region, null)" />
                          <button @click="addInlineHashtag(country, region, null)" class="btn-tiny">+</button>
                        </div>
                      </div>
                      
                      <!-- Cities -->
                      <div v-for="city in getRegionCities(country, region)" :key="city" class="city-node">
                        <div class="node-header" @click.prevent="toggleCity(country, region, city)">
                          <span class="expand-icon">{{ expandedCities.includes(`${country}:${region}:${city}`) ? '▼' : '▶' }}</span>
                          <span class="city-name">{{ city }}</span>
                          <span class="count">({{ getCityHashtagCount(country, region, city) }} hashtags)</span>
                          <div class="node-actions">
                            <button @click.stop="selectAllInCity(country, region, city)" class="btn-tiny">Select All</button>
                          </div>
                        </div>
                        
                        <div v-if="expandedCities.includes(`${country}:${region}:${city}`)" class="city-content">
                          <div class="section-title">City hashtags:</div>
                          <div class="hashtags-list">
                            <div v-for="hashtag in getCityHashtags(country, region, city)" :key="hashtag" class="hashtag-item">
                              <input type="checkbox" :value="hashtag" v-model="selectedHashtags" />
                              <code>{{ hashtag }}</code>
                              <button @click="deleteGeoEntry(hashtag)" class="btn-tiny btn-danger">×</button>
                            </div>
                          </div>
                          <div class="add-inline">
                            <input v-model="inlineAdd.city[`${country}:${region}:${city}`]" :placeholder="`Add hashtag for ${city}`" @keyup.enter="addInlineHashtag(country, region, city)" />
                            <button @click="addInlineHashtag(country, region, city)" class="btn-tiny">+</button>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            
            <!-- Table View (existing) -->
            <div v-if="geoViewMode === 'table'" class="geo-table">
              <table>
                <thead>
                  <tr>
                    <th>
                      <input type="checkbox" @change="toggleAllHashtags" :checked="allHashtagsSelected">
                    </th>
                    <th>Hashtag</th>
                    <th>City</th>
                    <th>Region</th>
                    <th>Country</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(entry, hashtag) in filteredGeoEntries" :key="hashtag">
                    <td>
                      <input type="checkbox" :value="hashtag" v-model="selectedHashtags">
                    </td>
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

    <!-- Edit Feed Modal -->
    <div v-if="showEditFeed" class="modal-overlay" @click="cancelEditFeed">
      <div class="modal" @click.stop>
        <h3>Edit Feed: {{ editingFeed?.name }}</h3>
        <div class="edit-feed-content">
          <div class="form-group">
            <label>Feed ID (read-only):</label>
            <span class="feed-id">{{ editingFeed?.id }}</span>
          </div>
          <div class="form-group">
            <label for="owner-input">Owner DID:</label>
            <input 
              id="owner-input" 
              v-model="newOwnerDid" 
              class="owner-input" 
              placeholder="did:plc:example... (leave empty for no owner)"
            >
            <small>The DID of the user who owns this feed</small>
          </div>
          <div class="form-group">
            <label for="websocket-input">WebSocket Base URL:</label>
            <input 
              id="websocket-input" 
              v-model="newWebsocketUrl" 
              class="websocket-input" 
              placeholder="wss://api.graze.social/app/contrail"
            >
            <small>Base WebSocket URL (ingestion worker will append feed parameters automatically)</small>
          </div>
          <div class="form-group">
            <label for="tier-select">Tier:</label>
            <select id="tier-select" v-model="newTier" class="tier-select">
              <option value="bronze">🥉 Bronze</option>
              <option value="silver">🥈 Silver</option>
              <option value="gold">🥇 Gold</option>
              <option value="platinum">💎 Platinum</option>
            </select>
          </div>
        </div>
        <div class="modal-actions">
          <button @click="cancelEditFeed" class="btn-small">Cancel</button>
          <button @click="saveEditFeed" class="btn-primary">Save Changes</button>
        </div>
      </div>
    </div>

    <!-- Create Feed Modal -->
    <div v-if="showCreateFeed" class="modal-overlay" @click="cancelCreateFeed">
      <div class="modal" @click.stop>
        <h3>Create New Feed</h3>
        <div class="create-feed-content">
          <div class="form-group">
            <label for="new-feed-id">Feed ID *</label>
            <input 
              id="new-feed-id" 
              v-model="newFeed.feed_id" 
              class="feed-input" 
              placeholder="e.g., 1234 or abcd1234"
            >
            <small>Unique identifier for the feed (WebSocket URL will be auto-constructed)</small>
          </div>
          <div class="form-group">
            <label for="new-feed-name">Feed Name *</label>
            <input 
              id="new-feed-name" 
              v-model="newFeed.name" 
              class="feed-input" 
              placeholder="e.g., My Awesome Feed"
            >
            <small>Display name for the feed</small>
          </div>
          <div class="form-group">
            <label for="new-owner-did">Owner DID</label>
            <input 
              id="new-owner-did" 
              v-model="newFeed.owner_did" 
              class="feed-input" 
              placeholder="did:plc:example... (optional)"
            >
            <small>DID of the user who owns this feed (leave empty for no owner)</small>
          </div>
          <div class="form-group">
            <label for="new-tier-select">Tier</label>
            <select id="new-tier-select" v-model="newFeed.tier" class="tier-select">
              <option value="bronze">🥉 Bronze</option>
              <option value="silver">🥈 Silver</option>
              <option value="gold">🥇 Gold</option>
              <option value="platinum">💎 Platinum</option>
            </select>
          </div>
        </div>
        <div class="modal-actions">
          <button @click="cancelCreateFeed" class="btn-small">Cancel</button>
          <button @click="saveCreateFeed" class="btn-primary">Create Feed</button>
        </div>
      </div>
    </div>

    <!-- Create API Key Modal -->
    <div v-if="showCreateApiKey" class="modal-overlay" @click="cancelCreateApiKey">
      <div class="modal large-modal" @click.stop>
        <h3>Generate New API Key</h3>
        <div class="create-api-key-content">
          <div class="form-group">
            <label for="api-owner-did">Owner DID *</label>
            <input 
              id="api-owner-did" 
              v-model="newApiKey.owner_did" 
              class="feed-input" 
              placeholder="did:plc:example..."
            >
            <small>The DID of the user who will own this API key</small>
          </div>
          
          <div class="form-group">
            <label for="api-expires">Expiration (days)</label>
            <input 
              id="api-expires" 
              v-model="newApiKey.expires_days" 
              class="feed-input" 
              type="number"
              placeholder="Leave empty for no expiration"
            >
            <small>Number of days until the key expires (optional)</small>
          </div>
          
          <div class="form-group">
            <label>Feed Permissions</label>
            <div class="permissions-grid">
              <div v-for="permission in newApiKey.feed_permissions" :key="permission.feed_id" class="permission-item">
                <div class="permission-header">
                  <input 
                    type="checkbox" 
                    v-model="permission.selected" 
                    :id="`feed-${permission.feed_id}`"
                  >
                  <label :for="`feed-${permission.feed_id}`" class="feed-label">
                    <strong>{{ permission.feed_name }}</strong>
                    <code>{{ permission.feed_id }}</code>
                  </label>
                </div>
                <div v-if="permission.selected" class="permission-level">
                  <select v-model="permission.permission_level" class="level-select">
                    <option value="viewer">👁️ Viewer - Read-only access</option>
                    <option value="moderator">🛡️ Moderator - Manage content</option>
                    <option value="admin">⚡ Admin - Full control</option>
                  </select>
                </div>
              </div>
            </div>
            <small>Select feeds and permission levels for this API key</small>
          </div>
        </div>
        <div class="modal-actions">
          <button @click="cancelCreateApiKey" class="btn-small">Cancel</button>
          <button @click="saveCreateApiKey" class="btn-primary">Generate API Key</button>
        </div>
      </div>
    </div>

    <!-- Edit API Key Permissions Modal -->
    <div v-if="showEditPermissions" class="modal-overlay" @click="cancelEditPermissions">
      <div class="modal large-modal" @click.stop>
        <h3>Edit Permissions: {{ editingApiKey?.owner_did }}</h3>
        <div class="edit-permissions-content">
          <div class="api-key-info">
            <div class="info-item">
              <strong>API Key ID:</strong> {{ editingApiKey?.id }}
            </div>
            <div class="info-item">
              <strong>Owner:</strong> {{ editingApiKey?.owner_did }}
            </div>
            <div class="info-item">
              <strong>Status:</strong> 
              <span :class="`status-badge ${editingApiKey?.is_active ? 'active' : 'inactive'}`">
                {{ editingApiKey?.is_active ? 'Active' : 'Inactive' }}
              </span>
            </div>
          </div>
          
          <div class="form-group">
            <label>Current Feed Permissions</label>
            <div v-if="editPermissions.length === 0" class="no-permissions">
              <p>This API key has no feed permissions.</p>
              <button @click="showAddFeedPermission = true" class="btn-small btn-primary">Add Feed Permission</button>
            </div>
            <div v-else class="permissions-list">
              <div v-for="permission in editPermissions" :key="permission.feed_id" class="permission-row">
                <div class="permission-info">
                  <div class="feed-info">
                    <strong>{{ permission.feed_name }}</strong>
                    <code>{{ permission.feed_id }}</code>
                  </div>
                  <div class="permission-controls">
                    <select v-model="permission.permission_level" class="level-select" @change="updatePermission(permission)">
                      <option value="viewer">👁️ Viewer</option>
                      <option value="moderator">🛡️ Moderator</option>
                      <option value="admin">⚡ Admin</option>
                    </select>
                    <button 
                      @click="togglePermissionActive(permission)" 
                      :class="`btn-tiny ${permission.is_active ? 'btn-warning' : 'btn-success'}`"
                    >
                      {{ permission.is_active ? 'Deactivate' : 'Activate' }}
                    </button>
                    <button @click="deletePermission(permission)" class="btn-tiny btn-danger">Delete</button>
                  </div>
                </div>
                <div v-if="!permission.is_active" class="inactive-notice">
                  ⚠️ This permission is temporarily deactivated
                </div>
              </div>
              <button @click="showAddFeedPermission = true" class="btn-small btn-primary add-permission-btn">Add Feed Permission</button>
            </div>
          </div>
        </div>
        <div class="modal-actions">
          <button @click="cancelEditPermissions" class="btn-small">Close</button>
        </div>
      </div>
    </div>

    <!-- Add Feed Permission Modal -->
    <div v-if="showAddFeedPermission" class="modal-overlay" @click="showAddFeedPermission = false">
      <div class="modal" @click.stop>
        <h3>Add Feed Permission</h3>
        <div class="add-permission-content">
          <div class="form-group">
            <label for="add-feed-select">Select Feed</label>
            <select id="add-feed-select" v-model="newPermission.feed_id" class="feed-select">
              <option value="">Choose a feed...</option>
              <option v-for="feed in availableFeeds" :key="feed.id" :value="feed.id">
                {{ feed.name }} ({{ feed.id }})
              </option>
            </select>
          </div>
          
          <div class="form-group">
            <label for="add-permission-level">Permission Level</label>
            <select id="add-permission-level" v-model="newPermission.permission_level" class="level-select">
              <option value="viewer">👁️ Viewer - Read-only access</option>
              <option value="moderator">🛡️ Moderator - Manage content</option>
              <option value="admin">⚡ Admin - Full control</option>
            </select>
          </div>
        </div>
        <div class="modal-actions">
          <button @click="showAddFeedPermission = false" class="btn-small">Cancel</button>
          <button @click="saveNewPermission" :disabled="!newPermission.feed_id" class="btn-primary">Add Permission</button>
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
    const stats = ref(null)
    const feeds = ref([])
    const apiKeys = ref([])
    const applications = ref([])
    const users = ref([])
    const userSearch = ref('')
    const health = ref(null)
    const activeTab = ref('api-keys')
    const showEditFeed = ref(false)
    const editingFeed = ref(null)
    const newTier = ref('')
    const newOwnerDid = ref('')
    const newWebsocketUrl = ref('')
    const showCreateFeed = ref(false)
    const newFeed = ref({
      feed_id: '',
      name: '',
      owner_did: '',
      tier: 'bronze'
    })
    const showCreateApiKey = ref(false)
    const newApiKey = ref({
      owner_did: '',
      expires_days: '',
      feed_permissions: []
    })
    const showEditPermissions = ref(false)
    const editingApiKey = ref(null)
    const editPermissions = ref([])
    const showAddFeedPermission = ref(false)
    const availableFeeds = ref([])
    const newPermission = ref({
      feed_id: '',
      permission_level: 'viewer'
    })
    const geoHashtags = ref({})
    const newsDomains = ref([])
    const newGeoEntry = ref({ hashtag: '', city: '', region: '', country: '' })
    const newDomain = ref('')
    const geoSearch = ref('')
    const domainSearch = ref('')
    const geoViewMode = ref('tree')
    const selectedHashtags = ref([])
    const expandedCountries = ref([])
    const expandedRegions = ref([])
    const expandedCities = ref([])
    const inlineAdd = ref({ country: {}, region: {}, city: {} })
    
    const tabs = [
      { id: 'api-keys', label: '🔑 API Key Management' },
      { id: 'stats', label: '📊 Platform Statistics & System Health' },
      { id: 'feeds', label: '🎯 Feed Management' },
      { id: 'applications', label: '📝 Feed Applications' },
      { id: 'users', label: '👥 User Management' },
      { id: 'geo-config', label: '🌍 Geo Hashtags Config' },
      { id: 'domains-config', label: '📰 News Domains Config' }
    ]
    
    // Bulk operations
    const selectedFeeds = ref([])

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
        await loadDataWithConfig()
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

    const openCreateApiKey = () => {
      newApiKey.value = {
        owner_did: '',
        expires_days: '',
        feed_permissions: feeds.value.map(feed => ({
          feed_id: feed.id,
          feed_name: feed.name,
          permission_level: 'viewer',
          selected: false
        }))
      }
      showCreateApiKey.value = true
    }
    
    const saveCreateApiKey = async () => {
      if (!newApiKey.value.owner_did) {
        alert('Owner DID is required')
        return
      }
      
      const selectedPermissions = newApiKey.value.feed_permissions.filter(p => p.selected)
      if (selectedPermissions.length === 0) {
        alert('Please select at least one feed')
        return
      }
      
      try {
        const payload = {
          owner_did: newApiKey.value.owner_did,
          feed_permissions: selectedPermissions.map(p => ({
            feed_id: p.feed_id,
            permission_level: p.permission_level
          }))
        }
        
        if (newApiKey.value.expires_days && !isNaN(newApiKey.value.expires_days)) {
          payload.expires_days = parseInt(newApiKey.value.expires_days)
        }
        
        const response = await apiCall('/api-keys', {
          method: 'POST',
          body: JSON.stringify(payload)
        })
        
        alert(`API Key generated successfully!\n\nKey: ${response.api_key}\n\nSave this key - it won't be shown again!`)
        
        const keysData = await apiCall('/api-keys')
        apiKeys.value = keysData.api_keys
        
        showCreateApiKey.value = false
      } catch (error) {
        console.error('API key generation error:', error)
        const errorMsg = error.message || error.detail || JSON.stringify(error)
        alert('Failed to generate API key: ' + errorMsg)
      }
    }
    
    const cancelCreateApiKey = () => {
      showCreateApiKey.value = false
    }
    
    const editApiKeyPermissions = async (apiKey) => {
      try {
        const permissionsData = await apiCall(`/api-keys/${apiKey.id}/permissions`)
        
        editingApiKey.value = apiKey
        editPermissions.value = permissionsData.permissions.map(perm => {
          const feed = feeds.value.find(f => f.id === perm.feed_id)
          return {
            feed_id: perm.feed_id,
            feed_name: feed ? feed.name : perm.feed_id,
            permission_level: perm.permission_level,
            is_active: perm.is_active !== false
          }
        })
        
        availableFeeds.value = feeds.value.filter(feed => 
          !editPermissions.value.some(p => p.feed_id === feed.id)
        )
        
        showEditPermissions.value = true
      } catch (error) {
        alert('Failed to load permissions: ' + error.message)
      }
    }
    
    const updatePermission = async (permission) => {
      try {
        await apiCall(`/api-keys/${editingApiKey.value.id}/permissions/${permission.feed_id}`, {
          method: 'PUT',
          body: JSON.stringify({
            permission_level: permission.permission_level,
            is_active: permission.is_active
          })
        })
      } catch (error) {
        alert('Failed to update permission: ' + error.message)
      }
    }
    
    const togglePermissionActive = async (permission) => {
      permission.is_active = !permission.is_active
      await updatePermission(permission)
    }
    
    const deletePermission = async (permission) => {
      if (!confirm(`Remove ${permission.feed_name} access for this API key?`)) return
      
      try {
        await apiCall(`/api-keys/${editingApiKey.value.id}/permissions/${permission.feed_id}`, {
          method: 'DELETE'
        })
        
        editPermissions.value = editPermissions.value.filter(p => p.feed_id !== permission.feed_id)
        availableFeeds.value = feeds.value.filter(feed => 
          !editPermissions.value.some(p => p.feed_id === feed.id)
        )
      } catch (error) {
        alert('Failed to delete permission: ' + error.message)
      }
    }
    
    const saveNewPermission = async () => {
      if (!newPermission.value.feed_id) return
      
      try {
        await apiCall(`/api-keys/${editingApiKey.value.id}/permissions`, {
          method: 'POST',
          body: JSON.stringify({
            feed_id: newPermission.value.feed_id,
            permission_level: newPermission.value.permission_level
          })
        })
        
        const feed = feeds.value.find(f => f.id === newPermission.value.feed_id)
        editPermissions.value.push({
          feed_id: newPermission.value.feed_id,
          feed_name: feed.name,
          permission_level: newPermission.value.permission_level,
          is_active: true
        })
        
        availableFeeds.value = availableFeeds.value.filter(f => f.id !== newPermission.value.feed_id)
        showAddFeedPermission.value = false
        newPermission.value = { feed_id: '', permission_level: 'viewer' }
      } catch (error) {
        alert('Failed to add permission: ' + error.message)
      }
    }
    
    const cancelEditPermissions = () => {
      showEditPermissions.value = false
      showAddFeedPermission.value = false
      editingApiKey.value = null
      editPermissions.value = []
      availableFeeds.value = []
      newPermission.value = { feed_id: '', permission_level: 'viewer' }
    }
    
    const generateApiKey = async () => {
      const ownerDid = prompt('Enter the DID for the API key owner:')
      if (!ownerDid) return
      
      const expireDays = prompt('Enter expiration days (leave empty for no expiration):')
      
      try {
        const payload = { owner_did: ownerDid }
        if (expireDays && !isNaN(expireDays)) {
          payload.expires_days = parseInt(expireDays)
        }
        
        const response = await apiCall('/api-keys', {
          method: 'POST',
          body: JSON.stringify(payload)
        })
        
        alert(`API Key generated successfully!\n\nKey: ${response.api_key}\n\nSave this key - it won't be shown again!`)
        
        // Reload API keys
        const keysData = await apiCall('/api-keys')
        apiKeys.value = keysData.api_keys
      } catch (error) {
        console.error('API key generation error:', error)
        const errorMsg = error.message || error.detail || JSON.stringify(error)
        alert('Failed to generate API key: ' + errorMsg)
      }
    }

    const revokeApiKey = async (key) => {
      if (!confirm(`Are you sure you want to revoke API key #${key.id} for ${key.owner_did || 'Master Admin'}?`)) {
        return
      }
      
      try {
        await apiCall(`/api-keys/${key.id}`, { method: 'DELETE' })
        
        // Reload API keys
        const keysData = await apiCall('/api-keys')
        apiKeys.value = keysData.api_keys
        
        alert('API key revoked successfully!')
      } catch (error) {
        alert('Failed to revoke API key: ' + error.message)
      }
    }

    const editFeed = (feed) => {
      editingFeed.value = feed
      newTier.value = feed.tier
      newOwnerDid.value = feed.owner_did || ''
      newWebsocketUrl.value = feed.contrails_websocket_url || ''
      showEditFeed.value = true
    }
    
    const saveEditFeed = async () => {
      const hasChanges = newTier.value !== editingFeed.value.tier || 
                        newOwnerDid.value !== (editingFeed.value.owner_did || '') ||
                        newWebsocketUrl.value !== (editingFeed.value.contrails_websocket_url || '')
      
      if (!hasChanges) {
        showEditFeed.value = false
        return
      }
      
      try {
        const updates = {}
        if (newTier.value !== editingFeed.value.tier) {
          updates.tier = newTier.value
        }
        if (newOwnerDid.value !== (editingFeed.value.owner_did || '')) {
          updates.owner_did = newOwnerDid.value || null
        }
        if (newWebsocketUrl.value !== (editingFeed.value.contrails_websocket_url || '')) {
          updates.contrails_websocket_url = newWebsocketUrl.value
        }
        
        await apiCall(`/feeds/${editingFeed.value.id}`, {
          method: 'PUT',
          body: JSON.stringify(updates)
        })
        
        // Reload feeds to show updated data
        const feedsData = await apiCall('/feeds')
        feeds.value = feedsData.feeds
        
        showEditFeed.value = false
        alert('Feed updated successfully!')
      } catch (error) {
        alert('Failed to update feed: ' + error.message)
      }
    }
    
    const cancelEditFeed = () => {
      showEditFeed.value = false
      editingFeed.value = null
      newTier.value = ''
      newOwnerDid.value = ''
      newWebsocketUrl.value = ''
    }
    
    const openCreateFeed = () => {
      newFeed.value = {
        feed_id: '',
        name: '',
        owner_did: '',
        tier: 'bronze'
      }
      showCreateFeed.value = true
    }
    
    const saveCreateFeed = async () => {
      if (!newFeed.value.feed_id || !newFeed.value.name) {
        alert('Feed ID and Name are required')
        return
      }
      
      // Use base WebSocket URL format (ingestion worker will construct full URL)
      const websocket_url = 'wss://api.graze.social/app/contrail'
      
      try {
        await apiCall('/feeds', {
          method: 'POST',
          body: JSON.stringify({
            feed_id: newFeed.value.feed_id,
            name: newFeed.value.name,
            websocket_url: websocket_url,
            owner_did: newFeed.value.owner_did || null,
            tier: newFeed.value.tier
          })
        })
        
        // Reload feeds to show new feed
        const feedsData = await apiCall('/feeds')
        feeds.value = feedsData.feeds
        
        showCreateFeed.value = false
        alert('Feed created successfully!')
      } catch (error) {
        alert('Failed to create feed: ' + error.message)
      }
    }
    
    const cancelCreateFeed = () => {
      showCreateFeed.value = false
      newFeed.value = {
        feed_id: '',
        name: '',
        owner_did: '',
        tier: 'bronze'
      }
    }

    const toggleFeedActive = async (feed, isActive) => {
      const action = isActive ? 'activate' : 'deactivate'
      if (!confirm(`Are you sure you want to ${action} feed "${feed.name}" (${feed.id})?\n\n${isActive ? 'This will make the feed visible and resume aggregations.' : 'This will hide the feed from users and stop aggregations.'}`)) {
        return
      }
      
      try {
        await apiCall(`/feeds/${feed.id}`, {
          method: 'PUT',
          body: JSON.stringify({ is_active: isActive })
        })
        
        // Reload feeds to show updated status
        const feedsData = await apiCall('/feeds')
        feeds.value = feedsData.feeds
        
        alert(`Feed "${feed.name}" ${action}d successfully!`)
      } catch (error) {
        alert(`Failed to ${action} feed: ` + error.message)
      }
    }
    
    const hardDeleteFeed = async (feed) => {
      if (!confirm(`⚠️ PERMANENT DELETION WARNING ⚠️\n\nAre you sure you want to PERMANENTLY DELETE feed "${feed.name}" (${feed.id})?\n\nThis will remove ALL data including:\n• All posts in this feed\n• All user achievements\n• All aggregated statistics\n• Feed configuration\n\nThis action CANNOT be undone!`)) {
        return
      }
      
      // Double confirmation for hard delete - actually require typing the feed ID
      const typedFeedId = prompt(`Final confirmation: Type the feed ID "${feed.id}" to confirm permanent deletion:`)
      if (typedFeedId !== feed.id) {
        alert('Feed ID does not match. Deletion cancelled.')
        return
      }
      
      try {
        await apiCall(`/feeds/${feed.id}?hard_delete=true`, { method: 'DELETE' })
        
        // Reload feeds to show updated list
        const feedsData = await apiCall('/feeds')
        feeds.value = feedsData.feeds
        
        alert(`Feed "${feed.name}" permanently deleted!`)
      } catch (error) {
        alert('Failed to delete feed: ' + error.message)
      }
    }

    const reviewApplication = async (app, status) => {
      try {
        await apiCall(`/applications/${app.id}`, {
          method: 'PUT',
          body: JSON.stringify({
            status: status,
            tier: 'bronze',
            notes: status === 'approved' ? 'Application approved' : 'Application rejected'
          })
        })
        
        // Reload applications to show updated status
        const appsData = await apiCall('/applications')
        applications.value = appsData.applications
        
        alert(`Application ${status} successfully!`)
      } catch (error) {
        alert('Failed to review application: ' + error.message)
      }
    }

    const viewApplicationDetails = (app) => {
      const details = `Application Details:

ID: ${app.id}
Applicant DID: ${app.applicant_did}
Applicant Handle: ${app.applicant_handle}
Feed ID: ${app.feed_id}
WebSocket URL: ${app.websocket_url}
Description: ${app.description}
Status: ${app.status}
Applied: ${new Date(app.applied_at).toLocaleString()}
Reviewed: ${app.reviewed_at ? new Date(app.reviewed_at).toLocaleString() : 'Not yet'}
Notes: ${app.notes || 'None'}`
      
      alert(details)
    }

    const searchUsers = async () => {
      console.log('Search users:', userSearch.value)
    }

    const viewUserDetails = async (user) => {
      console.log('View user details:', user)
    }

    const toggleProminent = async (user) => {
      console.log('Toggle prominent:', user)
    }

    const manageAchievements = async (user) => {
      console.log('Manage achievements:', user)
    }

    const refreshHealth = async () => {
      try {
        health.value = await apiCall('/health')
      } catch (error) {
        console.error('Failed to refresh health:', error)
      }
    }

    // Configuration functions
    const loadGeoConfig = async () => {
      try {
        const result = await apiCall('/config/geo-hashtags')
        if (result) geoHashtags.value = result
      } catch (error) {
        console.error('Failed to load geo config:', error)
      }
    }
    
    const loadDomainsConfig = async () => {
      try {
        const result = await apiCall('/config/news-domains')
        if (result) newsDomains.value = result
      } catch (error) {
        console.error('Failed to load domains config:', error)
      }
    }
    
    // Enhanced loadData to include config
    const loadDataWithConfig = async () => {
      await loadData()
      await loadGeoConfig()
      await loadDomainsConfig()
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
      selectedFeeds,
      authenticate,
      logout,
      openCreateApiKey,
      saveCreateApiKey,
      cancelCreateApiKey,
      editApiKeyPermissions,
      updatePermission,
      togglePermissionActive,
      deletePermission,
      saveNewPermission,
      cancelEditPermissions,
      revokeApiKey,
      editFeed,
      toggleFeedActive,
      hardDeleteFeed,
      reviewApplication,
      viewApplicationDetails,
      searchUsers,
      viewUserDetails,
      toggleProminent,
      manageAchievements,
      refreshHealth,
      
      // Feed management functions
      updateFeed: async (feedId, updates) => {
        try {
          await apiCall(`/feeds/${feedId}`, {
            method: 'PUT',
            body: JSON.stringify(updates)
          })
          
          // Reload feeds to show updated data
          const feedsData = await apiCall('/feeds')
          feeds.value = feedsData.feeds
          
          alert('Feed updated successfully!')
        } catch (error) {
          alert('Failed to update feed: ' + error.message)
        }
      },
      
      // Configuration management
      loadGeoConfig,
      loadDomainsConfig,
      
      addGeoEntry: async () => {
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
      },
      
      deleteGeoEntry: async (hashtag) => {
        if (!confirm(`Delete hashtag mapping for "${hashtag}"?`)) return
        try {
          await apiCall(`/config/geo-hashtags/${hashtag}`, { method: 'DELETE' })
          await loadGeoConfig()
        } catch (error) {
          alert('Failed to delete geo entry: ' + error.message)
        }
      },
      
      addDomain: async () => {
        let domain = newDomain.value.toLowerCase().trim()
        
        // Remove protocol (http:// or https://)
        domain = domain.replace(/^https?:\/\//, '')
        
        // Remove www. prefix
        domain = domain.replace(/^www\./, '')
        
        // Remove trailing slash and any path
        domain = domain.split('/')[0]
        
        // Remove any remaining whitespace
        domain = domain.trim()
        
        if (!domain || newsDomains.value.includes(domain)) return
        
        try {
          const response = await fetch('/api/v1/admin/config/news-domains', {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${apiKey.value}`,
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({ domain })
          })
          
          if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: response.statusText }))
            throw new Error(errorData.detail || 'Request failed')
          }
          await loadDomainsConfig()
          newDomain.value = ''
        } catch (error) {
          console.error('Domain add error:', error)
          const errorMsg = error.message || error.detail || JSON.stringify(error)
          alert('Failed to add domain: ' + errorMsg)
        }
      },
      
      deleteDomain: async (domain) => {
        if (!confirm(`Remove "${domain}" from news domains?`)) return
        try {
          await apiCall(`/config/news-domains/${domain}`, { method: 'DELETE' })
          await loadDomainsConfig()
        } catch (error) {
          alert('Failed to delete domain: ' + error.message)
        }
      },
      
      // Computed properties
      geoHierarchy: computed(() => {
        const countries = new Set()
        const regions = {}
        const cities = {}
        
        Object.entries(geoHashtags.value).forEach(([hashtag, entry]) => {
          countries.add(entry.country)
          
          if (entry.region) {
            if (!regions[entry.country]) regions[entry.country] = new Set()
            regions[entry.country].add(entry.region)
            
            if (entry.city) {
              const regionKey = `${entry.country}:${entry.region}`
              if (!cities[regionKey]) cities[regionKey] = new Set()
              cities[regionKey].add(entry.city)
            }
          }
        })
        
        return {
          countries: Array.from(countries).sort(),
          regions: Object.fromEntries(Object.entries(regions).map(([k, v]) => [k, Array.from(v).sort()])),
          cities: Object.fromEntries(Object.entries(cities).map(([k, v]) => [k, Array.from(v).sort()]))
        }
      }),
      
      filteredHierarchy: computed(() => {
        const countries = new Set()
        const regions = {}
        const cities = {}
        
        Object.entries(geoHashtags.value).forEach(([hashtag, entry]) => {
          countries.add(entry.country)
          
          if (entry.region) {
            if (!regions[entry.country]) regions[entry.country] = new Set()
            regions[entry.country].add(entry.region)
            
            if (entry.city) {
              const regionKey = `${entry.country}:${entry.region}`
              if (!cities[regionKey]) cities[regionKey] = new Set()
              cities[regionKey].add(entry.city)
            }
          }
        })
        
        const hierarchy = {
          countries: Array.from(countries).sort(),
          regions: Object.fromEntries(Object.entries(regions).map(([k, v]) => [k, Array.from(v).sort()])),
          cities: Object.fromEntries(Object.entries(cities).map(([k, v]) => [k, Array.from(v).sort()]))
        }
        
        if (!geoSearch.value) return hierarchy
        const search = geoSearch.value.toLowerCase()
        
        const matchingHashtags = Object.entries(geoHashtags.value)
          .filter(([hashtag, entry]) => 
            hashtag.includes(search) ||
            (entry.city && entry.city.toLowerCase().includes(search)) ||
            (entry.region && entry.region.toLowerCase().includes(search)) ||
            entry.country.toLowerCase().includes(search)
          )
        
        const matchingCountries = new Set(matchingHashtags.map(([_, entry]) => entry.country))
        
        return {
          countries: Array.from(matchingCountries).sort(),
          regions: hierarchy.regions,
          cities: hierarchy.cities
        }
      }),
      
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
      newDomain,
      geoViewMode,
      selectedHashtags,
      expandedCountries,
      expandedRegions,
      expandedCities,
      inlineAdd,
      showEditFeed,
      editingFeed,
      newTier,
      newOwnerDid,
      newWebsocketUrl,
      saveEditFeed,
      cancelEditFeed,
      showCreateFeed,
      newFeed,
      openCreateFeed,
      saveCreateFeed,
      cancelCreateFeed,
      showCreateApiKey,
      newApiKey,
      showEditPermissions,
      editingApiKey,
      editPermissions,
      showAddFeedPermission,
      availableFeeds,
      newPermission,
      
      copyPublicUrl: () => {
        const url = `${window.location.origin}/geo-hashtags`
        navigator.clipboard.writeText(url)
        alert('Public URL copied to clipboard: ' + url)
      },
      
      addInlineHashtag: async (country, region, city) => {
        let hashtag
        if (city) {
          hashtag = inlineAdd.value.city[`${country}:${region}:${city}`]
          inlineAdd.value.city[`${country}:${region}:${city}`] = ''
        } else if (region) {
          hashtag = inlineAdd.value.region[`${country}:${region}`]
          inlineAdd.value.region[`${country}:${region}`] = ''
        } else {
          hashtag = inlineAdd.value.country[country]
          inlineAdd.value.country[country] = ''
        }
        
        if (!hashtag) return
        
        hashtag = hashtag.toLowerCase().replace(/[^a-z0-9]/g, '')
        if (!hashtag) return
        
        try {
          await apiCall('/config/geo-hashtags', {
            method: 'POST',
            body: JSON.stringify({
              hashtag,
              city: city || null,
              region: region || null,
              country
            })
          })
          await loadGeoConfig()
        } catch (error) {
          alert('Failed to add hashtag: ' + error.message)
        }
      },
      
      // Geo hierarchy methods
      toggleCountry: (country) => {
        console.log('Toggle country:', country)
        const index = expandedCountries.value.indexOf(country)
        if (index > -1) {
          expandedCountries.value.splice(index, 1)
        } else {
          expandedCountries.value.push(country)
        }
      },
      
      toggleRegion(country, region) {
        const key = `${country}:${region}`
        const index = expandedRegions.value.indexOf(key)
        if (index > -1) {
          expandedRegions.value.splice(index, 1)
        } else {
          expandedRegions.value.push(key)
        }
      },
      
      toggleCity(country, region, city) {
        const key = `${country}:${region}:${city}`
        const index = expandedCities.value.indexOf(key)
        if (index > -1) {
          expandedCities.value.splice(index, 1)
        } else {
          expandedCities.value.push(key)
        }
      },
      
      getCountryFlag: (country) => {
        const flags = {
          'USA': '🇺🇸', 'United States': '🇺🇸',
          'Canada': '🇨🇦', 'United Kingdom': '🇬🇧',
          'France': '🇫🇷', 'Germany': '🇩🇪',
          'Japan': '🇯🇵', 'Australia': '🇦🇺',
          'Brazil': '🇧🇷', 'India': '🇮🇳',
          'China': '🇨🇳', 'Mexico': '🇲🇽',
          'Spain': '🇪🇸', 'Italy': '🇮🇹',
          'Netherlands': '🇳🇱', 'UAE': '🇦🇪',
          'Nigeria': '🇳🇬', 'South Africa': '🇿🇦'
        }
        return flags[country] || '🌍'
      },
      
      getCountryHashtagCount: (country) => {
        return Object.values(geoHashtags.value).filter(entry => entry.country === country).length
      },
      
      getCountryOnlyHashtags: (country) => {
        return Object.entries(geoHashtags.value)
          .filter(([_, entry]) => entry.country === country && !entry.region && !entry.city)
          .map(([hashtag]) => hashtag)
      },
      
      getCountryRegions: (country) => {
        const regions = new Set()
        
        Object.entries(geoHashtags.value).forEach(([hashtag, entry]) => {
          if (entry.region && entry.country === country) {
            regions.add(entry.region)
          }
        })
        
        return Array.from(regions).sort()
      },
      
      getRegionHashtagCount: (country, region) => {
        return Object.values(geoHashtags.value)
          .filter(entry => entry.country === country && entry.region === region).length
      },
      
      getRegionOnlyHashtags: (country, region) => {
        return Object.entries(geoHashtags.value)
          .filter(([_, entry]) => entry.country === country && entry.region === region && !entry.city)
          .map(([hashtag]) => hashtag)
      },
      
      getRegionCities: (country, region) => {
        const cities = new Set()
        
        Object.entries(geoHashtags.value).forEach(([hashtag, entry]) => {
          if (entry.city && entry.country === country && entry.region === region) {
            cities.add(entry.city)
          }
        })
        
        return Array.from(cities).sort()
      },
      
      getCityHashtagCount: (country, region, city) => {
        return Object.values(geoHashtags.value)
          .filter(entry => entry.country === country && entry.region === region && entry.city === city).length
      },
      
      getCityHashtags: (country, region, city) => {
        return Object.entries(geoHashtags.value)
          .filter(([_, entry]) => entry.country === country && entry.region === region && entry.city === city)
          .map(([hashtag]) => hashtag)
      },
      
      selectAllInCountry: (country) => {
        const hashtags = Object.entries(geoHashtags.value)
          .filter(([_, entry]) => entry.country === country)
          .map(([hashtag]) => hashtag)
        selectedHashtags.value = [...new Set([...selectedHashtags.value, ...hashtags])]
      },
      
      selectAllInRegion: (country, region) => {
        const hashtags = Object.entries(geoHashtags.value)
          .filter(([_, entry]) => entry.country === country && entry.region === region)
          .map(([hashtag]) => hashtag)
        selectedHashtags.value = [...new Set([...selectedHashtags.value, ...hashtags])]
      },
      
      selectAllInCity: (country, region, city) => {
        const hashtags = Object.entries(geoHashtags.value)
          .filter(([_, entry]) => entry.country === country && entry.region === region && entry.city === city)
          .map(([hashtag]) => hashtag)
        selectedHashtags.value = [...new Set([...selectedHashtags.value, ...hashtags])]
      },
      
      bulkDeleteHashtags: async () => {
        if (!confirm(`Delete ${selectedHashtags.value.length} selected hashtags?`)) return
        
        try {
          for (const hashtag of selectedHashtags.value) {
            await apiCall(`/config/geo-hashtags/${hashtag}`, { method: 'DELETE' })
          }
          await loadGeoConfig()
          selectedHashtags.value = []
        } catch (error) {
          alert('Failed to delete hashtags: ' + error.message)
        }
      },
      
      toggleAllHashtags: () => {
        const allHashtags = Object.keys(filteredGeoEntries.value)
        if (selectedHashtags.value.length === allHashtags.length) {
          selectedHashtags.value = []
        } else {
          selectedHashtags.value = allHashtags
        }
      },
      
      // Bulk operations placeholders
      toggleAllFeeds: () => {
        if (selectedFeeds.value.length === feeds.value.length) {
          selectedFeeds.value = []
        } else {
          selectedFeeds.value = feeds.value.map(f => f.id)
        }
      },
      allFeedsSelected: computed(() => selectedFeeds.value.length === feeds.value.length && feeds.value.length > 0),
      bulkUpdateTier: () => console.log('Bulk update tier'),
      bulkToggleActive: () => console.log('Bulk toggle active'),
      bulkDelete: () => console.log('Bulk delete')
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

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  flex-wrap: wrap;
  gap: 15px;
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

.status-badge {
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 0.8em;
  font-weight: bold;
}

.status-badge.active { background: #d4edda; color: #155724; }
.status-badge.inactive { background: #f8d7da; color: #721c24; }

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

.btn-primary, .btn-small, .btn-danger, .btn-success, .btn-warning {
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 500;
}

.btn-primary { background: #007bff; color: white; }
.btn-small { padding: 4px 8px; font-size: 0.8em; background: #6c757d; color: white; }
.btn-danger { background: #dc3545; color: white; }
.btn-success { background: #28a745; color: white; }
.btn-warning { background: #ffc107; color: #212529; }

.actions {
  display: flex;
  gap: 8px;
}

.search-box input {
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  width: 300px;
  font-size: 14px;
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

.no-applications {
  text-align: center;
  padding: 40px;
  color: #666;
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

.form-help {
  margin-top: 10px;
}

.form-help small {
  color: #666;
  font-style: italic;
}

/* Geo Hierarchy Styles */
.header-controls {
  display: flex;
  align-items: center;
  gap: 15px;
}

.view-toggle {
  display: flex;
  gap: 5px;
}

.view-toggle .btn-small.active {
  background: #007bff;
  color: white;
}

.geo-stats {
  display: flex;
  gap: 20px;
  padding: 15px;
  background: #f8f9fa;
  border-radius: 8px;
  margin-bottom: 20px;
  border-left: 4px solid #007bff;
}

.stat-item {
  text-align: center;
}

.stat-item strong {
  display: block;
  font-size: 1.2em;
  color: #007bff;
}

.geo-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  gap: 15px;
  flex-wrap: wrap;
}

.geo-tree {
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  background: white;
  max-height: 600px;
  overflow-y: auto;
}

.country-node, .region-node, .city-node {
  border-bottom: 1px solid #f0f0f0;
}

.country-node:last-child {
  border-bottom: none;
}

.node-header {
  display: flex;
  align-items: center;
  padding: 12px 15px;
  cursor: pointer;
  transition: background-color 0.2s;
  gap: 8px;
}

.node-header:hover {
  background: #f8f9fa;
}

.country-node > .node-header {
  background: #f8f9fa;
  font-weight: 600;
  border-bottom: 1px solid #e0e0e0;
}

.region-node > .node-header {
  background: #fdfdfd;
  padding-left: 35px;
  font-weight: 500;
}

.city-node > .node-header {
  padding-left: 55px;
  background: white;
}

.expand-icon {
  width: 16px;
  text-align: center;
  font-size: 12px;
  color: #666;
}

.flag {
  font-size: 18px;
}

.count {
  color: #666;
  font-size: 0.9em;
  margin-left: auto;
}

.node-actions {
  margin-left: 10px;
}

.country-content, .region-content, .city-content {
  background: #fafafa;
}

.hashtags-section {
  padding: 10px 15px;
  border-bottom: 1px solid #f0f0f0;
}

.hashtags-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.hashtag-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  font-size: 0.9em;
}

.hashtag-item input[type="checkbox"] {
  margin: 0;
}

.hashtag-item code {
  background: none;
  padding: 0;
  font-size: 0.85em;
  color: #0066cc;
}

.btn-tiny {
  padding: 2px 6px;
  font-size: 0.75em;
  border: none;
  border-radius: 3px;
  cursor: pointer;
  background: #6c757d;
  color: white;
}

.btn-tiny.btn-danger {
  background: #dc3545;
}

.btn-tiny:hover {
  opacity: 0.8;
}

.add-inline {
  display: flex;
  gap: 5px;
  margin-top: 8px;
  padding: 5px;
  background: #f0f8ff;
  border-radius: 4px;
}

.add-inline input {
  flex: 1;
  padding: 4px 8px;
  border: 1px solid #ddd;
  border-radius: 3px;
  font-size: 0.8em;
}

.region-node {
  margin-left: 20px;
}

.city-node {
  margin-left: 40px;
}

/* Edit Feed Modal Styles */
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
  box-shadow: 0 10px 30px rgba(0,0,0,0.3);
}

.modal h3 {
  margin: 0 0 20px 0;
  color: #2c3e50;
}

.edit-feed-content {
  margin: 20px 0;
}

.form-group {
  margin-bottom: 15px;
}

.form-group label {
  display: block;
  font-weight: 600;
  margin-bottom: 5px;
  color: #2c3e50;
}

.feed-id {
  font-family: monospace;
  background: #f8f9fa;
  padding: 8px 12px;
  border-radius: 4px;
  border: 1px solid #e0e0e0;
  display: block;
  color: #666;
}

.owner-input, .websocket-input {
  width: 100%;
  padding: 10px 12px;
  border: 2px solid #e0e0e0;
  border-radius: 6px;
  font-size: 14px;
  font-family: monospace;
  background: white;
}

.owner-input:focus, .websocket-input:focus {
  outline: none;
  border-color: #007bff;
}

.form-group small {
  color: #666;
  font-size: 0.85em;
  margin-top: 5px;
  display: block;
}

.tier-select {
  width: 100%;
  padding: 10px 12px;
  border: 2px solid #e0e0e0;
  border-radius: 6px;
  font-size: 16px;
  background: white;
  cursor: pointer;
}

.tier-select:focus {
  outline: none;
  border-color: #007bff;
}

.modal-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 20px;
}

.create-feed-content {
  margin: 20px 0;
}

.feed-input {
  width: 100%;
  padding: 10px 12px;
  border: 2px solid #e0e0e0;
  border-radius: 6px;
  font-size: 14px;
  background: white;
}

.feed-input:focus {
  outline: none;
  border-color: #007bff;
}

.large-modal {
  max-width: 700px;
  width: 95%;
}

.create-api-key-content {
  margin: 20px 0;
}

.permissions-grid {
  display: flex;
  flex-direction: column;
  gap: 15px;
  max-height: 300px;
  overflow-y: auto;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  padding: 15px;
  background: #f8f9fa;
}

.permission-item {
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  padding: 12px;
}

.permission-header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.feed-label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  cursor: pointer;
  flex: 1;
}

.feed-label code {
  font-size: 0.8em;
  color: #666;
  background: #f0f0f0;
  padding: 2px 6px;
  border-radius: 3px;
}

.permission-level {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid #f0f0f0;
}

.level-select {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  background: white;
  font-size: 14px;
}

.level-select:focus {
  outline: none;
  border-color: #007bff;
}

.edit-permissions-content {
  margin: 20px 0;
}

.api-key-info {
  background: #f8f9fa;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  padding: 15px;
  margin-bottom: 20px;
  display: flex;
  gap: 20px;
  flex-wrap: wrap;
}

.info-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.info-item strong {
  color: #2c3e50;
}

.permissions-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.permission-row {
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  padding: 12px;
  background: white;
}

.permission-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 15px;
}

.feed-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.feed-info code {
  font-size: 0.8em;
  color: #666;
  background: #f0f0f0;
  padding: 2px 6px;
  border-radius: 3px;
}

.permission-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.inactive-notice {
  margin-top: 8px;
  padding: 6px 10px;
  background: #fff3cd;
  border: 1px solid #ffeaa7;
  border-radius: 4px;
  color: #856404;
  font-size: 0.9em;
}

.no-permissions {
  text-align: center;
  padding: 30px;
  color: #666;
  background: #f8f9fa;
  border-radius: 6px;
  border: 1px dashed #ddd;
}

.add-permission-btn {
  margin-top: 10px;
  align-self: flex-start;
}

.add-permission-content {
  margin: 20px 0;
}

.feed-select {
  width: 100%;
  padding: 10px 12px;
  border: 2px solid #e0e0e0;
  border-radius: 6px;
  font-size: 14px;
  background: white;
}

.feed-select:focus {
  outline: none;
  border-color: #007bff;
}
</style>