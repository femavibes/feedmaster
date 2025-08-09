<template>
  <div v-if="isVisible" class="modal-overlay" @click="closeModal">
    <div class="modal-content" @click.stop>
      <div class="modal-header">
        <h2>Settings</h2>
        <button class="close-button" @click="closeModal">×</button>
      </div>
      <div class="modal-body">
        <div class="setting-group">
          <label class="setting-label">
            <input type="checkbox" v-model="lightMode" @change="toggleTheme" />
            <span class="checkmark"></span>
            Enable Light Mode
          </label>
        </div>
        
        <div class="setting-group">
          <label class="setting-label">
            <input type="checkbox" v-model="showTimestamps" @change="saveSettings" />
            <span class="checkmark"></span>
            Show relative timestamps ("2 hours ago")
          </label>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

defineProps({
  isVisible: Boolean
})

const emit = defineEmits(['close'])

const lightMode = ref(false)
const showTimestamps = ref(true)

const closeModal = () => {
  emit('close')
}

const loadSettings = () => {
  const settings = JSON.parse(localStorage.getItem('feedmaster-settings') || '{}')
  lightMode.value = settings.lightMode || false
  showTimestamps.value = settings.showTimestamps !== false
  
  // Apply theme on load
  applyTheme()
}

const saveSettings = () => {
  const settings = {
    lightMode: lightMode.value,
    showTimestamps: showTimestamps.value
  }
  localStorage.setItem('feedmaster-settings', JSON.stringify(settings))
  // Dispatch custom event for immediate updates
  window.dispatchEvent(new CustomEvent('settings-changed', { detail: settings }))
}

const applyTheme = () => {
  if (lightMode.value) {
    document.documentElement.classList.add('light-mode')
  } else {
    document.documentElement.classList.remove('light-mode')
  }
}

const toggleTheme = () => {
  saveSettings()
  applyTheme()
}

onMounted(() => {
  loadSettings()
})
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.7);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.modal-content {
  background-color: #2b2d31;
  border: 1px solid #404249;
  border-radius: 8px;
  width: 90%;
  max-width: 500px;
  max-height: 80vh;
  overflow-y: auto;
  color: #dcddde;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid #404249;
}

.modal-header h2 {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 600;
}

.close-button {
  background: none;
  border: none;
  color: #dcddde;
  font-size: 1.5rem;
  cursor: pointer;
  padding: 0;
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: background-color 0.2s ease;
}

.close-button:hover {
  background-color: #404249;
}

.modal-body {
  padding: 1.5rem;
}

.setting-group {
  margin-bottom: 1.5rem;
}

.setting-label {
  display: flex;
  align-items: center;
  cursor: pointer;
  font-size: 1rem;
  gap: 0.75rem;
}

.setting-label input[type="checkbox"] {
  display: none;
}

.checkmark {
  width: 20px;
  height: 20px;
  background-color: #404249;
  border: 2px solid #5a5d66;
  border-radius: 4px;
  position: relative;
  transition: all 0.2s ease;
}

.setting-label input[type="checkbox"]:checked + .checkmark {
  background-color: #5865f2;
  border-color: #5865f2;
}

.setting-label input[type="checkbox"]:checked + .checkmark::after {
  content: '✓';
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: white;
  font-size: 14px;
  font-weight: bold;
}

.setting-label:hover .checkmark {
  border-color: #6a6d76;
}

.notice {
  background-color: #404249;
  border: 1px solid #5a5d66;
  border-radius: 6px;
  padding: 1rem;
  margin-bottom: 1.5rem;
  text-align: center;
}

.notice p {
  margin: 0;
  color: #f0b90b;
  font-weight: 500;
}
</style>