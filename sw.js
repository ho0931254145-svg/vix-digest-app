// 每日強勢族群與 VIX 研究 — service worker
// 頁面、歷史紀錄與核對狀態（data/*.json）、附加腳本採網路優先：有網路就拿最新版，離線時改用上次快取的版本。
// 圖示與字型採快取優先。
const CACHE = 'vix-digest-v2';
const CORE = ['./', 'manifest.webmanifest', 'icon-192.png', 'icon-512.png', 'apple-touch-icon.png', 'app-extra.js'];
self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(CORE).catch(() => {})).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
function networkFirst(req, key) {
  return fetch(req).then(r => {
    if (r.ok) { const c = r.clone(); caches.open(CACHE).then(x => x.put(key, c)); }
    return r;
  }).catch(() => caches.match(key));
}
self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  const isFont = /fonts\.(googleapis|gstatic)\.com$/.test(url.hostname);
  if (req.mode === 'navigate') {
    e.respondWith(networkFirst(req, './'));
    return;
  }
  if (url.origin === location.origin && (/\/data\/[^/]+\.json$/.test(url.pathname) || /\/app-extra\.js$/.test(url.pathname))) {
    e.respondWith(networkFirst(req, url.origin + url.pathname));
    return;
  }
  if (isFont || url.origin === location.origin) {
    e.respondWith(caches.match(req).then(hit => hit || fetch(req).then(r => {
      if (r.ok || r.type === 'opaque') { const c = r.clone(); caches.open(CACHE).then(x => x.put(req, c)); }
      return r;
    })));
  }
});
