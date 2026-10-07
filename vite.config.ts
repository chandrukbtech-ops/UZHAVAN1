import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['uzhavan-mark.svg'],
      workbox: {
        globIgnores: ['**/firebase-*.js'],
      },
      manifest: {
        name: 'Uzhavan Farm Assistant',
        short_name: 'Uzhavan',
        description: 'Crop health, local weather, field planning, and crop-care reminders.',
        theme_color: '#1d573d',
        background_color: '#f5f7f1',
        display: 'standalone',
        start_url: '/',
        icons: [
          { src: '/uzhavan-mark.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any maskable' },
        ],
      },
    }),
  ],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
