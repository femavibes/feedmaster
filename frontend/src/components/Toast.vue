<template>
  <div v-if="visible" class="toast" :class="type">
    {{ message }}
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  message: String,
  type: { type: String, default: 'success' },
  duration: { type: Number, default: 3000 }
})

const visible = ref(false)

const show = () => {
  visible.value = true
  setTimeout(() => {
    visible.value = false
  }, props.duration)
}

watch(() => props.message, (newMessage) => {
  if (newMessage) {
    show()
  }
})

defineExpose({ show })
</script>

<style scoped>
.toast {
  position: fixed;
  top: 2rem;
  right: 2rem;
  padding: 1rem 1.5rem;
  border-radius: 8px;
  color: white;
  font-weight: 500;
  z-index: 10000;
  animation: slideIn 0.3s ease-out;
}

.toast.success {
  background-color: #10b981;
  border: 1px solid #059669;
}

.toast.error {
  background-color: #ef4444;
  border: 1px solid #dc2626;
}

@keyframes slideIn {
  from {
    transform: translateX(100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}
</style>