<template>
  <div class="stat-card">
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

    <div class="scrollable-content hide-scrollbar">
      <!-- Top Domains Tab -->
      <div v-if="activeTab === 'domains'" class="links-grid">
        <div v-if="domains && domains.length">
          <div v-for="(domain, index) in domains" :key="domain.domain + index" class="link-pill">
            <span class="link-name">{{ domain.domain }}</span>
            <span class="link-count">{{ domain.count.toLocaleString() }}</span>
          </div>
        </div>
        <div v-else class="no-data-message">
          <p>No domain data to display right now.</p>
        </div>
      </div>

      <!-- Top Links Tab -->
      <div v-if="activeTab === 'links'" class="links-grid">
        <div v-if="links && links.length">
          <a v-for="(link, index) in links" :key="link.uri + index" :href="link.uri" target="_blank" rel="noopener noreferrer" class="link-pill">
            <span class="link-name">{{ truncateUrl(link.uri) }}</span>
            <span class="link-count">{{ link.count.toLocaleString() }}</span>
          </a>
        </div>
        <div v-else class="no-data-message">
          <p>No link data to display right now.</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { PropType } from 'vue'
import type { TopLink } from '@/types/aggregates'

interface Domain {
  domain: string
  count: number
}

defineProps({
  links: {
    type: Array as PropType<TopLink[]>,
    required: true,
  },
  domains: {
    type: Array as PropType<Domain[]>,
    required: true,
  },
})

const activeTab = ref('domains')

const tabs = [
  { value: 'domains', label: 'Top Domains' },
  { value: 'links', label: 'Top Links' },
]

const getHostname = (url: string): string => {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch (e) {
    return url
  }
}

const truncateUrl = (url: string): string => {
  // Remove protocol for cleaner display
  const cleanUrl = url.replace(/^https?:\/\//, '').replace(/^www\./, '')
  // Truncate if too long
  return cleanUrl.length > 60 ? cleanUrl.substring(0, 57) + '...' : cleanUrl
}
</script>

<style scoped>
.stat-card {
  background-color: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 1rem 1.5rem;
  grid-column: span 2;
  grid-row: span 12;
  display: flex;
  flex-direction: column;
}

.card-header-with-tabs {
  margin-bottom: 1rem;
}

.tab-selector {
  display: flex;
  gap: 4px;
  background-color: var(--bg-tertiary);
  border-radius: 6px;
  padding: 4px;
}

.tab-selector button {
  background-color: transparent;
  border: none;
  color: var(--text-secondary);
  padding: 6px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.85rem;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.tab-selector button.active {
  background-color: var(--bg-secondary);
  color: var(--text-primary);
}

.tab-selector button:hover:not(.active) {
  background-color: var(--hover-bg);
}

.scrollable-content {
  flex-grow: 1;
  overflow-y: auto;
  -ms-overflow-style: none; /* IE and Edge */
  scrollbar-width: none; /* Firefox */
}

.scrollable-content::-webkit-scrollbar {
  display: none; /* Chrome, Safari, Opera*/
}

.links-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.link-pill {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 12px;
  background-color: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  margin-bottom: 8px;
  text-decoration: none;
  color: inherit;
  transition: background-color 0.2s ease;
}

.link-pill:hover {
  background-color: var(--hover-bg);
}

.link-name {
  color: var(--text-primary);
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex-grow: 1;
}

.link-count {
  background-color: var(--bg-secondary);
  color: var(--text-secondary);
  padding: 4px 6px;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 500;
  border: 1px solid var(--border-color);
  flex-shrink: 0;
}

.no-data-message {
  text-align: center;
  padding: 2rem;
  color: var(--text-muted);
}
</style>