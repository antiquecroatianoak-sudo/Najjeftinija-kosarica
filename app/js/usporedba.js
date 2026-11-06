// Usporedba cijena: rezultat A (najjeftinije po stavci), B (jedna trgovina), C (dvije trgovine).
//
// "Prodavač" je ili lanac (uobičajena cijena lanca – procjena) ili stvarna poslovnica (njezine cijene).
// Svaki prodavač ima Int32Array cijena u centima po indeksu proizvoda (0 = nema).
//
// Pravila:
//  - Uspoređuje se trošak za traženu količinu: broj pakiranja = ceil(tražena / količina pakiranja).
//    Količina pakiranja i broj pakiranja prikazuju se odvojeno; jedinična cijena (€/kg, €/l, €/kom) samo kad je
//    količina pakiranja poznata.
//  - Proizvod bez poznate količine ne može se uspoređivati po kg/l; tada se uspoređuje po pakiranju i to se jasno
//    označava ("po pakiranju").
//  - Korisnik može odbiti proizvod ("zamijeni"); odbijeni se preskaču u A, B i C.

import { norm, korijen, uOsnovnu } from './tekst.js';

export const NAJVISE_PAKIRANJA = 40;
export const NAJVISE_VISKA = 2.5;

// Procjena po lancu (bez odabrane lokacije): kod velikog lanca (20+ poslovnica) proizvod koji prodaje samo jedna
// poslovnica nije cijena lanca (npr. vino za 0,20 € u 1 od 188 Konzuma). U krugu oko lokacije svaka stvarna
// poslovnica i dalje ima svoje cijene. Za male lance vrijedi svaki proizvod.
export function pragPoslovnica(ukupnoPoslovnica) {
  return ukupnoPoslovnica >= 20 ? 2 : 1;
}

export class Baza {
  constructor(proizvodi, grupe) {
    this.p = proizvodi.p;               // [naziv, marka, količina, vrsta, grupa, podgrupa, barkod, (ostali barkodovi)]
    this.grupe = grupe;
    this.n = this.p.length;
    this.trazilica = this.p.map((r) => ' ' + norm(`${r[0]} ${r[1]}`) + ' ');
    this.poGrupi = new Map();
    this.poBarkodu = new Map();
    this.p.forEach((r, i) => {
      if (r[4] >= 0) {
        if (!this.poGrupi.has(r[4])) this.poGrupi.set(r[4], []);
        this.poGrupi.get(r[4]).push(i);
      }
      if (r[6]) this.poBarkodu.set(r[6], i);
      // isti proizvod pod više barkodova (spojen u uvozu): skener nalazi svaki
      if (r[7]) for (const b of String(r[7]).split(',')) if (b && !this.poBarkodu.has(b)) this.poBarkodu.set(b, i);
    });
    this.lanci = {};
    for (const [id, d] of Object.entries(proizvodi.l)) {
      const cijena = new Int32Array(this.n);
      const lokalno = new Int32Array(this.n);
      let i = 0;
      d.i.forEach((delta, k) => {
        i += delta;
        cijena[i] = d.t[k];
        lokalno[i] = k + 1;
      });
      let ukupno = 1;
      for (const s of d.s || []) if (s > ukupno) ukupno = s;
      const prag = pragPoslovnica(ukupno);
      const procjena = new Int32Array(cijena);
      if (d.s) {
        let j = 0;
        d.i.forEach((delta, k) => { j += delta; if (d.s[k] < prag) procjena[j] = 0; });
      }
      this.lanci[id] = { id, cijena, procjena, lokalno, t: d.t, n: d.n, x: d.x, r: d.r, s: d.s, b: d.b || null, a: d.a || null, indeksi: null };
    }
  }

  // Neobično niska cijena: jedinična cijena ispod 1/8 medijana iste vrste proizvoda (grupa, podgrupa, kg/l).
  // Takva cijena je gotovo uvijek greška u cjeniku (krivo upisana količina ili cijena), pa se NIGDJE ne
  // koristi: ni u rezultatima A/B/C, ni u akcijama, favoritima ni detaljima proizvoda (odluka vlasnika 6.11.2026.).
  sumnjivoNiska(i, cijenaCenti) {
    if (!this.donjaGranica) this.donjaGranica = this.izracunajGranice();
    return cijenaCenti < this.donjaGranica[i];
  }

  // Cijena koja smije ući u usporedbu: postoji i nije neobično niska.
  prihvatljiva(i, cijenaCenti) {
    return cijenaCenti > 0 && !this.sumnjivoNiska(i, cijenaCenti);
  }

