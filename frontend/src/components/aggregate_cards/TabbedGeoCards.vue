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
      <!-- Cities Tab -->
      <div v-if="activeTab === 'cities'" class="geo-grid">
        <div v-if="cities && cities.length">
          <div v-for="(city, index) in cities" :key="city.city" class="geo-item">
            <span class="rank">{{ index + 1 }}</span>
            <div class="geo-info">
              <span class="geo-name">{{ city.city }}</span>
            </div>
            <span class="geo-count">{{ city.count.toLocaleString() }}</span>
          </div>
        </div>
        <div v-else class="no-data-message">
          <p>No city data to display right now.</p>
        </div>
      </div>

      <!-- Regions Tab -->
      <div v-if="activeTab === 'regions'" class="geo-grid">
        <div v-if="regions && regions.length">
          <div v-for="(region, index) in regions" :key="region.region" class="geo-item">
            <span class="rank">{{ index + 1 }}</span>
            <div class="geo-info">
              <span class="geo-name">{{ region.region }}</span>
            </div>
            <span class="geo-count">{{ region.count.toLocaleString() }}</span>
          </div>
        </div>
        <div v-else class="no-data-message">
          <p>No region data to display right now.</p>
        </div>
      </div>

      <!-- Countries Tab -->
      <div v-if="activeTab === 'countries'" class="geo-grid">
        <div v-if="countries && countries.length">
          <div v-for="(country, index) in countries" :key="country.country" class="geo-item">
            <span class="rank">{{ index + 1 }}</span>
            <div class="geo-info">
              <span class="geo-name">{{ country.country }}</span>
            </div>
            <span class="geo-count">{{ country.count.toLocaleString() }}</span>
          </div>
        </div>
        <div v-else class="no-data-message">
          <p>No country data to display right now.</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { PropType } from 'vue'

interface CityItem {
  type: string
  city: string
  count: number
}

interface RegionItem {
  type: string
  region: string
  count: number
}

interface CountryItem {
  type: string
  country: string
  count: number
}

defineProps({
  cities: {
    type: Array as PropType<CityItem[]>,
    required: true,
  },
  regions: {
    type: Array as PropType<RegionItem[]>,
    required: true,
  },
  countries: {
    type: Array as PropType<CountryItem[]>,
    required: true,
  },
})

const activeTab = ref('cities')

const tabs = [
  { value: 'cities', label: 'Cities' },
  { value: 'regions', label: 'Regions' },
  { value: 'countries', label: 'Countries' },
]
</script>

<style scoped>
.stat-card {
  background-color: #2b2d31;
  border: 1px solid #404249;
  border-radius: 8px;
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
}

.tab-selector button.active {
  background-color: #2b2d31;
  color: #fff;
}

.tab-selector button:hover:not(.active) {
  background-color: #3c3e44;
}

.scrollable-content {
  flex: 1;
  overflow-y: auto;
}

.geo-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
}

.geo-item {
  display: grid;
  grid-template-columns: 30px 1fr auto;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
}

.rank {
  font-size: 0.9rem;
  font-weight: 600;
  color: #949ba4;
  text-align: center;
}

.geo-info {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.geo-name {
  font-weight: 600;
  color: #fff;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.geo-details {
  color: #949ba4;
  font-size: 0.9rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.geo-count {
  font-size: 0.9rem;
  font-weight: 500;
  color: #b5bac1;
  white-space: nowrap;
}

.no-data-message {
  text-align: center;
  padding: 2rem;
  color: #949ba4;
}

.hide-scrollbar {
  scrollbar-width: none;
}

.hide-scrollbar::-webkit-scrollbar {
  display: none;
}
</style>