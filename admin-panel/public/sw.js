// public/sw.js
//
// Service worker for real push notifications — the thing that makes a
// video-failed or video-ready alert show up on your phone's lock screen
// the same way any other app's notification does, without you having to
// have the app open, or even have your phone unlocked.
//
// WHY THIS FILE HAS TO BE HERE, SPECIFICALLY
// Browsers only allow a service worker to register from the root of the
// site (or a path it explicitly scopes to) — a service worker that only
// lives inside a JS bundle can't receive push events at all, because those
// events need to reach your device even while the app itself isn't open.
// Vite serves anything in /public untouched at the site root, which is
// exactly what this needs.

self.addEventListener('install', () => {
  // Activate immediately rather than waiting for every open tab to close
  // first — for a dashboard you check occasionally, waiting could mean
  // the new service worker never takes over at all.
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim())
})

// The actual push event — fired when the backend sends a notification via
// engine/push_notifications.py. The payload is plain JSON (see that file
// for the exact shape): { title, body, url }.
self.addEventListener('push', (event) => {
  let data = { title: 'Shorts Studio', body: 'Something happened.', url: '/queue' }
  try {
    if (event.data) data = { ...data, ...event.data.json() }
  } catch (e) {
    // A malformed payload should still show SOMETHING rather than silently
    // drop the notification — better information than none.
  }

  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: '/favicon.svg',
      badge: '/favicon.svg',
      data: { url: data.url || '/queue' },
      // Distinct failures/successes shouldn't collapse into one notification
      // and silently overwrite each other — each gets its own tag based on
      // content so genuinely different events stay visible, but the SAME
      // event retried (e.g. a flaky delivery retry) doesn't spam a second
      // banner for the identical thing.
      tag: data.tag || undefined,
    })
  )
})

// Tapping the notification should open the app (or focus it if already
// open) and land on the relevant page, not just dismiss silently.
self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const targetUrl = event.notification.data?.url || '/queue'

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if (client.url.includes(self.registration.scope) && 'focus' in client) {
          client.navigate(targetUrl)
          return client.focus()
        }
      }
      return self.clients.openWindow(targetUrl)
    })
  )
})
