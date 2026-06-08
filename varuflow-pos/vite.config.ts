import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      strategies: 'injectManifest',
      srcDir: 'src',
      filename: 'sw.ts',
      registerType: 'autoUpdate',
      // Use the existing public/manifest.json rather than generating one
      manifest: false,
      devOptions: {
        // Enable PWA in dev so you can test service-worker registration
        // without a production build. Set to false if it causes HMR issues.
        enabled: false,
        type: 'module',
      },
    }),
  ],
  server: {
    port: 3003,
    host: true,
  },
  build: {
    target: 'es2020',
  },
})