  // Najniža prihvatljiva cijena pakiranja po proizvodu (0 = bez granice).
  izracunajGranice() {
    const mediani = this.izracunajMedijane();
    const out = new Float64Array(this.n);
    for (let i = 0; i < this.n; i++) {
      const [, , kol, vrsta, g, pg] = this.p[i];
      if (!(kol > 0) || (vrsta !== 'kg' && vrsta !== 'l') || g < 0) continue;
      const m = mediani.get(`${g}|${pg}|${vrsta}`);
      if (m != null) out[i] = (m / 8) * kol;
    }
    return out;
  }

  izracunajMedijane() {
    const po = new Map();
    for (const L of Object.values(this.lanci)) {
      const idx = this.indeksiLanca(L.id);
      for (let k = 0; k < L.t.length; k++) {
        const i = idx[k];
        const [, , kol, vrsta, g, pg] = this.p[i];
        if (!(kol > 0) || (vrsta !== 'kg' && vrsta !== 'l') || g < 0) continue;
        const kljuc = `${g}|${pg}|${vrsta}`;
        if (!po.has(kljuc)) po.set(kljuc, []);
        po.get(kljuc).push(L.t[k] / kol);
      }
    }
    const out = new Map();
    for (const [k, v] of po) {
      if (v.length < 20) continue;
      v.sort((a, b) => a - b);
      out.set(k, v[Math.floor(v.length / 2)]);
    }
    return out;
  }

  // Indeksi proizvoda lanca redom (za datoteke poslovnica).
  indeksiLanca(id) {
    const L = this.lanci[id];
    if (!L.indeksi) {
      L.indeksi = new Int32Array(L.t.length);
      for (let i = 0; i < this.n; i++) if (L.lokalno[i]) L.indeksi[L.lokalno[i] - 1] = i;
    }
    return L.indeksi;
  }

  // Cijene stvarne poslovnice iz njezine datoteke (razlike od uobičajene cijene lanca).
  cijenePoslovnice(lanac, datoteka) {
    const L = this.lanci[lanac];
    const idx = this.indeksiLanca(lanac);
    const cijena = new Int32Array(L.cijena);
    let poz = 0;
    if (datoteka.o) {
      for (const d of datoteka.o) { poz += d; cijena[idx[poz]] = 0; }
    } else if (datoteka.u) {
      const ima = new Uint8Array(idx.length);
      for (const d of datoteka.u) { poz += d; ima[poz] = 1; }
      for (let k = 0; k < idx.length; k++) if (!ima[k]) cijena[idx[k]] = 0;
    }
    poz = 0;
    datoteka.d.forEach((d, k) => { poz += d; cijena[idx[poz]] = datoteka.c[k]; });
    return cijena;
  }

  raspon(lanac, i) {
    const L = this.lanci[lanac];
    const k = L && L.lokalno[i];
    if (!k) return null;
    const t = L.t[k - 1];
    return { min: t - L.n[k - 1], max: t + L.x[k - 1], redovna: L.r[k - 1], poslovnica: L.s[k - 1],
      najniza30: L.b ? L.b[k - 1] : 0, sidrena: L.a ? L.a[k - 1] : 0 };
  }

  trazi(upit, najvise = Infinity) {
    const rijeci = norm(upit).split(' ').filter((r) => r.length > 1);
    if (!rijeci.length) return [];
    const uzorci = rijeci.map((r) => ' ' + (r.length > 4 ? korijen(r) : r));
    const out = [];
    for (let i = 0; i < this.n && out.length < najvise; i++) {
      const t = this.trazilica[i];
      if (uzorci.every((u) => t.includes(u))) out.push(i);
    }
    return out;
  }

  // "nutella", "Dukat mlijeko": samo proizvodi grupe koji u nazivu/marki imaju te riječi
  suzi(indeksi, filtar) {
    if (!filtar) return [];
    const uzorci = norm(filtar).split(' ').filter(Boolean).map((r) => ' ' + (r.length > 4 ? korijen(r) : r));
    return indeksi.filter((i) => uzorci.every((u) => this.trazilica[i].includes(u)));
  }

  filtarPronaden(stavka) {
    if (!stavka.filtar || stavka.g < 0) return false;
    const svi = this.poGrupi.get(stavka.g) || [];
    return this.suzi(stavka.pg >= 0 ? svi.filter((i) => this.p[i][5] === stavka.pg) : svi, stavka.filtar).length > 0;
  }

