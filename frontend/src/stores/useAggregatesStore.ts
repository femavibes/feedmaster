import { defineStore } from 'pinia';
import { ref } from 'vue';
import type { AggregateData } from '@/types/aggregates';
import apiService from '@/apiService';

export const useAggregatesStore = defineStore('aggregates', () => {
  const aggregates = ref<AggregateData | null>(null);
  const loading = ref(false);
  const error = ref<string | null>(null);

  const fetchAggregates = async (feedId: string, timeframe: string) => {
    loading.value = true;
    error.value = null;
    try {
      aggregates.value = await apiService.getAggregates(feedId, timeframe);
    } catch (err) {
      error.value = 'Failed to fetch aggregates';
      console.error(err);
    } finally {
      loading.value = false;
    }
  };

  return { aggregates, loading, error, fetchAggregates };
});
