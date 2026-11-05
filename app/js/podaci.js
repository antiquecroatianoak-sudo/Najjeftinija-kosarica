// Učitavanje podataka s ponovnim pokušajima i povratkom na zadnje dobre (spremljene) podatke.
import { zabiljezi } from './greske.js';

export const DRZAVE = [
  { id: 'hr', naziv: 'Hrvatska', aktivna: true },
  { id: 'si', naziv: 'Slovenija', aktivna: false },
  { id: 'ba', naziv: 'Bosna i Hercegovina', aktivna: false },
  { id: 'rs', naziv: 'Srbija', aktivna: false },
];

const cekaj = (ms) => new Promise((r) => setTimeout(r, ms));

export async function dohvatiJSON(url, { pokusaja = 3, timeout = 25000, provjera } = {}) {
  let zadnja;
  for (let i = 0; i < pokusaja; i++) {
    const kontrola = new AbortController();
    const sat = setTimeout(() => kontrola.abort(), timeout);
    try {
      const r = await fetch(url, { cache: 'no-cache', signal: kontrola.signal });
      if (!r.ok) throw new Error(`HTTP ${r.status} za ${url}`);
      const podaci = await r.json();
      if (provjera && !provjera(podaci)) throw new Error(`Neispravan sadržaj: ${url}`);
      return { podaci, izSpremista: r.headers.get('x-kosarica-izvor') === 'spremiste' };
    } catch (e) {
      zadnja = e;
      if (i < pokusaja - 1) await cekaj(800 * 2 ** i);
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
export async function ucitajPoslovnice(drzava, datoteke, paralelno = 6) {
  const out = new Map();
  const red = [...new Set(datoteke)];
  const neuspjele = [];
  async function radnik() {
    while (red.length) {
      const ime = red.shift();
      if (predmemorija.has(ime)) { out.set(ime, predmemorija.get(ime)); continue; }
      try {
        const { podaci } = await dohvatiJSON(`data/${drzava}/s/${ime}.json`, { pokusaja: 3, timeout: 20000, provjera: (d) => d && Array.isArray(d.d) });
        predmemorija.set(ime, podaci);
        out.set(ime, podaci);
      } catch (e) {
        neuspjele.push(ime);
        zabiljezi('podaci', 'Cijene poslovnice se nisu učitale', `${ime}: ${e.message}`);
      }
    }
  }
  await Promise.all(Array.from({ length: paralelno }, radnik));
  return { datoteke: out, neuspjele };
}
