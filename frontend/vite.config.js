import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [svelte(), tailwindcss()],
  server: {
    host: true, // Listen on all addresses (needed for Docker)
    port: 5173,
    watch: {
      usePolling: true, // Enable polling for Docker volumes
    },
  },
})
