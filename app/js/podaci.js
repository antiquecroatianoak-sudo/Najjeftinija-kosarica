// Učitavanje podataka s ponovnim pokušajima i povratkom na zadnje dobre (spremljene) podatke.
import { zabiljezi } from './greske.js';

export const DRZAVE = [
  { id: 'hr', naziv: 'Hrvatska', aktivna: true },
  { id: 'si', naziv: 'Slovenija', aktivna: false },
  { id: 'ba', naziv: 'Bosna i Hercegovina', aktivna: false },
  { id: 'rs', naziv: 'Srbija', aktivna: false },
];

const cekaj = (ms) => new Promise((r) => setTimeout(r, ms));

// rok: apsolutno vrijeme (Date.now()) nakon kojeg se više ne pokušava – nijedan poziv ne traje dulje od roka.
export async function dohvatiJSON(url, { pokusaja = 3, timeout = 25000, provjera, rok = Infinity } = {}) {
  let zadnja = new Error(`Isteklo vrijeme za ${url}`);
  for (let i = 0; i < pokusaja; i++) {
    const preostalo = rok - Date.now();
    if (preostalo <= 0) break;
    const kontrola = new AbortController();
    const sat = setTimeout(() => kontrola.abort(), Math.min(timeout, preostalo));
    try {
      const r = await fetch(url, { cache: 'no-cache', signal: kontrola.signal });
      if (!r.ok) throw new Error(`HTTP ${r.status} za ${url}`);
      const podaci = await r.json();
      if (provjera && !provjera(podaci)) throw new Error(`Neispravan sadržaj: ${url}`);
      return { podaci, izSpremista: r.headers.get('x-kosarica-izvor') === 'spremiste' };
    } catch (e) {
      zadnja = e;
      if (i < pokusaja - 1) await cekaj(Math.min(800 * 2 ** i, Math.max(0, rok - Date.now())));
    } finally {
      clearTimeout(sat);
    }
  }
  throw zadnja;
}

const ispravno = {
  meta: (d) => d && Array.isArray(d.lanci) && typeof d.datum === 'string',
  proizvodi: (d) => d && Array.isArray(d.p) && d.l && typeof d.l === 'object',
  poslovnice: (d) => d && Array.isArray(d.p),
  grupe: (d) => d && Array.isArray(d.grupe) && d.grupe.length > 0,
};

export async function ucitajPodatke(drzava = 'hr') {
  const baza = `data/${drzava}/`;
  const meta = await dohvatiJSON(baza + 'meta.json', { provjera: ispravno.meta });
  const [proizvodi, poslovnice, grupe] = await Promise.all([
    dohvatiJSON(baza + 'proizvodi.json', { provjera: ispravno.proizvodi, timeout: 60000 }),
    dohvatiJSON(baza + 'poslovnice.json', { provjera: ispravno.poslovnice }).catch((e) => {
      zabiljezi('podaci', 'Poslovnice se nisu učitale; karta i lokacija nisu dostupne', e.message);
      return { podaci: { p: [] }, izSpremista: false };
    }),
    dohvatiJSON(baza + 'grupe.json', { provjera: ispravno.grupe }),
  ]);
  if (proizvodi.podaci.verzija && meta.podaci.verzija && proizvodi.podaci.verzija !== meta.podaci.verzija) {
    zabiljezi('podaci', 'Verzije meta.json i proizvodi.json se razlikuju (objava je možda u tijeku)', `${meta.podaci.verzija} / ${proizvodi.podaci.verzija}`);
  }
  return {
    meta: meta.podaci, proizvodi: proizvodi.podaci, poslovnice: poslovnice.podaci.p, grupe: grupe.podaci.grupe,
    izSpremista: meta.izSpremista || proizvodi.izSpremista,
  };
}

// Datoteke cijena pojedinih poslovnica (učitavaju se samo za poslovnice u odabranom krugu).
const predmemorija = new Map();
// Ukupno vrijeme za cijene poslovnica u krugu: zaslon nikad ne čeka dulje (slaba mobilna veza). Poslovnice koje se
// ne učitaju na vrijeme izostavljaju se iz usporedbe i navode se, uz "Pokušaj ponovno".
export const ROK_POSLOVNICA_MS = 15000;

export async function ucitajPoslovnice(drzava, datoteke, { paralelno = 6, rok = ROK_POSLOVNICA_MS, napredak } = {}) {
  const out = new Map();
  const red = [...new Set(datoteke)];
  const ukupno = red.length;
  const neuspjele = [];
  const kraj = Date.now() + rok;
  let gotovo = 0;
  const javi = () => { if (napredak) { try { napredak(gotovo, ukupno); } catch { /* prikaz napretka ne smije srušiti učitavanje */ } } };
  async function radnik() {
    while (red.length) {
      const ime = red.shift();
      if (predmemorija.has(ime)) { out.set(ime, predmemorija.get(ime)); gotovo++; javi(); continue; }
      const preostalo = kraj - Date.now();
      if (preostalo < 500) { neuspjele.push(ime); continue; }
      try {
        const { podaci } = await dohvatiJSON(`data/${drzava}/s/${ime}.json`,
          { pokusaja: 2, timeout: 8000, rok: kraj, provjera: (d) => d && Array.isArray(d.d) });
        predmemorija.set(ime, podaci);
        out.set(ime, podaci);
      } catch (e) {
        neuspjele.push(ime);
        zabiljezi('podaci', 'Cijene poslovnice se nisu učitale', `${ime}: ${e.message}`);
      }
      gotovo++; javi();
    }
  }
  await Promise.all(Array.from({ length: paralelno }, radnik));
  return { datoteke: out, neuspjele };
}

// Unaprijed učitaj cijene poslovnica (npr. odmah nakon odabira kruga) da rezultati budu odmah spremni.
export function pripremiPoslovnice(drzava, datoteke) {
  ucitajPoslovnice(drzava, datoteke).catch(() => {});
}
