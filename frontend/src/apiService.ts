import axios from 'axios';
import { useFeedStore } from '@/stores/useFeedStore';

// Use full HTTPS URL when served over HTTPS, otherwise use relative path
const API_BASE_URL = window.location.protocol === 'https:' 
  ? `https://${window.location.host}/api/v1`
  : (import.meta.env.VITE_API_BASE_URL || '/api/v1');
console.log('API_BASE_URL configured as:', API_BASE_URL);

// Create axios instance with explicit HTTPS configuration
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
});

const apiService = {
  async fetchFeeds() {
    const store = useFeedStore();
    store.setLoading(true);
    store.setError(null);
    try {
      const fullUrl = `${API_BASE_URL}/feeds/`;
      console.log('Attempting to fetch feeds from:', fullUrl);
      const response = await fetch(fullUrl, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json'
        }
      });
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      console.log('Response from /api/v1/feeds:', data);
      store.setFeeds(data.feeds);
      if (data.feeds.length > 0 && !store.selectedFeedId) {
        store.selectFeed(data.feeds[0].id);
      }
    } catch (error) {
      console.error('Error fetching feeds:', error);
      store.setError('Failed to fetch feeds.');
    } finally {
      store.setLoading(false);
    }
  },

  async fetchPosts(feedId: string, retries = 2) {
    for (let attempt = 0; attempt <= retries; attempt++) {
      try {
        const response = await apiClient.get(`/feeds/${feedId}/posts?limit=50`);
        return response.data.posts;
      } catch (error) {
        console.error(`Failed to fetch posts for feed ${feedId} (attempt ${attempt + 1}):`, error);
        
        // If this is the last attempt, throw the error
        if (attempt === retries) {
          throw new Error('Failed to fetch posts.');
        }
        
        // Wait before retrying (exponential backoff)
        await new Promise(resolve => setTimeout(resolve, Math.pow(2, attempt) * 1000));
      }
    }
  },

  async fetchAggregates(feedId: string, timeframe: string) {
    try {
      const response = await apiClient.get(`/feeds/${feedId}/aggregates_all?timeframe=${timeframe}`);
      console.log('Response from /api/v1/feeds/{feed_id}/aggregates_all:', response.data);
      return response.data;
    } catch (error) {
      console.error(`Failed to fetch aggregates for feed ${feedId}:`, error);
      throw new Error('Failed to fetch aggregates.');
    }
  },

  // User profile methods
  async get(endpoint: string) {
    try {
      const response = await apiClient.get(endpoint);
      return response;
    } catch (error) {
      console.error(`Failed to fetch ${endpoint}:`, error);
      throw error;
    }
  },
};

export default apiService;
