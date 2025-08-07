import './assets/main.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'


import App from './App.vue'
import router from './router/index.ts'
import apiService from './apiService'

const app = createApp(App)

app.use(createPinia())
app.use(router)

app.provide('apiService', apiService);

apiService.fetchFeeds()

app.mount('#app')