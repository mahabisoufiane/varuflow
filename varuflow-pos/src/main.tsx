import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { registerSW } from 'virtual:pwa-register'
import './index.css'
import App from './App'
import { Toaster } from 'sonner'

// Register PWA service worker — handles offline-first caching and background
// sync for queued POS sales. registerSW is a no-op in dev (devOptions.enabled=false).
registerSW({ immediate: true })

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
    <Toaster position="top-center" richColors />
  </StrictMode>,
)
