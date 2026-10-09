/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import basicSsl from '@vitejs/plugin-basic-ssl'

// Telefon + LAN IP üzerinden kamera (getUserMedia) için güvenli bağlam gerekir.
// https://192.168.x.x:3000 — sertifika uyarısında "Gelişmiş / Devam et" ile onaylayın.
export default defineConfig({
  plugins: [react(), basicSsl()],
  server: {
    port: 3000,
    strictPort: true, // 3000 doluysa başka porta geçme; çakışmayı net göster
    host: '0.0.0.0', // Tüm network interface'lerinden erişilebilir yap
    https: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
        ws: true, // WebSocket desteği
        // Rewrite: API path'ini koru
        rewrite: (path) => path,
        // Hata yönetimi - backend çalışmıyorsa sessizce handle et
        configure: (proxy, _options) => {
          proxy.on('error', (err, _req, _res) => {
            // Backend bağlantı hatalarını sessizce handle et
            // (Backend çalışmıyorsa bu normal)
            if (err.code !== 'ECONNREFUSED' && err.code !== 'ECONNRESET') {
              console.warn('Proxy error:', err.message)
            }
          })
        },
      },
    },
  },
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
  },
})









