/* Shell-only cache: never cache daily JSON or private research. */
const CACHE = "daily-news-shell-v5";
const SHELL = ["./", "./index.html", "./manifest.webmanifest", "./icon.svg", "./push.js", "./push-config.js"];
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
  event.waitUntil(self.registration.showNotification("Your morning, in focus.",{body:"A fresh look at what matters today.",icon:"./icon.svg",data:{url:"./"},tag:"daily-news-edition"}));
});
self.addEventListener("notificationclick", event => {
  event.notification.close();
  event.waitUntil(self.clients.openWindow("./"));
});
