// Service worker aplikacije Najjeftinija košarica.
// Upravlja samo vlastitim opsegom (mapa aplikacije) i samo cacheovima s prefiksom "kosarica-".
const VERZIJA = '1.7.5';
const PREFIKS = 'kosarica-';
const APLIKACIJA = `${PREFIKS}aplikacija-${VERZIJA}`;
const PODACI = `${PREFIKS}podaci`;
const POSLOVNICE = `${PREFIKS}poslovnice`;
const NAJVISE_POSLOVNICA = 400;

const LJUSKA = [
  './', 'index.html', 'manifest.webmanifest', 'css/stil.css',
  'js/app.js', 'js/tekst.js', 'js/popis.js', 'js/usporedba.js', 'js/podaci.js', 'js/greske.js', 'js/karta.js', 'js/stanje.js',
  'vendor/leaflet/leaflet.js', 'vendor/leaflet/leaflet.css', 'ikone/ikona.svg', 'ikone/ikona-192.png', 'ikone/ikona-512.png',
];

self.addEventListener('install', (e) => {
  // cache: 'reload' – nova verzija uvijek uzima svježe datoteke s poslužitelja, nikad stare kopije iz HTTP spremišta
  // preglednika (GitHub Pages dopušta do 10 min); inače bi nova verzija mogla spremiti stari kod
  e.waitUntil(caches.open(APLIKACIJA).then((c) => c.addAll(LJUSKA.map((u) => new Request(u, { cache: 'reload' })))).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil((async () => {
    const imena = await caches.keys();
    // briše samo vlastite stare cacheove (prefiks "kosarica-", i one stare verzije aplikacije);
    // cacheove drugih aplikacija na istoj domeni ne dira
    const vazeci = new Set([APLIKACIJA, PODACI, POSLOVNICE]);
    await Promise.all(imena.filter((i) => i.startsWith(PREFIKS) && !vazeci.has(i)).map((i) => caches.delete(i)));
    await self.clients.claim();
  })());
});

function uOpsegu(url) {
  return url.origin === self.location.origin && url.pathname.startsWith(new URL(self.registration.scope).pathname);
}

async function mrezaPaSpremiste(zahtjev, cache) {
  const c = await caches.open(cache);
  const kljuc = zahtjev.url.split('?')[0];
  const spremljeno = await c.match(kljuc);
  try {
    const mreza = fetch(zahtjev).then(async (odgovor) => {
      if (odgovor.ok) await c.put(kljuc, odgovor.clone());
      return odgovor;
    });
    // ako postoje spremljeni podaci, spora mreža ne smije blokirati aplikaciju
    const odgovor = spremljeno
      ? await Promise.race([mreza, new Promise((_, ne) => setTimeout(() => ne(new Error('spora mreža')), 9000))])
      : await mreza;
    if (!odgovor.ok && spremljeno) throw new Error(`HTTP ${odgovor.status}`);
    return odgovor;
  } catch (e) {
    if (!spremljeno) throw e;
    const zaglavlja = new Headers(spremljeno.headers);
    zaglavlja.set('x-kosarica-izvor', 'spremiste');
    return new Response(await spremljeno.blob(), { status: 200, headers: zaglavlja });
  }
}

async function spremistePaMreza(zahtjev) {
  const c = await caches.open(POSLOVNICE);
  const spremljeno = await c.match(zahtjev.url);
  if (spremljeno) return spremljeno;
  const odgovor = await fetch(zahtjev);
  if (odgovor.ok) {
    await c.put(zahtjev.url, odgovor.clone());
    const kljucevi = await c.keys();
    if (kljucevi.length > NAJVISE_POSLOVNICA) await Promise.all(kljucevi.slice(0, kljucevi.length - NAJVISE_POSLOVNICA).map((k) => c.delete(k)));
  }
  return odgovor;
}

self.addEventListener('fetch', (e) => {
  if (e.request.method !== 'GET') return;
  const url = new URL(e.request.url);
  if (!uOpsegu(url)) return;
  if (url.pathname.includes('/data/')) {
    // datoteke poslovnica imaju ime po sadržaju: ista datoteka se nikad ne mijenja
    if (/\/data\/[a-z]{2}\/s\//.test(url.pathname)) e.respondWith(spremistePaMreza(e.request));
    else e.respondWith(mrezaPaSpremiste(e.request, PODACI));
    return;
  }
  // ljuska aplikacije: najprije spremište, u pozadini osvježi
  e.respondWith((async () => {
    const c = await caches.open(APLIKACIJA);
    const spremljeno = await c.match(e.request, { ignoreSearch: true });
    const mreza = fetch(e.request, { cache: 'no-cache' }).then((o) => { if (o.ok && url.pathname.match(/\.(js|css|html|svg|png|webmanifest)$|\/$/)) c.put(e.request, o.clone()); return o; });
    if (spremljeno) { mreza.catch(() => {}); return spremljeno; }
    try { return await mreza; } catch {
      return (await c.match('index.html')) || Response.error();
    }
  })());
});