  kandidati(stavka) {
    if (stavka.proizvod != null && stavka.samoTaj) return [stavka.proizvod];
    if (stavka.g >= 0) {
      const svi = this.poGrupi.get(stavka.g) || [];
      const grupa = stavka.pg >= 0 ? svi.filter((i) => this.p[i][5] === stavka.pg) : svi;
      const suzeno = this.suzi(grupa, stavka.filtar);
      return suzeno.length ? suzeno : grupa;
    }
    if (stavka.proizvod != null) return [stavka.proizvod];
    return this.trazi(stavka.upit || stavka.tekst);
  }
}

// Za stavku: popis {i, pakiranja, poPakiranju} – kako bi se pokrila tražena količina.
export function nacinKupnje(baza, stavka) {
  const [trazeno, vrsta] = uOsnovnu(stavka.kolicina, stavka.jedinica);
  const odbijeni = new Set(stavka.odbijeni || []);
  const kandidati = baza.kandidati(stavka).filter((i) => !odbijeni.has(i));
  const out = [];
  if (vrsta === 'pak') {
    const n = Math.max(1, Math.round(trazeno));
    for (const i of kandidati) out.push({ i, pakiranja: n, poPakiranju: true });
    return { opcije: out, poPakiranju: true };
  }
  const preveliki = [];
  for (const i of kandidati) {
    const [, , kol, v] = baza.p[i];
    if (v !== vrsta || !(kol > 0)) continue;
    const n = Math.ceil(trazeno / kol - 1e-9);
    if (n < 1 || n > NAJVISE_PAKIRANJA) continue;
    // ne nudi 6 l kad je traženo 1 l: ukupno najviše 2,5× tražene količine (osim ako drugog nema)
    (kol * n > trazeno * NAJVISE_VISKA ? preveliki : out).push({ i, pakiranja: n, poPakiranju: false });
  }
  if (out.length) return { opcije: out, poPakiranju: false };
  if (preveliki.length) return { opcije: preveliki, poPakiranju: false };
  // ništa s poznatom količinom iste vrste: uspoređuje se jedno pakiranje (jasno označeno)
  for (const i of kandidati) out.push({ i, pakiranja: 1, poPakiranju: true });
  return { opcije: out, poPakiranju: true };
}

function bolje(a, b, baza) {
  if (a.trosak !== b.trosak) return a.trosak - b.trosak;
  const ka = baza.p[a.i][2] * a.pakiranja;
  const kb = baza.p[b.i][2] * b.pakiranja;
  if (ka && kb && ka !== kb) return kb - ka;      // za isti novac više robe
  return a.i - b.i;
}

// Najbolja ponuda za stavku kod jednog prodavača.
function najboljaKod(baza, nacin, cijena) {
  let naj = null;
  for (const o of nacin.opcije) {
    const c = cijena[o.i];
    if (!baza.prihvatljiva(o.i, c)) continue;
    const ponuda = { i: o.i, pakiranja: o.pakiranja, cijena: c, trosak: c * o.pakiranja, poPakiranju: o.poPakiranju };
    if (!naj || bolje(ponuda, naj, baza) < 0) naj = ponuda;
  }
  return naj;
}

// Rezultat A: za svaku stavku najjeftinija ponuda u cijeloj bazi (među odabranim prodavačima)
// i rang-lista ostalih proizvoda iz iste grupe.
export function rezultatA(baza, stavke, prodavaci) {
  return stavke.map((stavka) => {
    const nacin = nacinKupnje(baza, stavka);
    const poProizvodu = new Map();
    for (const o of nacin.opcije) {
      let naj = null;
      const isti = [];
      for (const pr of prodavaci) {
        const c = pr.cijena[o.i];
        if (!baza.prihvatljiva(o.i, c)) continue;
        if (!naj || c < naj.cijena) { naj = { cijena: c, prodavac: pr }; isti.length = 0; isti.push(pr); } else if (c === naj.cijena) isti.push(pr);
      }
      if (naj) {
        poProizvodu.set(o.i, { i: o.i, pakiranja: o.pakiranja, cijena: naj.cijena, trosak: naj.cijena * o.pakiranja,
          prodavac: naj.prodavac, istaCijena: isti, poPakiranju: o.poPakiranju });
      }
    }
    const rang = [...poProizvodu.values()].sort((a, b) => bolje(a, b, baza));
    return { stavka, najbolja: rang[0] || null, rang, poPakiranju: nacin.poPakiranju };
  });
}

