<template>
  <div class="geo-hashtags-container">
    <div class="header">
      <h1>🌍 Supported Locations & Hashtags</h1>
      <p>Use these hashtags in your posts to be included in location-based feeds</p>
    </div>
    
    <div v-if="loading" class="loading">Loading hashtags...</div>
    
    <div v-else-if="error" class="error">{{ error }}</div>
    
    <div v-else class="geo-tree">
      <div v-for="country in hierarchy.countries" :key="country" class="country-section">
        <div class="country-header">
          <span class="flag">{{ getCountryFlag(country) }}</span>
          <strong>{{ country }}</strong>
          <span class="hashtag-count">({{ getCountryHashtagCount(country) }} hashtags)</span>
        </div>
        
        <div class="country-content">
          <!-- Country hashtags -->
          <div v-if="getCountryOnlyHashtags(country).length > 0" class="hashtags-section">
            <div class="hashtags-list">
              <span v-for="hashtag in getCountryOnlyHashtags(country)" :key="hashtag" class="hashtag">#{{ hashtag }}</span>
            </div>
          </div>
          
          <!-- Regions -->
          <div v-for="region in getCountryRegions(country)" :key="region" class="region-section">
            <div class="region-header">
              <strong>{{ region }}</strong>
              <span class="hashtag-count">({{ getRegionHashtagCount(country, region) }} hashtags)</span>
            </div>
            
            <!-- Region hashtags -->
            <div v-if="getRegionOnlyHashtags(country, region).length > 0" class="hashtags-section">
              <div class="hashtags-list">
                <span v-for="hashtag in getRegionOnlyHashtags(country, region)" :key="hashtag" class="hashtag">#{{ hashtag }}</span>
              </div>
            </div>
            
            <!-- Cities -->
            <div v-for="city in getRegionCities(country, region)" :key="city" class="city-section">
              <div class="city-header">
                <strong>{{ city }}</strong>
                <span class="hashtag-count">({{ getCityHashtagCount(country, region, city) }} hashtags)</span>
              </div>
              <div class="hashtags-list">
                <span v-for="hashtag in getCityHashtags(country, region, city)" :key="hashtag" class="hashtag">#{{ hashtag }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, computed } from 'vue'

export default {
  name: 'GeoHashtagsView',
  setup() {
    const geoHashtags = ref({})
    const loading = ref(true)
    const error = ref(null)

    const loadGeoHashtags = async () => {
      try {
        const response = await fetch('/api/v1/geo-hashtags')
        if (!response.ok) throw new Error('Failed to load hashtags')
        geoHashtags.value = await response.json()
      } catch (err) {
        error.value = err.message
      } finally {
        loading.value = false
      }
    }

    const hierarchy = computed(() => {
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
    })

    const getCountryFlag = (country) => {
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
    }

    const getCountryHashtagCount = (country) => {
      return Object.values(geoHashtags.value).filter(entry => entry.country === country).length
    }

    const getCountryOnlyHashtags = (country) => {
      return Object.entries(geoHashtags.value)
        .filter(([_, entry]) => entry.country === country && !entry.region && !entry.city)
        .map(([hashtag]) => hashtag)
    }

    const getCountryRegions = (country) => {
      return hierarchy.value.regions[country] || []
    }

    const getRegionHashtagCount = (country, region) => {
      return Object.values(geoHashtags.value)
        .filter(entry => entry.country === country && entry.region === region).length
    }

    const getRegionOnlyHashtags = (country, region) => {
      return Object.entries(geoHashtags.value)
        .filter(([_, entry]) => entry.country === country && entry.region === region && !entry.city)
        .map(([hashtag]) => hashtag)
    }

    const getRegionCities = (country, region) => {
      return hierarchy.value.cities[`${country}:${region}`] || []
    }

    const getCityHashtagCount = (country, region, city) => {
      return Object.values(geoHashtags.value)
        .filter(entry => entry.country === country && entry.region === region && entry.city === city).length
    }

    const getCityHashtags = (country, region, city) => {
      return Object.entries(geoHashtags.value)
        .filter(([_, entry]) => entry.country === country && entry.region === region && entry.city === city)
        .map(([hashtag]) => hashtag)
    }

    onMounted(loadGeoHashtags)

    return {
      geoHashtags,
      loading,
      error,
      hierarchy,
      getCountryFlag,
      getCountryHashtagCount,
      getCountryOnlyHashtags,
      getCountryRegions,
      getRegionHashtagCount,
      getRegionOnlyHashtags,
      getRegionCities,
      getCityHashtagCount,
      getCityHashtags
    }
  }
}
</script>

<style scoped>
.geo-hashtags-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 40px 20px;
  background: #f8f9fa;
  min-height: 100vh;
}

.header {
  text-align: center;
  margin-bottom: 40px;
  padding-bottom: 20px;
  border-bottom: 2px solid #e0e0e0;
}

.header h1 {
  margin: 0 0 10px 0;
  color: #2c3e50;
  font-size: 2.5em;
}

.header p {
  margin: 0;
  color: #666;
  font-size: 1.1em;
  font-style: italic;
}

.loading, .error {
  text-align: center;
  padding: 40px;
  font-size: 1.2em;
}

.error {
  color: #dc3545;
}

.country-section {
  margin-bottom: 40px;
  background: white;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 6px rgba(0,0,0,0.1);
}

.country-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 20px 30px;
  display: flex;
  align-items: center;
  gap: 15px;
  font-size: 1.3em;
}

.flag {
  font-size: 1.5em;
}

.country-content {
  padding: 30px;
}

.region-section {
  margin: 25px 0;
  padding-left: 25px;
  border-left: 4px solid #007bff;
}

.region-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 15px;
  color: #007bff;
  font-size: 1.1em;
}

.city-section {
  margin: 20px 0;
  padding-left: 25px;
  border-left: 3px solid #28a745;
}

.city-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  color: #28a745;
  font-size: 1.05em;
}

.hashtags-section {
  margin: 15px 0;
}

.hashtags-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.hashtag {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 8px 16px;
  border-radius: 20px;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 0.95em;
  font-weight: 600;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  transition: transform 0.2s;
}

.hashtag:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0,0,0,0.15);
}

.hashtag-count {
  color: rgba(255,255,255,0.8);
  font-size: 0.9em;
  font-weight: normal;
}

.region-header .hashtag-count,
.city-header .hashtag-count {
  color: #666;
}
</style>