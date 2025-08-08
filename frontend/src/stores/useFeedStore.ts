import { defineStore } from 'pinia';

export const useFeedStore = defineStore('feed', {
  state: () => ({
    availableFeeds: [],
    selectedFeedId: null,
    feedsLoading: false,
    feedsError: null,
  }),
  getters: {
    selectedFeed: (state) => {
      return state.availableFeeds.find(feed => feed.id === state.selectedFeedId);
    },
  },
  actions: {
    selectFeed(feedId) {
      this.selectedFeedId = feedId;
    },
    setFeeds(feeds) {
      this.availableFeeds = feeds;
    },
    setLoading(loading) {
      this.feedsLoading = loading;
    },
    setError(error) {
      this.feedsError = error;
    },
  },
});