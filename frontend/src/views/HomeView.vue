<template>
  <div class="home-view">
    <div v-if="feedStore.feedsLoading" class="loading-indicator">
      Loading feeds...
    </div>
    <div v-else-if="feedStore.feedsError" class="error-message">
      {{ feedStore.feedsError }}
    </div>
    <div v-else-if="feedStore.availableFeeds.length > 0" class="feed-selection">
      <label for="feed-select">Select a Feed:</label>
      <select id="feed-select" v-model="feedStore.selectedFeedId">
        <option v-for="feed in feedStore.availableFeeds" :key="feed.id" :value="feed.id">
          {{ feed.name }}
        </option>
      </select>
    </div>
    <div v-else class="no-feeds">
      No feeds available.
    </div>

    <div v-if="aggregatesStore.loading" class="loading-indicator">
      Loading aggregates...
    </div>
    <div v-else-if="aggregatesStore.error" class="error-message">
      {{ aggregatesStore.error }}
    </div>
    <div v-else-if="aggregatesStore.aggregates" class="aggregates-container">
      <component
        v-for="(item, index) in aggregatesStore.aggregates.top"
        :key="index"
        :is="getCardComponent(item.type)"
        :item="item"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { watch } from 'vue';
import { useFeedStore } from '@/stores/useFeedStore';
import { useAggregatesStore } from '@/stores/useAggregatesStore';
import TopHashtagsCard from '@/components/aggregate_cards/TopHashtagsCard.vue';
import TopPostersCard from '@/components/aggregate_cards/TopPostersCard.vue';
import TopLinkCard from '@/components/aggregate_cards/TopLinkCard.vue';

const feedStore = useFeedStore();
const aggregatesStore = useAggregatesStore();

const getCardComponent = (type: string) => {
  switch (type) {
    case 'hashtag':
      return TopHashtagsCard;
    case 'user':
      return TopPostersCard;
    case 'link_card':
      return TopLinkCard;
    default:
      return null;
  }
};

watch(() => feedStore.selectedFeedId, (newFeedId) => {
  if (newFeedId) {
    aggregatesStore.fetchAggregates(newFeedId, '24h');
  }
}, { immediate: true });
</script>

<style scoped>
.home-view {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1rem;
}

.loading-indicator, .error-message, .no-feeds {
  text-align: center;
  padding: 2rem;
  font-size: 1.2rem;
}

.error-message {
  color: #e57373;
}

.feed-selection {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background-color: #313338;
  padding: 1rem;
  border-radius: 8px;
}

.feed-selection label {
  font-weight: bold;
  color: #dcddde;
}

.feed-selection select {
  padding: 0.5rem;
  border-radius: 5px;
  border: 1px solid #404249;
  background-color: #2b2d31;
  color: #dcddde;
  cursor: pointer;
}

.feed-selection select:focus {
  outline: none;
  border-color: #5865f2;
}

.aggregates-container {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1rem;
}
</style>
