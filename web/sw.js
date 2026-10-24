/* Shell-only cache: never cache daily JSON or private research. */
const CACHE = "daily-news-shell-v7";
const SHELL = ["./", "./index.html", "./manifest.webmanifest", "./app-icon.png", "./push.js", "./push-config.js"];
self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(SHELL)));
  self.skipWaiting();
});
self.addEventListener("activate", event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(
    keys.filter(key => key !== CACHE).map(key => caches.delete(key))
  )));
  self.clients.claim();
});
self.addEventListener("fetch", event => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin || url.pathname.endsWith("/briefing.json")) return;
  if (event.request.mode === "navigate") {
    event.respondWith(fetch(event.request).catch(() => caches.match("./index.html")));
  }
});
self.addEventListener("push", event => {
  let payload = {};
  try { payload = event.data?.json() || {}; } catch { /* Default copy below. */ }
  const title = typeof payload.title === "string" && payload.title.trim() ? payload.title : "The Morning Edition";
  const body = typeof payload.body === "string" && payload.body.trim() ? payload.body : "Fresh off the press. Your daily briefing is here.";
  event.waitUntil(self.registration.showNotification(title, {body,icon:"./app-icon.png",data:{url:"./"},tag:"daily-news-edition"}));
});
self.addEventListener("notificationclick", event => {
  event.notification.close();
  event.waitUntil(self.clients.openWindow("./"));
});
