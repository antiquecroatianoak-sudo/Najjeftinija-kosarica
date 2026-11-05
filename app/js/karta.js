// Karta poslovnica (Leaflet + OpenStreetMap). Učitava se tek kad se otvori zaslon karte.
let ucitavanje = null;

function ucitajLeaflet() {
  if (window.L) return Promise.resolve(window.L);
  if (ucitavanje) return ucitavanje;
  ucitavanje = new Promise((ok, greska) => {
    const css = document.createElement('link');
    css.rel = 'stylesheet';
    css.href = 'vendor/leaflet/leaflet.css';
    document.head.appendChild(css);
    const s = document.createElement('script');
    s.src = 'vendor/leaflet/leaflet.js';
    s.onload = () => ok(window.L);
    s.onerror = () => { ucitavanje = null; greska(new Error('Leaflet se nije učitao')); };
    document.head.appendChild(s);
  });
  return ucitavanje;
}

const esc = (t) => String(t ?? '').replace(/[&<>"']/g, (z) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[z]));

export async function nacrtajKartu(element, { poslovnice, lokacija, boja, naziv, odaberi }) {
  const L = await ucitajLeaflet();
  if (!element || !element.isConnected) return null;
  const sredina = lokacija.lat != null ? [lokacija.lat, lokacija.lon] : [44.9, 16.2];
  const karta = L.map(element, { zoomControl: true, attributionControl: true, preferCanvas: true })
    .setView(sredina, lokacija.lat != null ? (lokacija.radijus <= 2 ? 14 : lokacija.radijus <= 5 ? 13 : lokacija.radijus <= 10 ? 12 : 11) : 7);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  }).addTo(karta);
  const sloj = L.layerGroup().addTo(karta);
  for (const p of poslovnice) {
    L.circleMarker([p[5], p[6]], { radius: 7, color: '#fff', weight: 2, fillColor: boja(p[0]), fillOpacity: 0.95, bubblingMouseEvents: false })
      .bindPopup(`<b>${esc(naziv(p[0]))}</b><br>${esc(p[2])}<br>${esc([p[4], p[3]].filter(Boolean).join(' '))}`)
      .addTo(sloj);
  }
  if (lokacija.lat != null) {
    if (lokacija.ukljucena) {
      L.circle([lokacija.lat, lokacija.lon], { radius: lokacija.radijus * 1000, color: '#0b5d56', weight: 2, fillColor: '#0f7a70', fillOpacity: 0.08 }).addTo(karta);
    }
    L.circleMarker([lokacija.lat, lokacija.lon], { radius: 9, color: '#fff', weight: 3, fillColor: '#f2a516', fillOpacity: 1 })
      .bindTooltip(lokacija.izvor === 'karta' ? 'Odabrana točka' : 'Ti si ovdje').addTo(karta);
  }
  karta.on('click', (e) => {
    if (confirm('Postaviti ovu točku kao središte kruga za usporedbu?')) odaberi(e.latlng.lat, e.latlng.lng);
  });
  // odgođeno preračunavanje veličine samo dok je karta još na zaslonu (inače Leaflet baca "_leaflet_pos")
  const sat = setTimeout(() => { if (element.isConnected && karta._loaded && !karta._uklonjena) karta.invalidateSize(); }, 50);
  karta.on('unload', () => { karta._uklonjena = true; clearTimeout(sat); });
  return karta;
}

// Sigurno uklanjanje karte: zaustavi animacije prije uklanjanja.
export function ukloniKartu(karta) {
  if (!karta) return;
  try { karta._uklonjena = true; karta.stop(); karta.off(); karta.remove(); } catch { /* karta je već uklonjena */ }
}
