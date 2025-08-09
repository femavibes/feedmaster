<template>
  <div class="view-container">
    <div class="header">
      <h1>Recent Posts</h1>
    </div>
    <div v-if="loading" class="loading">Loading posts for {{ feedStore.selectedFeed?.name }}...</div>
    <div v-if="error" class="error">{{ error }}</div>
    <div v-if="posts.length" class="posts-list" @scroll="handleScroll">
      <div class="post-item" v-for="post in posts" :key="post.uri">
        <div class="post-author clickable" @click="openUserModal(post.author)">
          <img :src="proxyImageUrl(post.author.avatar_url)" alt="avatar" class="avatar" @error="onAvatarError" />
          <div class="author-info">
            <span class="display-name">{{ post.author.display_name || post.author.handle }}</span>
            <span class="handle">@{{ post.author.handle }}</span>
          </div>
        </div>
        <div class="post-text">
          <template v-for="(part, index) in parsePostText(post.text, post)" :key="index">
            <span v-if="part.type === 'text'">{{ part.content }}</span>
            <span v-else-if="part.type === 'mention' && part.exists" class="mention-link" @click="openUserModalByHandle(part.handle)">{{ part.content }}</span>
            <span v-else-if="part.type === 'mention' && !part.exists" class="mention-inactive" title="User not in our database">{{ part.content }}</span>
            <span v-else-if="part.type === 'hashtag'" class="hashtag-link" @click="openHashtagModal(part.hashtag)">{{ part.content }}</span>
            <a v-else-if="part.type === 'link'" class="text-link" :href="part.url" target="_blank" rel="noopener noreferrer" :title="part.url">{{ part.content }}</a>
            <br v-else-if="part.type === 'newline'" />
          </template>
        </div>
        <a :href="getPostUrl(post)" target="_blank" rel="noopener noreferrer" class="post-meta clickable-meta">
          <span>♡ {{ post.like_count }}</span>
          <span>↻ {{ post.repost_count }}</span>
          <span>↳ {{ post.reply_count }}</span>
          <span class="bluesky-icon">🦋</span>
          <span class="post-time">{{ useRelativeTime ? formatRelativeTime(post.created_at) : new Date(post.created_at).toLocaleString() }}</span>
        </a>
      </div>
      
      <!-- Loading more indicator -->
      <div v-if="loadingMore" class="loading-more">
        Loading more posts...
      </div>
      
      <!-- End of posts indicator -->
      <div v-if="!hasMore && posts.length >= MAX_POSTS" class="end-of-posts">
        Showing latest {{ MAX_POSTS }} posts
      </div>
      <div v-else-if="!hasMore && !loadingMore" class="end-of-posts">
        No more posts to load
      </div>
    </div>
    
    <HashtagModal 
      :isVisible="showHashtagModal" 
      :hashtag="selectedHashtag" 
      :feedId="feedStore.selectedFeedId" 
      @close="closeHashtagModal" 
      @openUserModal="openUserModal" 
    />
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue';
import { useRoute } from 'vue-router';
import { useFeedStore } from '@/stores/useFeedStore';
import apiService from '@/apiService';
import HashtagModal from '@/components/HashtagModal.vue';
import { proxyImageUrl } from '@/utils/imageProxy';
import { formatRelativeTime } from '@/utils/timeFormat';

const route = useRoute();
const posts = ref([]);
const loading = ref(true);
const error = ref(null);
const mentionUserCache = ref(new Map());
const loadingMore = ref(false);
const hasMore = ref(true);
const currentPage = ref(0);
const POSTS_PER_PAGE = 50;
const MAX_POSTS = 150;
const showHashtagModal = ref(false);
const selectedHashtag = ref(null);
const useRelativeTime = ref(true);

const feedStore = useFeedStore();

let currentFetchController = null;

