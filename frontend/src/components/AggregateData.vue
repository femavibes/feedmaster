<template>
  <aside class="aggregate-data-container">
    <div v-if="feedStore.selectedFeed" class="content-wrapper">
      <div class="header">
        <h2>Aggregates</h2>
        <div class="timeframe-selector">
          <button
            v-for="tf in timeframes"
            :key="tf.value"
            :class="{ active: selectedTimeframe === tf.value }"
            @click="selectedTimeframe = tf.value"
          >
            {{ tf.label }}
          </button>
        </div>
      </div>

      <div v-if="loading" class="state-message">Loading stats...</div>
      <div v-if="error" class="state-message error">{{ error }}</div>

      <div v-if="!loading && !error && aggregates" class="stats-grid">
        <TopPostersCard class="posters-card" :users="aggregates.top_posters_by_count" :topUsers="aggregates.top_users || []" :topMentions="aggregates.top_mentions || []" :key="`users-${feedStore.selectedFeedId}-${selectedTimeframe}`" @openUserModal="openUserModal" />
        <TopHashtagsCard class="hashtags-card" :hashtags="aggregates.top_hashtags" :key="`hashtags-${feedStore.selectedFeedId}-${selectedTimeframe}`" @openHashtagModal="openHashtagModal" />
        <FirstTimePostersCard class="first-time-posters-card" :firstTimePosters="aggregates.first_time_posters || []" @openUserModal="openUserModal" />
        <TabbedMediaCards class="media-cards" :videos="aggregates.top_videos || []" :images="aggregates.top_images || []" />
        <TopLinksCard class="links-card" :links="aggregates.top_links" :domains="aggregates.top_domains || []" />
        <TabbedLinkCards class="news-links-card" :newsLinks="aggregates.top_news_links" :linkCards="aggregates.top_link_cards" />
        <TabbedStreakCards class="streak-cards" :activeStreaks="aggregates.active_streaks" :longestStreaks="aggregates.longest_streaks" />
        <TabbedGeoCards class="geo-cards" :cities="aggregates.top_cities || []" :regions="aggregates.top_regions || []" :countries="aggregates.top_countries || []" />
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ref, watch, computed, inject } from 'vue'
import { useFeedStore } from '@/stores/useFeedStore'
import { type Aggregates } from '@/types/aggregates'
import TopHashtagsCard from './aggregate_cards/TopHashtagsCard.vue'
import TopPostersCard from './aggregate_cards/TopPostersCard.vue'
import TabbedLinkCards from './aggregate_cards/TabbedLinkCards.vue'
import TabbedStreakCards from './aggregate_cards/TabbedStreakCards.vue'
import TabbedGeoCards from './aggregate_cards/TabbedGeoCards.vue'
import TabbedMediaCards from './aggregate_cards/TabbedMediaCards.vue'
import FirstTimePostersCard from './aggregate_cards/FirstTimePostersCard.vue'
import TopLinksCard from './aggregate_cards/TopLinksCard.vue'

const apiService = inject('apiService');

// Define types for the data we expect from the API.



const timeframes = [
  { value: '1h', label: '1H' },
  { value: '6h', label: '6H' },
  { value: '1d', label: '1D' },
  { value: '7d', label: '7D' },
  { value: '30d', label: '30D' },
  { value: 'allTime', label: 'All' },
];
const selectedTimeframe = ref('1d');

const aggregates = ref<Aggregates | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

const feedStore = useFeedStore()

const emit = defineEmits(['openUserModal'])

const openUserModal = (user: any) => {
  emit('openUserModal', user)
}

const openHashtagModal = (hashtag: string) => {
  emit('openHashtagModal', hashtag)
}



