// Omogućuje da se aplikacija otvori i bez interneta (s posljednjim cijenama).
const CACHE = "kosarica-v15";
const OSNOVA = ["./", "index.html", "stil.css", "aplikacija.js", "skupine.js", "manifest.webmanifest", "ikona.svg", "ikona-192.png", "ikona-512.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(OSNOVA)));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((k) => Promise.all(k.filter((x) => x !== CACHE).map((x) => caches.delete(x)))));
  e.waitUntil(self.clients.claim());
});

// Uvijek prvo pokušaj s interneta (svježe cijene), a ako nema veze, koristi spremljeno.
self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET") return;
  e.respondWith(
    fetch(e.request)
      .then((odgovor) => {
        if (odgovor.ok && new URL(e.request.url).origin === self.location.origin) {
          const kopija = odgovor.clone();
          e.waitUntil(caches.open(CACHE).then((c) => c.put(e.request, kopija)).catch(() => {}));
        }
        return odgovor;
      })
      .catch(async () => (await caches.match(e.request, { ignoreSearch: true }))
        || new Response("Nema internetske veze.", { status: 503, headers: { "Content-Type": "text/plain; charset=utf-8" } }))
  );
});


