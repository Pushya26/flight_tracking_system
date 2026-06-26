import { defineConfig } from 'vite'
import react  from '@vitejs/plugin-react'
import cesium from 'vite-plugin-cesium'

export default defineConfig({
  plugins: [react(), cesium()],
  server: {
    proxy: {
      '/flights':   'http://localhost:8000',
      '/alerts':    'http://localhost:8000',
      '/airports':  'http://localhost:8000',
      '/simulator': 'http://localhost:8000',
      '/ws/flights': {
        target:       'ws://localhost:8000',
        ws:           true,
        changeOrigin: true,
      },
    },
  },
})
