import { defineConfig } from 'vite'

// macOS reserves :5000 for AirPlay Receiver; point the dev proxy elsewhere with
// PESTO_BACKEND=http://localhost:5050 npm run dev (default stays the Flask :5000).
const backend = process.env.PESTO_BACKEND || 'http://localhost:5000'
import path from 'path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [
    // The React and Tailwind plugins are both required for Make, even if
    // Tailwind is not being actively used – do not remove them
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      // Alias @ to the src directory
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    // Build output directory (relative to this file)
    outDir: '../web_build',
    // Empty the directory before building
    emptyOutDir: true,
  },
  server: {
    // Dev server configuration
    port: 5173,
    proxy: {
      // Proxy API requests to Flask backend during development
      '/socket.io': {
        target: backend,
        ws: true,
        changeOrigin: true,
      },
      '/api': {
        target: backend,
        changeOrigin: true,
      },
    },
  },
})
