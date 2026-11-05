// Bilježenje grešaka i izvješće koje vlasnik može kopirati u Claude Code.
export const VERZIJA_APLIKACIJE = '1.2.0';   // mora biti ista kao VERZIJA u sw.js (tests/test_sw.py)
const KLJUC = 'kosarica-greske';
const NAJVISE = 30;

function procitaj() {
  try { return JSON.parse(localStorage.getItem(KLJUC) || '[]'); } catch { return []; }
}

export function zabiljezi(vrsta, poruka, detalji = '') {
  const zapis = { vrijeme: new Date().toISOString(), vrsta, poruka: String(poruka).slice(0, 500), detalji: String(detalji || '').slice(0, 2000) };
  try {
    const sve = procitaj();
    sve.push(zapis);
    localStorage.setItem(KLJUC, JSON.stringify(sve.slice(-NAJVISE)));
  } catch { /* spremanje nije dostupno: greška ostaje samo u konzoli */ }
  console.warn('[košarica]', vrsta, poruka, detalji);
  return zapis;
}

export function sveGreske() { return procitaj(); }

export function obrisiGreske() {
  try { localStorage.removeItem(KLJUC); } catch { /* ništa */ }
}

export function ukljuciHvatanje() {
  window.addEventListener('error', (e) => zabiljezi('greska', e.message, `${e.filename || ''}:${e.lineno || ''}:${e.colno || ''}\n${e.error && e.error.stack ? e.error.stack : ''}`));
  window.addEventListener('unhandledrejection', (e) => {
    const r = e.reason || {};
    zabiljezi('obećanje', r.message || String(r), r.stack || '');
  });
}

export function izvjesce(stanje = {}) {
  const greske = procitaj();
  const redovi = [
    '## Izvješće o grešci – Najjeftinija košarica (aplikacija)',
    '',
    'Kopiraj cijeli ovaj tekst i zalijepi ga u Claude Code s porukom: "Popravi ovu grešku u aplikaciji".',
    '',
    `- Vrijeme: ${new Date().toISOString()}`,
    `- Verzija aplikacije: ${VERZIJA_APLIKACIJE}`,
    `- Podaci: ${stanje.podaci || 'nisu učitani'}`,
    `- Država: ${stanje.drzava || '-'}`,
    `- Zaslon: ${stanje.zaslon || '-'}; stavki na popisu: ${stanje.stavki ?? '-'}`,
    `- Lokacija uključena: ${stanje.lokacija ? 'da' : 'ne'}`,
    `- Preglednik: ${navigator.userAgent}`,
    `- Na mreži: ${navigator.onLine ? 'da' : 'ne'}; service worker: ${'serviceWorker' in navigator ? (navigator.serviceWorker.controller ? 'aktivan' : 'nije aktivan') : 'nije podržan'}`,
    '',
    `### Zadnje greške (${greske.length})`,
  ];
  if (!greske.length) redovi.push('Nema zabilježenih grešaka.');
  for (const g of greske.slice(-12).reverse()) {
    redovi.push(`- ${g.vrijeme} [${g.vrsta}] ${g.poruka}`);
    if (g.detalji) redovi.push('```', g.detalji.slice(0, 1200), '```');
  }
  return redovi.join('\n');
}
