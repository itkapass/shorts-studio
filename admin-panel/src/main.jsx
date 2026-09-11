import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

// Registers the push-notification service worker (public/sw.js). Safe to
// call on every load — the browser no-ops if it's already registered and
// unchanged. Wrapped in a capability check so this never breaks anything
// on a browser that doesn't support service workers at all.
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch((err) => {
      console.warn('Service worker registration failed (push notifications will not work):', err)
    })
  })
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
