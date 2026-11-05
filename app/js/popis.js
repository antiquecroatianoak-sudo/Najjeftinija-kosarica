// Iz izgovorenog ili upisanog teksta napravi stavke popisa: "dvije litre mlijeka, kruh i 10 jaja".
import { norm, korijen, rijecUBroj, rijecUJedinicu } from './tekst.js';

const RAZDJELNICI = /\s*(?:,|;|\.(?!\d)|\bi\b|\bte\b|\bpa\b|\bonda\b|\bplus\b|\bjos\b|\bi jos\b|\btakoder\b|\bi onda\b)\s*/;
const SUVISNO = new Set(['molim', 'trebam', 'treba', 'kupiti', 'kupi', 'kupit', 'dodaj', 'stavi', 'mi', 'nam', 'jos', 'neki', 'neko', 'neku', 'nekog', 'malo', 'od', 'kom', 'komad']);

let rjecnik = null;   // fraza -> {g, pg}

// Ijekavski/ekavski i zapis prepoznavanja govora: "mlijeko", "mljeko", "mleko" -> "mleko"; "bijeli kruh" -> "beli kruh".
export function kanon(tekst) {
  return norm(tekst).replace(/ije/g, 'e').replace(/je/g, 'e');
}

// Udaljenost uređivanja najviše 1 (zamjena, umetanje, brisanje, zamjena susjednih slova).
export function blizu(a, b) {
  if (a === b) return true;
  if (Math.abs(a.length - b.length) > 1) return false;
  if (a.length === b.length) {
    const r = [];
    for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) r.push(i);
    return r.length === 1 || (r.length === 2 && r[1] === r[0] + 1 && a[r[0]] === b[r[1]] && a[r[1]] === b[r[0]]);
  }
  const [k, d] = a.length < b.length ? [a, b] : [b, a];
  let i = 0;
  while (i < k.length && k[i] === d[i]) i++;
  return k.slice(i) === d.slice(i + 1);
}

export function pripremiGrupe(grupe) {
  rjecnik = { fraze: new Map(), kanoni: new Map(), korijeni: new Map(), grupe };
  grupe.forEach((g, gi) => {
    const dodaj = (fraza, pg) => {
      const n = norm(fraza);
      if (!n) return;
      if (!rjecnik.fraze.has(n) || pg >= 0) rjecnik.fraze.set(n, { g: gi, pg });
      const k = kanon(n);
      if (!rjecnik.kanoni.has(k) || pg >= 0) rjecnik.kanoni.set(k, { g: gi, pg });
      if (!n.includes(' ') && pg < 0 && !rjecnik.korijeni.has(korijen(n))) rjecnik.korijeni.set(korijen(n), { g: gi, pg: -1 });
    };
    dodaj(g.naziv, -1);
    for (const r of g.rijeci || []) dodaj(r, -1);
    (g.pod || []).forEach((p, pi) => {
      dodaj(p.naziv, pi);
      for (const r of p.rijeci || []) dodaj(r, pi);
    });
  });
  return rjecnik;
}

// Prepoznaj grupu/podgrupu za frazu (bez količine).
export function prepoznaj(fraza) {
  const n = norm(fraza);
  if (!n || !rjecnik) return null;
  if (rjecnik.fraze.has(n)) return rjecnik.fraze.get(n);
  const rijeci = n.split(' ').filter((r) => !SUVISNO.has(r));
  const cisto = rijeci.join(' ');
  if (rjecnik.fraze.has(cisto)) return rjecnik.fraze.get(cisto);
  // isti izraz napisan ijekavski/ekavski ili kako ga je zapisalo prepoznavanje govora ("mljeko")
  if (rjecnik.kanoni.has(kanon(cisto))) return rjecnik.kanoni.get(kanon(cisto));
  // najduža poznata fraza unutar teksta ("jeftini bijeli kruh" -> "bijeli kruh")
  let najbolje = null;
  for (let duljina = Math.min(4, rijeci.length); duljina >= 1 && !najbolje; duljina--) {
    for (let i = 0; i + duljina <= rijeci.length; i++) {
      const dio = rijeci.slice(i, i + duljina).join(' ');
      const pogodak = rjecnik.fraze.get(dio) || rjecnik.kanoni.get(kanon(dio));
      if (pogodak && (!najbolje || pogodak.pg >= 0)) najbolje = pogodak;
    }
  }
  if (najbolje) {
    // grupa je prepoznata; postoji li i podgrupa među ostalim riječima?
    if (najbolje.pg < 0) {
      const g = rjecnik.grupe[najbolje.g];
      const ostalo = new Set(rijeci.map(korijen));
      (g.pod || []).forEach((p, pi) => {
        const kljucne = norm(p.naziv).split(' ').map(korijen).filter((k) => k.length > 2 && !norm(g.naziv).includes(k));
        if (najbolje.pg < 0 && kljucne.length && kljucne.every((k) => ostalo.has(k))) najbolje = { g: najbolje.g, pg: pi };
      });
    }
    return najbolje;
  }
  if (rijeci.length === 1 || rijeci.length === 2) {
    for (const r of rijeci) {
      const k = rjecnik.korijeni.get(korijen(r));
      if (k) return k;
    }
    // jedno krivo slovo ("mlieko", "jogrut"): samo za riječi od 5+ slova i samo ako je pogodak jednoznačan
    for (const r of rijeci) {
      if (r.length < 5) continue;
      const pogodci = new Map();
      for (const [f, v] of rjecnik.kanoni) {
        if (!f.includes(' ') && f.length >= 5 && blizu(kanon(r), f)) pogodci.set(`${v.g}/${v.pg}`, v);
      }
      if (pogodci.size === 1) return [...pogodci.values()][0];
    }
  }
  return null;
}

