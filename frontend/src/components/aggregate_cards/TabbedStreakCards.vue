<template>
  <div class="tabbed-streak-cards">
    <div class="tab-header">
      <button 
        :class="{ active: activeTab === 'active' }" 
        @click="activeTab = 'active'"
      >
        Active Streaks
      </button>
      <button 
        :class="{ active: activeTab === 'longest' }" 
        @click="activeTab = 'longest'"
      >
        Longest Streaks
      </button>
    </div>
    
    <div class="tab-content">
      <StreakCard 
        v-if="activeTab === 'active'"
        title="Active Posting Streaks" 
        :streaks="activeStreaks" 
      />
      <StreakCard 
        v-if="activeTab === 'longest'"
        title="Longest Posting Streaks" 
        :streaks="longestStreaks" 
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import StreakCard from './StreakCard.vue'

const props = defineProps<{
  activeStreaks: any[]
  longestStreaks: any[]
}>()

const activeTab = ref('active')

// Auto-switch to first tab with data
const autoSelectTab = computed(() => {
  if (props.activeStreaks && props.activeStreaks.length > 0) return 'active'
  if (props.longestStreaks && props.longestStreaks.length > 0) return 'longest'
  return 'active' // Default to first tab if no data
})

// Watch for data changes and auto-switch
watch([() => props.activeStreaks, () => props.longestStreaks], () => {
  activeTab.value = autoSelectTab.value
}, { immediate: true })
</script>

<style scoped>
.tabbed-streak-cards {
  background-color: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 1rem 1.5rem;
  display: flex;
  flex-direction: column;
  height: 100%;
}

.tab-header {
  display: flex;
  gap: 4px;
  background-color: var(--bg-tertiary);
  border-radius: 6px;
  padding: 4px;
  margin-bottom: 1rem;
}

.tab-header button {
  flex: 1;
  background-color: transparent;
  border: none;
  color: var(--text-secondary);
  padding: 6px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.85rem;
  transition: all 0.2s ease;
}

.tab-header button.active {
  background-color: var(--bg-secondary);
  color: var(--text-primary);
}

.tab-content {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.tab-content :deep(.stat-card) {
  height: 100%;
  margin: 0;
  padding: 0;
  border: none;
  border-radius: 0;
  background-color: transparent;
  display: flex;
  flex-direction: column;
}

.tab-content :deep(h3) {
  display: none;
}

.tab-content :deep(.scrollable-content) {
  flex: 1;
  overflow-y: auto;
}

.tab-content :deep(.hide-scrollbar) {
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.tab-content :deep(.hide-scrollbar::-webkit-scrollbar) {
  display: none;
}
</style>