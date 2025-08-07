<template>
  <div class="leaderboard">
    <h1>Engagement Leaderboard</h1>
    <p class="subtitle">Top 50 most engaging users in the last 24 hours.</p>
    <div v-if="loading" class="loading">Loading...</div>
    <div v-if="error" class="error">{{ error }}</div>
    <div v-if="leaderboardData.length" class="leaderboard-grid">
      <div class="leaderboard-item" v-for="item in leaderboardData" :key="item.did">
        <div class="rank">{{ item.rank }}</div>
        <div class="profile">
          <img :src="item.avatar" alt="avatar" class="avatar" @error="onAvatarError" />
          <div class="profile-info">
            <a :href="`https://bsky.app/profile/${item.did}`" target="_blank" class="display-name">{{ item.display_name || item.handle }}</a>
            <span class="handle">@{{ item.handle }}</span>
          </div>
        </div>
        <div class="score">{{ item.score.toLocaleString() }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import axios from 'axios';

const leaderboardData = ref([]);
const loading = ref(true);
const error = ref(null);

// This should be configured more robustly in a real app, e.g., via environment variables
const API_BASE_URL = 'http://localhost:8000/api/v1';

const fetchLeaderboard = async () => {
  try {
    // Fetch the top 50 users from the last 24 hours
    const response = await axios.get(`${API_BASE_URL}/leaderboards/engagement?timeframe=24h&limit=50`);
    leaderboardData.value = response.data.map((item, index) => ({
      ...item,
      rank: index + 1,
    }));
  } catch (err) {
    console.error('Failed to fetch leaderboard:', err);
    error.value = 'Failed to load leaderboard data. Please try again later.';
  } finally {
    loading.value = false;
  }
};

const onAvatarError = (event) => {
  // Replace broken avatar images with a default placeholder
  event.target.src = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxIDEiPjwvc3ZnPg==';
};

onMounted(() => {
  fetchLeaderboard();
});
</script>

<style scoped>
.leaderboard {
  font-family: sans-serif;
}
.subtitle {
  color: #666;
  margin-bottom: 2rem;
}
.loading, .error {
  text-align: center;
  padding: 2rem;
  font-size: 1.2rem;
}
.error {
  color: #e53e3e;
}
.leaderboard-grid {
  display: grid;
  gap: 1px;
  background-color: #e2e8f0;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
}
.leaderboard-item {
  display: grid;
  grid-template-columns: 50px 1fr 100px;
  align-items: center;
  gap: 1rem;
  padding: 0.75rem 1rem;
  background-color: #fff;
}
.rank {
  font-size: 1.1rem;
  font-weight: bold;
  color: #718096;
  text-align: center;
}
.profile {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
.avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  object-fit: cover;
}
.profile-info {
  display: flex;
  flex-direction: column;
}
.display-name {
  font-weight: bold;
  color: #2d3748;
}
.handle {
  color: #718096;
  font-size: 0.9rem;
}
.score {
  font-size: 1.1rem;
  font-weight: 500;
  text-align: right;
  color: #2c5282;
}
</style>