const fetchAggregates = async (feedId: string | undefined, timeframe: string) => {
  console.log('fetchAggregates called:', feedId, timeframe);
  if (!feedId) return

  loading.value = true
  error.value = null
  // Don't reset aggregates to null to prevent flash

  try {
    let rawAggregates = await apiService.fetchAggregates(feedId, timeframe);

    // The API response for aggregates might now be wrapped in a 'data' property.
    if (rawAggregates && rawAggregates.data && typeof rawAggregates.data === 'object') {
      rawAggregates = rawAggregates.data;
    }

    console.log('Raw aggregates:', rawAggregates);
    
    // The backend now returns flat arrays directly
    const transformedAggregates: Aggregates = {
      top_hashtags: rawAggregates?.top_hashtags || [],
      top_users: rawAggregates?.top_users || [],
      top_posters_by_count: rawAggregates?.top_posters_by_count || [],
      top_mentions: rawAggregates?.top_mentions || [],
      longest_streaks: rawAggregates?.longest_poster_streaks || [],
      active_streaks: rawAggregates?.active_poster_streaks || [],
      top_news_links: rawAggregates?.top_news_link_cards || [],
      top_links: rawAggregates?.top_links || [],
      top_link_cards: rawAggregates?.top_link_cards || [],
      top_videos: rawAggregates?.top_videos || [],
      top_images: rawAggregates?.top_images || [],
      top_cities: rawAggregates?.top_cities || [],
      top_regions: rawAggregates?.top_regions || [],
      top_countries: rawAggregates?.top_countries || [],
      first_time_posters: rawAggregates?.first_time_posters || [],
      top_domains: rawAggregates?.top_domains || [],
    };
    
    console.log('Transformed aggregates:', transformedAggregates);

    aggregates.value = transformedAggregates;
  } catch (err) {
    console.error(`Failed to fetch aggregates for feed ${feedId}:`, err)
    error.value = `Failed to load aggregate data. Please ensure the backend is running and the data has been aggregated.`
  } finally {
    loading.value = false
  }
}

// Watch for changes in the selected feed ID and re-fetch aggregates.
watch([() => feedStore.selectedFeedId, selectedTimeframe], ([newFeedId, newTimeframe]) => {
  console.log('Watcher triggered:', newFeedId, newTimeframe);
  fetchAggregates(newFeedId, newTimeframe)
}, { immediate: true })
</script>

<style scoped>
.aggregate-data-container {
  grid-area: sidebar;
  background-color: #313338;
  border-radius: 8px;
  overflow: hidden;
  height: 100%;
}
.content-wrapper {
  padding: 1.5rem;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #404249;
  padding-bottom: 1rem;
  margin-bottom: 1.5rem;
}

h2 {
  color: #fff;
  font-size: 1.2rem;
  margin-top: 0;
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}

.timeframe-selector {
  display: flex;
  gap: 4px;
  background-color: #2b2d31;
  border-radius: 6px;
  padding: 4px;
}

.timeframe-selector button {
  background-color: transparent;
  border: none;
  color: #b5bac1;
  padding: 4px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 600;
  transition: all 0.2s ease;
}

.timeframe-selector button.active {
  background-color: #404249;
  color: #fff;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  grid-template-rows: repeat(4, 1fr);
  gap: 1rem;
  height: calc(100vh - 200px);
}

.posters-card { grid-column: 1 / 4; grid-row: 1 / 3; }
.hashtags-card { grid-column: 11 / 13; grid-row: 1 / 3; }
.first-time-posters-card { grid-column: 11 / 13; grid-row: 3 / 5; }
.media-cards { grid-column: 8 / 11; grid-row: 1 / 3; }
.streak-cards { grid-column: 1 / 4; grid-row: 3 / 5; }

.news-links-card { grid-column: 4 / 8; grid-row: 1 / 3; }
.geo-cards { grid-column: 4 / 8; grid-row: 3 / 5; }
.links-card { grid-column: 8 / 11; grid-row: 3 / 5; }

.stats-grid > * {
  overflow-y: auto;
  scrollbar-width: none;
}

.stats-grid > *::-webkit-scrollbar {
  display: none;
}
.state-message { text-align: center; padding: 2rem; color: #949ba4; }
.error { color: #e57373;
}
</style>