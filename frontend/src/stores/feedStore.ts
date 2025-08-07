import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'


// Define a type for our feed objects for better type safety
export interface Feed {
  id: string;
  name: string;
  icon: string; // e.g., 'U' or avatar URL
  avatar_url?: string; // Avatar URL from Bluesky
  like_count?: number; // Feed likes from Bluesky
  bluesky_description?: string; // Feed description from Bluesky
  order?: number; // Optional order field for sorting
}

export const useFeedStore = defineStore('feed', () => {
  const router = useRouter();
  // --- STATE ---
  const availableFeeds = ref<Feed[]>([])
  const feedsLoading = ref(false)
  const feedsError = ref<string | null>(null)

  // The currently selected feed. Default to the first one.
  const selectedFeedId = ref<string | null>(null)

  // --- GETTERS ---

  // A computed property to get the full object of the currently selected feed.
  const selectedFeed = computed(() =>
    availableFeeds.value.find((feed) => feed.id === selectedFeedId.value),
  )

  // --- ACTIONS ---

  // Action to change the selected feed.
  function selectFeed(feedId: string) {
    selectedFeedId.value = feedId
    router.push(`/feed/${feedId}`);
  }

  async function fetchAvailableFeeds() {
    feedsLoading.value = true
    feedsError.value = null
    try {
      // NOTE: This API endpoint is hypothetical. It needs to be created in the backend.
      await apiService.fetchFeeds();
    } catch (err) {
      console.error('Failed to fetch available feeds:', err)
      feedsError.value = 'Could not load feeds.'
    } finally {
      feedsLoading.value = false
    }
  }

  return { availableFeeds, feedsLoading, feedsError, selectedFeedId, selectedFeed, selectFeed, fetchAvailableFeeds }
})