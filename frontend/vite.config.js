import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/players': 'http://127.0.0.1:8000',
      '/teams': 'http://127.0.0.1:8000',
      '/game': 'http://127.0.0.1:8000',
      '/create-team': 'http://127.0.0.1:8000',
      '/select-team': 'http://127.0.0.1:8000',
      '/negotiations': 'http://127.0.0.1:8000',
      '/ai-buyouts': 'http://127.0.0.1:8000',
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
