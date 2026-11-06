// Spremljeno stanje s mobitela (localStorage) i stavke iz tuđih poveznica: provjera tipova i granica.
// Neispravan, oštećen ili stariji zapis nikad ne smije srušiti aplikaciju ni umetnuti nešto neočekivano.
import { novaStavkaId } from './popis.js';

// Svako polje dobije ispravan tip; neispravne stavke se izbacuju umjesto da sruše zaslon.
const JEDINICE = ['g', 'kg', 'ml', 'l', 'kom', 'pak'];
export function ocistiStavku(x) {
  if (!x || typeof x !== 'object') return null;
  const broj = (v, d) => (v != null && v !== '' && Number.isFinite(Number(v)) ? Number(v) : d);   // null nije 0
  const kolicina = broj(x.kolicina, 1);
  return {
    ...x,
    id: String(x.id || novaStavkaId()), tekst: String(x.tekst ?? '').slice(0, 120), upit: String(x.upit ?? '').slice(0, 120),
    filtar: String(x.filtar ?? '').slice(0, 60), g: Math.trunc(broj(x.g, -1)), pg: Math.trunc(broj(x.pg, -1)),
    kolicina: kolicina > 0 && kolicina <= 1000 ? kolicina : 1, jedinica: JEDINICE.includes(x.jedinica) ? x.jedinica : 'pak',
    zadano: !!x.zadano, uKosari: !!x.uKosari, samoTaj: !!x.samoTaj,
    proizvod: Number.isInteger(x.proizvod) && x.proizvod >= 0 ? x.proizvod : null,
    odbijeni: Array.isArray(x.odbijeni) ? x.odbijeni.filter(Number.isInteger) : [],
  };
}
export function ocistiStanje(s) {
  s.stavke = (Array.isArray(s.stavke) ? s.stavke : []).slice(0, 200).map(ocistiStavku).filter(Boolean);
  s.lanci = Array.isArray(s.lanci) ? s.lanci.filter((x) => typeof x === 'string') : null;
  s.favoriti = Array.isArray(s.favoriti) ? s.favoriti.filter((x) => typeof x === 'string') : [];
  s.povijest = s.povijest && typeof s.povijest === 'object' && !Array.isArray(s.povijest) ? s.povijest : {};
  if (!Array.isArray(s.usteda.kupnje)) s.usteda = { ukupno: 0, kupnje: [] };
  s.usteda.ukupno = Number.isFinite(Number(s.usteda.ukupno)) ? Number(s.usteda.ukupno) : 0;
  s.lokacija.radijus = [2, 5, 10, 20].includes(s.lokacija.radijus) ? s.lokacija.radijus : 5;
  return s;
}

// Vraća redni broj grupe/podgrupe iz spremljenog ID-a (vidi zapamtiIdGrupa u app.js).
export function vratiGrupePoId(stavke, grupe) {
  for (const s of stavke) {
    if (s.gid) {
      const gi = grupe.findIndex((g) => g.id === s.gid);
      s.g = gi;
      s.pg = gi >= 0 && s.pgid ? grupe[gi].pod.findIndex((p) => p.id === s.pgid) : -1;
      if (gi < 0) { s.upit = s.upit || s.tekst; }            // grupa više ne postoji: traži po tekstu (osvjeziStavke prepozna)
    } else if (s.g >= grupe.length || (s.g >= 0 && s.pg >= (grupe[s.g].pod || []).length)) {
      s.g = -1; s.pg = -1; s.upit = s.upit || s.tekst;         // stari zapis s nevaljanim brojem
    }
  }
}