const fetchPosts = async (feedId, reset = true) => {
  if (!feedId) return;
  
  // Cancel any ongoing request
  if (currentFetchController) {
    currentFetchController.abort();
  }
  
  // Create new abort controller for this request
  currentFetchController = new AbortController();
  
  if (reset) {
    loading.value = true;
    error.value = null;
    posts.value = [];
    currentPage.value = 0;
    hasMore.value = true;
  } else {
    loadingMore.value = true;
  }
  
  const skip = reset ? 0 : currentPage.value * POSTS_PER_PAGE;
  
  try {
    const response = await fetch(`/api/v1/feeds/${feedId}/posts?limit=${POSTS_PER_PAGE}&skip=${skip}`);
    if (!response.ok) throw new Error('Failed to fetch posts');
    
    const data = await response.json();
    const fetchedPosts = data.posts || [];
    
    // Only update if this is still the current request
    if (currentFetchController && !currentFetchController.signal.aborted) {
      // Process mentions for new posts
      await processMentionsForPosts(fetchedPosts);
      
      if (reset) {
        posts.value = fetchedPosts;
      } else {
        posts.value = [...posts.value, ...fetchedPosts];
      }
      
      currentPage.value++;
      
      // Check if we have more posts to load
      hasMore.value = fetchedPosts.length === POSTS_PER_PAGE && posts.value.length < MAX_POSTS;
    }
  } catch (err) {
    // Only show error if this is still the current request
    if (currentFetchController && !currentFetchController.signal.aborted) {
      console.error('Posts fetch error:', err);
      error.value = `Failed to load posts. Please try again.`;
    }
  } finally {
    // Only update loading state if this is still the current request
    if (currentFetchController && !currentFetchController.signal.aborted) {
      loading.value = false;
      loadingMore.value = false;
    }
  }
};

const loadMorePosts = () => {
  if (!loadingMore.value && hasMore.value && feedStore.selectedFeedId) {
    fetchPosts(feedStore.selectedFeedId, false);
  }
};

const handleScroll = (event) => {
  const { scrollTop, scrollHeight, clientHeight } = event.target;
  if (scrollTop + clientHeight >= scrollHeight - 100 && hasMore.value && !loadingMore.value) {
    loadMorePosts();
  }
};

const onAvatarError = (event) => {
  event.target.src = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxIDEiPjwvc3ZnPg==';
};

const prettifyUrl = (url) => {
  try {
    const urlObj = new URL(url)
    let hostname = urlObj.hostname
    
    // Remove www. prefix
    if (hostname.startsWith('www.')) {
      hostname = hostname.substring(4)
    }
    
    // Remove mobile prefixes that aren't useful
    if (hostname.startsWith('m.')) {
      hostname = hostname.substring(2)
    }
    
    return hostname + '...'
  } catch {
    // If URL parsing fails, just clean up the string
    return url.replace(/^https?:\/\/(www\.)?/, '').split('/')[0] + '...'
  }
}

const getPostUrl = (post) => {
  const postRkey = post.uri.split('/').pop()
  const authorHandle = post.author.handle
  return `https://bsky.app/profile/${authorHandle}/post/${postRkey}`
}

const emit = defineEmits(['openUserModal'])

const openUserModal = (user) => {
  emit('openUserModal', {
    did: user.did,
    handle: user.handle,
    display_name: user.display_name,
    avatar_url: user.avatar_url
  })
}

const openHashtagModal = (hashtag) => {
  selectedHashtag.value = hashtag
  showHashtagModal.value = true
}

const closeHashtagModal = () => {
  showHashtagModal.value = false
  selectedHashtag.value = null
}

