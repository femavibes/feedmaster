import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [
    vue(),
  ],
  // Build for root path deployment
  base: '/',
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  // This `proxy` configuration is ONLY for the development server (`npm run dev`).
  // It tells the dev server to forward any requests to `/api` to your backend at `http://localhost:8000`.
  // This setting has NO effect on your production build (`npm run build`).
  // Your production build will make API calls to relative paths.
  server: {
    proxy: {
      '/api': 'http://localhost:8000'
    }
  }
})