// Rezultat B: ukupno za cijeli popis kod svakog prodavača.
export function rezultatB(baza, stavke, prodavaci) {
  const nacini = stavke.map((s) => nacinKupnje(baza, s));
  const out = prodavaci.map((pr) => {
    const stavkeKod = nacini.map((n) => najboljaKod(baza, n, pr.cijena));
    const ukupno = stavkeKod.reduce((s, p) => s + (p ? p.trosak : 0), 0);
    const nedostaje = stavkeKod.filter((p) => !p).length;
    return { prodavac: pr, stavke: stavkeKod, ukupno, nedostaje };
  });
  out.sort((a, b) => a.nedostaje - b.nedostaje || a.ukupno - b.ukupno);
  return out;
}

// Rezultat C: najbolji par prodavača (svaka stavka kod jeftinijeg od dvaju).
export function rezultatC(rezB, najvisePrikaza = 5) {
  const kandidati = rezB.slice(0, 120);      // dovoljno za točan optimum u praksi; najjeftiniji su na vrhu
  const parovi = [];
  for (let a = 0; a < kandidati.length; a++) {
    for (let b = a + 1; b < kandidati.length; b++) {
      const A = kandidati[a];
      const B = kandidati[b];
      let ukupno = 0;
      let nedostaje = 0;
      let uA = 0;
      let uB = 0;
      const podjela = A.stavke.map((pa, k) => {
        const pb = B.stavke[k];
        if (!pa && !pb) { nedostaje++; return null; }
        if (pa && (!pb || pa.trosak <= pb.trosak)) { ukupno += pa.trosak; uA++; return { kod: 0, ponuda: pa }; }
        ukupno += pb.trosak; uB++; return { kod: 1, ponuda: pb };
      });
      if (!uA || !uB) continue;      // par ima smisla samo ako se u obje trgovine nešto kupuje
      parovi.push({ prodavaci: [A.prodavac, B.prodavac], ukupno, nedostaje, podjela });
    }
  }
  parovi.sort((x, y) => x.nedostaje - y.nedostaje || x.ukupno - y.ukupno);
  return parovi.slice(0, najvisePrikaza);
}

// Ušteda: prosjek prodavača koji imaju sve stavke minus odabrani iznos (nikad negativno).
export function procjenaUstede(rezB, odabraniIznos) {
  const potpuni = rezB.filter((r) => r.nedostaje === 0);
  if (potpuni.length < 2) return { prosjek: 0, usteda: 0, najskuplje: 0 };
  const prosjek = potpuni.reduce((s, r) => s + r.ukupno, 0) / potpuni.length;
  const najskuplje = Math.max(...potpuni.map((r) => r.ukupno));
  return { prosjek: Math.round(prosjek), usteda: Math.max(0, Math.round(prosjek - odabraniIznos)), najskuplje };
}

// Udaljenost u km (haversine).
export function udaljenost(lat1, lon1, lat2, lon2) {
  const R = 6371;
  const rad = Math.PI / 180;
  const dLat = (lat2 - lat1) * rad;
  const dLon = (lon2 - lon1) * rad;
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

// Akcije: proizvodi kojima je uobičajena cijena lanca niža od redovne.
export function akcije(baza, lanci, { grupa = -1, upit = '', najvise = 300 } = {}) {
  const dozvoljeni = upit ? new Set(baza.trazi(upit)) : null;
  const out = [];
  for (const id of lanci) {
    const L = baza.lanci[id];
    if (!L) continue;
    for (let i = 0; i < baza.n; i++) {
      const k = L.lokalno[i];
      if (!k) continue;
      const redovna = L.r[k - 1];
      const t = L.t[k - 1];
      if (!redovna || redovna <= t) continue;
      if (!baza.prihvatljiva(i, t)) continue;
      if (grupa >= 0 && baza.p[i][4] !== grupa) continue;
      if (dozvoljeni && !dozvoljeni.has(i)) continue;
      out.push({ i, lanac: id, cijena: t, redovna, popust: 1 - t / redovna });
    }
  }
  out.sort((a, b) => b.popust - a.popust || a.cijena - b.cijena);
  return out.slice(0, najvise);
}

// Je li cijena stvarno povoljna? Po NN 75/2025 trgovac objavljuje najnižu cijenu u zadnjih 30 dana.
//  'najniza'  – današnja cijena je najniža u 30 dana (prava akcija)
//  'bilo-jeftinije' – u zadnjih 30 dana bilo je jeftinije (popust je u odnosu na višu "redovnu" cijenu)
//  null – lanac ne objavljuje podatak
export function ocjenaCijene(raspon, cijenaCenti) {
  if (!raspon || !raspon.najniza30) return null;
  if (cijenaCenti <= raspon.najniza30) return { tip: 'najniza', najniza30: raspon.najniza30 };
  return { tip: 'bilo-jeftinije', najniza30: raspon.najniza30 };
}
