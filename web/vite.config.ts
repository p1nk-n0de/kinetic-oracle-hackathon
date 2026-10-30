import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Static, relocatable build: `base: './'` lets dist/ be served from any sub-path
// (file server, GitHub Pages, a USB stick). Bundles are plain files under public/runs/.
export default defineConfig({
  base: './',
  plugins: [react(), tailwindcss()],
  build: {
    target: 'es2022',
    sourcemap: false,
  },
  server: {
    port: 5173,
    strictPort: false,
  },
})
