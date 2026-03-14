import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'Stock Toolkit',
        short_name: 'StockTK',
        description: '주식 투자 분석 대시보드',
        theme_color: '#030712',
        background_color: '#030712',
        display: 'standalone',
        start_url: '/stock_toolkit/',
        scope: '/stock_toolkit/',
        icons: [
          { src: 'icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icon-512.png', sizes: '512x512', type: 'image/png' },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,json,png}'],
      },
    }),
  ],
  base: '/stock_toolkit/',
})
