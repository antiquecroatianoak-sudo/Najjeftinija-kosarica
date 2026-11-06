// Tekst, brojevi i jedinice. Isto pravilo normalizacije kao u uvozu (uvoz/kolicina.py: norm).

const DIJAKRITICI = { č: 'c', ć: 'c', đ: 'd', š: 's', ž: 'z' };

export function norm(tekst) {
  if (!tekst) return '';
  let t = String(tekst).toLowerCase().replace(/[čćđšž]/g, (z) => DIJAKRITICI[z]);
  t = t.normalize('NFKD').replace(/[̀-ͯ]/g, '');
  return t.replace(/[^a-z0-9%]+/g, ' ').trim();
}

// Jednostavno korjenovanje za hrvatske oblike: "jabuke" -> "jabuk", "mlijeka" -> "mlijek".
export function korijen(rijec) {
  const r = norm(rijec);
  if (r.length <= 3) return r;
  for (const nastavak of ['ima', 'ama', 'ovi', 'eve', 'om', 'em', 'ih', 'a', 'e', 'i', 'o', 'u']) {
    if (r.endsWith(nastavak) && r.length - nastavak.length >= 3) return r.slice(0, -nastavak.length);
  }
  return r;
}

const BROJEVI = {
  nula: 0, jedan: 1, jedna: 1, jedno: 1, jednu: 1, jednog: 1, dva: 2, dvije: 2, dvi: 2, tri: 3, cetiri: 4, pet: 5,
  sest: 6, sedam: 7, osam: 8, devet: 9, deset: 10, jedanaest: 11, dvanaest: 12, trinaest: 13, cetrnaest: 14,
  petnaest: 15, sesnaest: 16, sedamnaest: 17, osamnaest: 18, devetnaest: 19, dvadeset: 20, trideset: 30,
  cetrdeset: 40, pedeset: 50, sto: 100, dvjesto: 200, tristo: 300, petsto: 500,
  pola: 0.5, pol: 0.5, cetvrt: 0.25, par: 2,
};

// Riječ jedinice -> [jedinica, množitelj]
const JEDINICE = {
  kg: ['kg', 1], kila: ['kg', 1], kile: ['kg', 1], kilu: ['kg', 1], kilo: ['kg', 1], kil: ['kg', 1], kilograma: ['kg', 1], kilogram: ['kg', 1], kilograme: ['kg', 1],
  g: ['g', 1], gr: ['g', 1], grama: ['g', 1], gram: ['g', 1], grami: ['g', 1],
  dag: ['g', 10], deka: ['g', 10], deke: ['g', 10], dekagrama: ['g', 10], dkg: ['g', 10],
  l: ['l', 1], lit: ['l', 1], litra: ['l', 1], litre: ['l', 1], litru: ['l', 1], litara: ['l', 1], litar: ['l', 1],
  dl: ['ml', 100], decilitar: ['ml', 100], decilitra: ['ml', 100], deci: ['ml', 100],
  ml: ['ml', 1], mililitara: ['ml', 1], mililitar: ['ml', 1],
  kom: ['kom', 1], komad: ['kom', 1], komada: ['kom', 1], komadi: ['kom', 1], komadic: ['kom', 1], kos: ['kom', 1],
  pak: ['pak', 1], paket: ['pak', 1], paketa: ['pak', 1], pakiranje: ['pak', 1], pakiranja: ['pak', 1], kutija: ['pak', 1],
  kutije: ['pak', 1], kutiju: ['pak', 1], boca: ['pak', 1], boce: ['pak', 1], bocu: ['pak', 1], vrecica: ['pak', 1],
  vrecice: ['pak', 1], vrecicu: ['pak', 1], limenka: ['pak', 1], limenke: ['pak', 1], limenku: ['pak', 1],
  tetrapak: ['pak', 1], glavica: ['kom', 1], glavicu: ['kom', 1], glavice: ['kom', 1],
};

export function rijecUBroj(r) {
  if (r == null) return null;
  const s = String(r).replace(',', '.');
  if (/^\d+(\.\d+)?$/.test(s)) return parseFloat(s);
  return Object.prototype.hasOwnProperty.call(BROJEVI, r) ? BROJEVI[r] : null;
}

export function rijecUJedinicu(r) {
  return Object.prototype.hasOwnProperty.call(JEDINICE, r) ? JEDINICE[r] : null;
}

// ---------------------------------------------------------------- jedinice i prikaz
// Osnovna vrsta: kg, l, kom. Korisnik vidi g/kg, ml/l, kom, pak.
export const OSNOVNA = { g: ['kg', 0.001], kg: ['kg', 1], ml: ['l', 0.001], l: ['l', 1], kom: ['kom', 1], pak: ['pak', 1] };

export function uOsnovnu(kolicina, jedinica) {
  const o = OSNOVNA[jedinica];
  return o ? [kolicina * o[1], o[0]] : [kolicina, jedinica];
}

const fmtBroj = (n, dec = 2) => {
  const zaokruzeno = Math.round(n * 10 ** dec) / 10 ** dec;
  return zaokruzeno.toLocaleString('hr-HR', { maximumFractionDigits: dec });
};

export function eur(centi) {
  return (centi / 100).toLocaleString('hr-HR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' €';
}

// Količina pakiranja iz baze (osnovna jedinica) za prikaz: 0.5 kg -> "500 g".
export function prikazPakiranja(kolicina, vrsta) {
  if (!kolicina || !vrsta) return '';
  if (vrsta === 'kg') return kolicina < 1 ? `${fmtBroj(kolicina * 1000, 0)} g` : `${fmtBroj(kolicina)} kg`;
  if (vrsta === 'l') return kolicina < 1 ? `${fmtBroj(kolicina * 1000, 0)} ml` : `${fmtBroj(kolicina)} l`;
  return `${fmtBroj(kolicina, 0)} kom`;
}

export function prikazKolicine(kolicina, jedinica) {
  if (jedinica === 'pak') return `${fmtBroj(kolicina, 0)} ${kolicina === 1 ? 'pakiranje' : kolicina < 5 ? 'pakiranja' : 'pakiranja'}`;
  return `${fmtBroj(kolicina, jedinica === 'kg' || jedinica === 'l' ? 2 : 0)} ${jedinica}`;
}

export function jedinicnaCijena(centi, kolicina, vrsta) {
  if (!kolicina || !vrsta) return '';
  const po = centi / kolicina;
  return `${eur(po)}/${vrsta}`;
}

export function korakKolicine(jedinica) {
  return { g: 100, ml: 250, kg: 0.5, l: 0.5, kom: 1, pak: 1 }[jedinica] || 1;
}

// Broj iz imenika u međunarodni oblik za wa.me (bez +, razmaka i vodeće nule; hrvatski 09x → 3859x)
export function brojZaWhatsApp(broj, pozivni = '385') {
  let d = String(broj || '').trim();
  const plus = d.startsWith('+');
  d = d.replace(/\D/g, '');
  if (!d) return '';
  if (plus) return d;
  if (d.startsWith('00')) return d.slice(2);
  if (d.startsWith('0')) return pozivni + d.slice(1);
  return d;
}
