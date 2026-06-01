import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const API_PROXY_TARGET = process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:8010'
// Semantic Intelligence OS (the new 14-step pipeline) runs as a separate service.
const SIO_PROXY_TARGET = process.env.VITE_SIO_PROXY_TARGET || 'http://127.0.0.1:8020'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5180,
    proxy: {
      '/api': {
        target: API_PROXY_TARGET,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      '/sio': {
        target: SIO_PROXY_TARGET,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/sio/, ''),
      },
    },
  },
})