const processMentionsForPosts = async (posts) => {
  // Extract all unique mentions from all posts
  const allMentions = new Set()
  posts.forEach(post => {
    if (post.text) {
      const mentionMatches = post.text.match(/@([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63}/g)
      if (mentionMatches) {
        mentionMatches.forEach(mention => {
          const handle = mention.substring(1)
          allMentions.add(handle)
        })
      }
    }
  })
  
  // Check which users exist in our database
  for (const handle of allMentions) {
    if (!mentionUserCache.value.has(handle)) {
      try {
        const response = await fetch(`/api/v1/search?q=${encodeURIComponent(handle)}`)
        if (response.ok) {
          const data = await response.json()
          const user = data.users?.find(u => u.handle === handle)
          mentionUserCache.value.set(handle, user || null)
        } else {
          mentionUserCache.value.set(handle, null)
        }
      } catch (error) {
        console.error('Error checking user:', error)
        mentionUserCache.value.set(handle, null)
      }
    }
  }
}

const openUserModalByHandle = async (handle) => {
  const user = mentionUserCache.value.get(handle)
  if (user) {
    openUserModal(user)
  }
}

const parsePostText = (text, post) => {
  if (!text) return [{ type: 'text', content: 'No content.' }]
  
  const parts = []
  // Create a map of shortened URLs to full URLs from the post's links array
  const linkMap = {}
  if (post?.links) {
    post.links.forEach(link => {
      // Extract the shortened URL from the full URL (everything after the last slash)
      const shortUrl = link.uri.split('/').pop()
      if (shortUrl && text.includes(shortUrl)) {
        linkMap[shortUrl] = link.uri
      }
      // Also check for domain matches
      const domain = link.uri.replace(/^https?:\/\//, '').split('/')[0]
      if (text.includes(domain)) {
        linkMap[domain] = link.uri
      }
    })
  }
  
  // Combined regex for mentions, hashtags, and URLs (including truncated ones)
  const combinedRegex = /(@([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63})|(#[a-zA-Z0-9_]+)|(https?:\/\/[^\s]+(?:\.\.\.)?)|([a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:\/[^\s]*)?(?:\.\.\.)?)/g
  
  let lastIndex = 0
  let match
  
  while ((match = combinedRegex.exec(text)) !== null) {
    // Add text before match
    if (match.index > lastIndex) {
      const beforeText = text.slice(lastIndex, match.index)
      parts.push(...splitByNewlines(beforeText))
    }
    
    const fullMatch = match[0]
    if (fullMatch.startsWith('@')) {
      // It's a mention - check if user exists in our database
      const handle = fullMatch.substring(1)
      const user = mentionUserCache.value.get(handle)
      if (user) {
        parts.push({ type: 'mention', content: fullMatch, handle, exists: true })
      } else {
        parts.push({ type: 'mention', content: fullMatch, handle, exists: false })
      }
    } else if (fullMatch.startsWith('#')) {
      // It's a hashtag
      const hashtag = fullMatch.substring(1)
      parts.push({ type: 'hashtag', content: fullMatch, hashtag })
    } else if (fullMatch.startsWith('http')) {
      // It's a full URL
      const displayText = prettifyUrl(fullMatch)
      parts.push({ type: 'link', content: displayText, url: fullMatch })
    } else {
      // It's a domain or truncated URL - find the matching full URL
      let fullUrl = fullMatch
      
      // Check if this truncated text matches any of our full URLs
      if (post?.links) {
        for (const link of post.links) {
          const cleanMatch = fullMatch.replace(/\.\.\.$/, '') // Remove trailing ...
          if (link.uri.includes(cleanMatch) || link.uri.startsWith(`https://${cleanMatch}`)) {
            fullUrl = link.uri
            break
          }
        }
      }
      
      // If no match found and it doesn't start with http, add https://
      if (fullUrl === fullMatch && !fullUrl.startsWith('http')) {
        fullUrl = `https://${fullMatch.replace(/\.\.\.$/, '')}`
      }
      
      const displayText = prettifyUrl(fullUrl)
      parts.push({ type: 'link', content: displayText, url: fullUrl })
    }
    
    lastIndex = match.index + match[0].length
  }
  
  // Add remaining text
  if (lastIndex < text.length) {
    const remainingText = text.slice(lastIndex)
    parts.push(...splitByNewlines(remainingText))
  }
  
  return parts
}

const splitByNewlines = (text) => {
  const parts = []
  const lines = text.split('\n')
  
  for (let i = 0; i < lines.length; i++) {
    if (lines[i]) {
      parts.push({ type: 'text', content: lines[i] })
    }
    if (i < lines.length - 1) {
      parts.push({ type: 'newline' })
    }
  }
  
  return parts
}

const loadSettings = () => {
  const settings = JSON.parse(localStorage.getItem('feedmaster-settings') || '{}')
  useRelativeTime.value = settings.showTimestamps !== false
}

// Watch for settings changes
const watchSettings = () => {
  // Listen for custom settings-changed event for immediate updates
  window.addEventListener('settings-changed', (e) => {
    useRelativeTime.value = e.detail.showTimestamps !== false
  })
  
  // Also listen for localStorage changes (for other tabs)
  window.addEventListener('storage', (e) => {
    if (e.key === 'feedmaster-settings') {
      loadSettings()
    }
  })
}

onMounted(() => {
  loadSettings()
  watchSettings()
})

// Watch route parameter and update store
watch(() => route.params.feed_id, (newFeedId) => {
  if (newFeedId) {
    feedStore.selectedFeedId = newFeedId;
    fetchPosts(newFeedId, true);
    
    // Fallback timeout to prevent infinite loading
    const timeoutId = setTimeout(() => {
      if (loading.value && !error.value) {
        console.warn('Posts loading timeout, forcing completion');
        loading.value = false;
        if (posts.value.length === 0) {
          error.value = 'Loading timed out. Please refresh the page.';
        }
      }
    }, 15000); // 15 second timeout
    
    // Clear timeout if posts load successfully
    const checkLoaded = setInterval(() => {
      if (!loading.value || posts.value.length > 0) {
        clearTimeout(timeoutId);
        clearInterval(checkLoaded);
      }
    }, 100);
  }
}, { immediate: true });


</script>

<style scoped>
.view-container {
  /* This is the "box" styling that used to be in App.vue's .main-content */
  background-color: var(--bg-secondary);
  border-radius: 8px;
  padding: 1.5rem 2rem;
  height: 100%;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
}

h1 {
  font-size: 1.2rem;
  color: var(--text-primary);
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}

.loading, .error {
  text-align: center;
  padding: 2rem;
  font-size: 1.2rem;
}

.error {
  color: #e57373;
}

.posts-list {
  overflow-y: auto;
  flex-grow: 1;
  /* Hide scrollbar for Firefox */
  scrollbar-width: none;
  /* Remove padding that was making space for the scrollbar */
  padding-right: 0;
}

.posts-list::-webkit-scrollbar {
  display: none; /* Hide scrollbar for Webkit browsers (Chrome, Safari, Edge) */
}

.post-item {
  background-color: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 1rem;
  margin-bottom: 1rem;
}

.header {
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 1rem;
  margin-bottom: 1.5rem;
}

.post-author { display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.75rem; }
.post-author.clickable { cursor: pointer; transition: all 0.2s ease; border-radius: 6px; padding: 8px; margin: -8px -8px 0.75rem -8px; }
.post-author.clickable:hover { background-color: var(--bg-tertiary); transform: translateY(-1px); }
.avatar { width: 40px; height: 40px; border-radius: 50%; object-fit: cover; }
.author-info { display: flex; flex-direction: column; }
.display-name { font-weight: bold; color: var(--text-primary); }
.handle { color: var(--text-muted); font-size: 0.9rem; }
.post-text { white-space: pre-wrap; word-break: break-word; margin-bottom: 1rem; color: var(--text-primary); }
.mention-link { color: #5865f2; cursor: pointer; font-weight: bold; }
.mention-link:hover { text-decoration: underline; }
.mention-inactive { color: var(--text-muted); font-weight: bold; cursor: help; }
.hashtag-link { color: #00d4aa; cursor: pointer; font-weight: bold; }
.hashtag-link:hover { text-decoration: underline; }
.text-link { color: #00aff4; font-weight: bold; text-decoration: none; }
.text-link:hover { text-decoration: underline; }
.post-meta { display: flex; gap: 1rem; font-size: 0.85rem; color: var(--text-muted); border-top: 1px solid var(--border-color); padding-top: 0.75rem; margin-top: 1rem; align-items: center; }
.post-meta span { color: var(--text-muted); }
.clickable-meta { text-decoration: none; color: inherit; transition: all 0.2s ease; border-radius: 4px; padding: 0.25rem; margin: -0.25rem; }
.clickable-meta:hover { background-color: var(--bg-tertiary); transform: translateY(-1px); }
.bluesky-icon { flex-grow: 1; text-align: center; font-size: 0.9rem; }
.post-time { margin-left: auto; }
.loading-more, .end-of-posts { text-align: center; padding: 1rem; color: var(--text-muted); font-size: 0.9rem; }
.end-of-posts { border-top: 1px solid var(--border-color); margin-top: 1rem; }


</style>