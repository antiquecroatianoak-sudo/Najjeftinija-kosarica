// Omogućuje da se aplikacija otvori i bez interneta (s posljednjim cijenama).
const CACHE = "kosarica-v2";
const OSNOVA = ["./", "index.html", "stil.css", "aplikacija.js", "manifest.webmanifest", "ikona.svg", "ikona-192.png", "ikona-512.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(OSNOVA)));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((k) => Promise.all(k.filter((x) => x !== CACHE).map((x) => caches.delete(x)))));
  self.clients.claim();
});

// Uvijek prvo pokušaj s interneta (svježe cijene), a ako nema veze, koristi spremljeno.
self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET") return;
  e.respondWith(
    fetch(e.request)
      .then((odgovor) => {
        const kopija = odgovor.clone();
        caches.open(CACHE).then((c) => c.put(e.request, kopija));
        return odgovor;
      })
      .catch(() => caches.match(e.request, { ignoreSearch: true }))
  );
});