// Rastavi jedan dio ("2 litre mlijeka") na količinu, jedinicu i frazu.
export function rastaviDio(dio) {
  const rijeci = norm(dio.replace(/(\d),(\d)/g, '$1.$2')).replace(/(\d) (\d)/g, '$1.$2').split(' ').filter(Boolean);
  // "1.5" je norm-iran u "1 5": vrati decimalni broj
  let kolicina = null;
  let jedinica = null;
  const ostalo = [];
  for (let i = 0; i < rijeci.length; i++) {
    let r = rijeci[i];
    const m = r.match(/^(\d+(?:\.\d+)?)([a-z]+)$/);       // "500g", "2l"
    if (m && rijecUJedinicu(m[2])) {
      kolicina = parseFloat(m[1]);
      [jedinica] = rijecUJedinicu(m[2]);
      kolicina *= rijecUJedinicu(m[2])[1];
      continue;
    }
    const b = rijecUBroj(r);
    if (b != null && kolicina == null) {
      kolicina = b;
      // "jedan i pol" već je razdvojeno, "dvije i pol" isto; "jedna pol" rijetko
      if (rijeci[i + 1] === 'pol' || rijeci[i + 1] === 'pola') { kolicina += 0.5; i++; }
      continue;
    }
    const j = rijecUJedinicu(r);
    if (j && (kolicina != null || ['kilu', 'kila', 'kilo', 'litru', 'litra', 'deku', 'paket', 'kutiju', 'bocu', 'glavicu'].includes(r))) {
      jedinica = j[0];
      if (kolicina == null) kolicina = 1;
      kolicina *= j[1];
      continue;
    }
    ostalo.push(r);
  }
  return { kolicina, jedinica, fraza: ostalo.join(' ') };
}

// Riječi koje nisu opće ime grupe ni podgrupe ("nutella", "dukat", "jana") sužavaju pretragu unutar grupe.
export function posebneRijeci(fraza, pogodak) {
  if (!pogodak || !rjecnik) return '';
  const g = rjecnik.grupe[pogodak.g];
  const opce = new Set();
  for (const t of [g.naziv, ...(g.pod || []).map((p) => p.naziv)]) for (const r of norm(t).split(' ')) if (r.length > 2) opce.add(korijen(r));
  // opća je i riječ koja je samo drugi zapis imena grupe ("mljeko", "mleko", "mlieko" za Mlijeko) – nije marka/filtar
  const opceKanon = new Set();
  for (const t of [g.naziv, ...(g.pod || []).map((p) => p.naziv)]) {      // samo imena (riječi grupe sadrže i marke, npr. "jana")
    for (const r of norm(t).split(' ')) if (r.length > 2) opceKanon.add(kanon(r));
  }
  const jeOpca = (r) => [...opce].some((o) => o.startsWith(korijen(r)) || korijen(r).startsWith(o))
    || [...opceKanon].some((o) => { const k = kanon(r); return k === o || (k.length >= 5 && blizu(k, o)) || korijen(k) === korijen(o); });
  return norm(fraza).split(' ').filter((r) => r.length > 2 && !SUVISNO.has(r) && !/^\d/.test(r) && !jeOpca(r)).join(' ');
}

let brojac = 0;
export function novaStavkaId() {
  brojac += 1;
  return `s${Date.now().toString(36)}${brojac}`;
}

// Glavna funkcija: tekst -> stavke {id, tekst, g, pg, upit, kolicina, jedinica, zadano}
export function rastavi(tekst) {
  const izvorno = String(tekst || '').replace(/(\d),(\d)/g, '$1.$2');
  // "jedan i pol kilogram" ne smije se razdvojiti na "i"
  const zasticeno = izvorno.replace(/\b(jedan|jedna|dva|dvije|tri|cetiri|četiri|pet)\s+i\s+pol(a)?\b/gi, '$1 pol');
  const dijelovi = zasticeno.split(RAZDJELNICI).map((d) => d.trim()).filter(Boolean);
  const stavke = [];
  for (const dio of dijelovi) {
    const { kolicina, jedinica, fraza } = rastaviDio(dio);
    if (!fraza) continue;
    const p = prepoznaj(fraza);
    const g = p ? rjecnik.grupe[p.g] : null;
    let k = kolicina;
    let j = jedinica;
    let zadano = false;
    if (g) {
      const [zk, zj] = g.zadano;
      if (k == null) { k = zk; j = zj; zadano = true; } else if (!j) {
        // "dva mlijeka" = 2 × zadana količina; "deset jaja" = 10 kom
        if (zj === 'kom' || zj === 'pak') j = zj; else { k = k * zk; j = zj; }
      }
    } else {
      if (k == null) { k = 1; zadano = true; }
      if (!j) j = 'pak';
    }
    stavke.push({
      id: novaStavkaId(), tekst: fraza, g: p ? p.g : -1, pg: p ? p.pg : -1, upit: p ? '' : fraza, filtar: posebneRijeci(fraza, p),
      kolicina: Math.round(k * 1000) / 1000, jedinica: j, zadano,
    });
  }
  return stavke;
}
