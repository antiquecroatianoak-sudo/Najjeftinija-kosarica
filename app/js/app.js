// Najjeftinija košarica – sučelje aplikacije.
import { eur, prikazPakiranja, prikazKolicine, jedinicnaCijena, korakKolicine, norm, brojZaWhatsApp } from './tekst.js';
import { pripremiGrupe, rastavi, novaStavkaId, kanon, osvjeziStavke } from './popis.js';
import { Baza, rezultatA, rezultatB, rezultatC, procjenaUstede, akcije, udaljenost, ocjenaCijene } from './usporedba.js';
import { ucitajPodatke, ucitajPoslovnice, pripremiPoslovnice, DRZAVE } from './podaci.js';
import { ukljuciHvatanje, zabiljezi, izvjesce, obrisiGreske, VERZIJA_APLIKACIJE } from './greske.js';

ukljuciHvatanje();

const REPOZITORIJ = 'https://github.com/antiquecroatianoak-sudo/Najjeftinija-kosarica';
const RADIJUSI = [2, 5, 10, 20];
const NAJVISE_POSLOVNICA = 60;
const BOJE = {
  konzum: '#e30613', lidl: '#0050aa', kaufland: '#d4001a', plodine: '#f28c00', tommy: '#c8102e', studenac: '#00843d',
  spar: '#007a3d', interspar: '#b5121b', eurospin: '#1d3f94', ntl: '#ef7d00', ktc: '#0067b1', dm: '#7b2481', zabac: '#5da130',
  ribola: '#00a3e0', boso: '#a6192e', vrutak: '#2e7d32', trgocentar: '#6d4c41', lorenco: '#455a64', brodokomerc: '#283593',
};
const boja = (id) => BOJE[id] || `hsl(${[...id].reduce((s, z) => s + z.charCodeAt(0), 0) * 47 % 360} 55% 42%)`;

const IKONE = {
  mikrofon: '<svg viewBox="0 0 24 24"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></svg>',
  plus: '<svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg>',
  brisi: '<svg viewBox="0 0 24 24"><path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14"/></svg>',
  lokot: '<svg viewBox="0 0 24 24"><rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>',
  otkljucaj: '<svg viewBox="0 0 24 24"><rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 7.5-2"/></svg>',
  podijeli: '<svg viewBox="0 0 24 24"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="m8.6 13.5 6.8 4M15.4 6.5l-6.8 4"/></svg>',
  zamijeni: '<svg viewBox="0 0 24 24"><path d="M17 2l4 4-4 4M3 11V9a3 3 0 0 1 3-3h15M7 22l-4-4 4-4M21 13v2a3 3 0 0 1-3 3H3"/></svg>',
  info: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 16v-4M12 8h.01"/></svg>',
  barkod: '<svg viewBox="0 0 24 24"><path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2M7 8v8M10 8v8M13 8v8M17 8v8"/></svg>',
  obitelj: '<svg viewBox="0 0 24 24"><circle cx="9" cy="7" r="3"/><path d="M3 21v-1a6 6 0 0 1 12 0v1M16 3.5a3 3 0 0 1 0 5.8M21 21v-1a6 6 0 0 0-4-5.6"/></svg>',
  status: '<svg viewBox="0 0 24 24"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>',
  trgovina: '<svg viewBox="0 0 24 24"><path d="M3 9l1.5-5h15L21 9M3 9h18v2a3 3 0 0 1-6 0 3 3 0 0 1-6 0 3 3 0 0 1-6 0V9zM5 13v8h14v-8"/></svg>',
  postavke: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 0 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 0 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 0 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 0 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg>',
  greska: '<svg viewBox="0 0 24 24"><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0zM12 9v4M12 17h.01"/></svg>',
  novac: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M15 9.5a3 3 0 0 0-3-1.5c-1.7 0-3 .9-3 2.2 0 3 6 1.6 6 4.6 0 1.3-1.3 2.2-3 2.2a3.3 3.3 0 0 1-3-1.6M12 6v2M12 16v2"/></svg>',
  srce: '<svg viewBox="0 0 24 24"><path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1-1.1a5.5 5.5 0 0 0-7.8 7.8l1 1.1L12 21l7.8-7.5 1-1.1a5.5 5.5 0 0 0 0-7.8z"/></svg>',
  natrag: '<svg viewBox="0 0 24 24"><path d="M15 18l-6-6 6-6"/></svg>',
  lokacija: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/><circle cx="12" cy="12" r="7"/></svg>',
  kopiraj: '<svg viewBox="0 0 24 24"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>',
  zastava: '<svg viewBox="0 0 24 24"><path d="M4 22V4M4 4h13l-2 4 2 4H4"/></svg>',
  kvacica: '<svg viewBox="0 0 24 24"><path d="M20 6 9 17l-5-5"/></svg>',
  whatsapp: '<svg viewBox="0 0 24 24" class="puna"><path d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2zm5.3 14.1c-.2.6-1.3 1.2-1.8 1.2-.5.1-1 .2-3.3-.7-2.8-1.1-4.6-4-4.7-4.2-.1-.2-1.1-1.5-1.1-2.9s.7-2.1 1-2.4c.3-.3.6-.3.8-.3h.6c.2 0 .4 0 .6.5l.8 2c.1.2.1.4 0 .5l-.4.6-.4.4c-.1.1-.3.3-.1.6.2.3.7 1.2 1.5 1.9 1 .9 1.9 1.2 2.2 1.3.3.1.4.1.6-.1l.8-1c.2-.3.4-.2.6-.1l1.9.9c.3.1.5.2.5.3.1.2.1.8-.1 1.5z"/></svg>',
  imenik: '<svg viewBox="0 0 24 24"><rect x="4" y="2" width="16" height="20" rx="2"/><circle cx="12" cy="10" r="3"/><path d="M7.5 18a4.5 4.5 0 0 1 9 0M2 7h2M2 12h2M2 17h2"/></svg>',
  viber: '<svg viewBox="0 0 24 24"><path d="M5 4.5C7 2.8 9.5 2.5 12 2.5s5 .3 7 2c1.8 1.6 2.4 3.9 2.4 7s-.6 5.4-2.4 7c-1.6 1.4-3.6 1.8-5.6 1.9L10 23v-2.7c-1.9-.2-3.6-.6-5-1.8C3.2 16.9 2.6 14.6 2.6 11.5S3.2 6.1 5 4.5z"/><path d="M9 7.5c.5 2.5 2.5 5 5.5 6.5l1-1.2 2 1-.5 1.7c-4.5-.5-8-4-8.7-8.2L9.5 7"/></svg>',
  akcija: '<svg viewBox="0 0 24 24"><path d="M20.6 13.4 13.4 20.6a2 2 0 0 1-2.8 0L3 13V3h10l7.6 7.6a2 2 0 0 1 0 2.8z"/><circle cx="7.5" cy="7.5" r="1.5"/></svg>',
  zvijezda: '<svg viewBox="0 0 24 24"><path d="m12 2 3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21l1.2-6.8-5-4.9 6.9-1z"/></svg>',
  poruka: '<svg viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
};

// ---------------------------------------------------------------- stanje
const KLJUC = 'kosarica-stanje-v1';
const POCETNO = {
  drzava: 'hr', stavke: [], zakljucano: false, lanci: null, rezTab: 'B', zaslon: 'popis',
  lokacija: { ukljucena: false, lat: null, lon: null, radijus: 5, izvor: '' },
  usteda: { ukupno: 0, kupnje: [] }, premium: false, tema: 'auto', kupljenoKljuc: '',
  povijest: {},        // id grupe/podgrupe -> koliko puta dodano (za "Često kupuješ")
  favoriti: [],        // barkod ili naziv proizvoda
};
let S = ucitajStanje();
let P = null;           // { meta, grupe, poslovnice, baza, izSpremista }
let zadnjiIzracun = null;
let instalacija = null;
let karta = null;

function ucitajStanje() {
  try {
    const s = JSON.parse(localStorage.getItem(KLJUC) || 'null');
    return s ? { ...POCETNO, ...s, lokacija: { ...POCETNO.lokacija, ...(s.lokacija || {}) }, usteda: { ...POCETNO.usteda, ...(s.usteda || {}) } } : structuredClone(POCETNO);
  } catch (e) {
    zabiljezi('stanje', 'Spremljeno stanje se ne može pročitati; počinjem iznova', e.message);
    return structuredClone(POCETNO);
  }
}
function spremi() {
  try { localStorage.setItem(KLJUC, JSON.stringify(S)); } catch (e) { zabiljezi('stanje', 'Spremanje nije uspjelo', e.message); }
}

const $ = (sel, korijen = document) => korijen.querySelector(sel);
const esc = (t) => String(t ?? '').replace(/[&<>"']/g, (z) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[z]));
const datumHR = (iso) => {
  if (!iso) return '–';
  const d = new Date(iso.length === 10 ? iso + 'T12:00:00' : iso);
  return isNaN(d) ? iso : d.toLocaleDateString('hr-HR', { day: 'numeric', month: 'numeric', year: 'numeric' });
};
const vrijemeHR = (iso) => (iso ? new Date(iso).toLocaleString('hr-HR', { day: 'numeric', month: 'numeric', hour: '2-digit', minute: '2-digit' }) : '–');

function nazivLanca(id) {
  const l = P && P.meta.lanci.find((x) => x.id === id);
  return l ? l.naziv : id;
}
function sviLanci() { return P ? Object.keys(P.baza.lanci) : []; }
function odabraniLanci() {
  const svi = sviLanci();
  return S.lanci ? svi.filter((l) => S.lanci.includes(l)) : svi;
}

// ---------------------------------------------------------------- poruke i ploča
let porukaSat;
function poruka(tekst, akcija) {
  const el = $('#poruka');
  el.innerHTML = `<span>${esc(tekst)}</span>${akcija ? `<button type="button">${esc(akcija.tekst)}</button>` : ''}`;
  el.hidden = false;
  if (akcija) el.querySelector('button').onclick = () => { el.hidden = true; akcija.radi(); };
  clearTimeout(porukaSat);
  porukaSat = setTimeout(() => { el.hidden = true; }, akcija ? 6000 : 3200);
}
function otvoriPlocu(html, nakon) {
  const p = $('#ploca');
  p.querySelector('.ploca-sadrzaj').innerHTML = html;
  p.hidden = false;
  if (nakon) nakon(p.querySelector('.ploca-sadrzaj'));
}
function zatvoriPlocu() { $('#ploca').hidden = true; }

async function kopiraj(tekst) {
  try {
    await navigator.clipboard.writeText(tekst);
    poruka('Kopirano.');
  } catch {
    const t = document.createElement('textarea');
    t.value = tekst; document.body.appendChild(t); t.select();
    try { document.execCommand('copy'); poruka('Kopirano.'); } catch { poruka('Kopiranje nije uspjelo – označi tekst i kopiraj ručno.'); }
    t.remove();
  }
}

// ---------------------------------------------------------------- navigacija
function idi(zaslon) {
  S.zaslon = zaslon;
  spremi();
  for (const b of document.querySelectorAll('.izbornik button')) {
    const glavni = { usteda: 'vise', obitelj: 'vise', skener: 'vise', status: 'vise', trgovine: 'vise', postavke: 'vise', greska: 'vise', o: 'vise' }[zaslon] || zaslon;
    b.classList.toggle('aktivno', b.dataset.idi === glavni);
  }
  prikazi();
  window.scrollTo({ top: 0 });
}

function prikazi() {
  const sadrzaj = $('#sadrzaj');
  osvjeziUstedu();
  if (!P) return;
  if (karta && S.zaslon !== 'karta') { const k = karta; karta = null; import('./karta.js').then((m) => m.ukloniKartu(k)); }
  try {
    const zasloni = { popis: zaslonPopis, rezultati: zaslonRezultati, akcije: zaslonAkcije, karta: zaslonKarta, vise: zaslonVise,
      usteda: zaslonUsteda, favoriti: zaslonFavoriti, obitelj: zaslonObitelj, skener: zaslonSkener, status: zaslonStatus, trgovine: zaslonTrgovine,
      postavke: zaslonPostavke, greska: zaslonGreska, o: zaslonO };
    (zasloni[S.zaslon] || zaslonPopis)(sadrzaj);
  } catch (e) {
    zabiljezi('prikaz', e.message, e.stack);
    sadrzaj.innerHTML = karticaGreske('Ovaj zaslon se nije mogao prikazati.');
  }
}

function karticaGreske(tekst) {
  return `<div class="zaslon"><div class="kartica greska-kartica"><h3>Nešto nije u redu</h3><p class="prigusen" style="margin-top:6px">${esc(tekst)} Pokušaj ponovno; ako se ponavlja, pošalji izvješće o grešci.</p>
  <div class="redak" style="margin-top:12px"><button class="gumb mali" data-akcija="ponovno">Pokušaj ponovno</button><button class="gumb mali" data-idi="greska">Izvješće o grešci</button></div></div></div>`;
}

function osvjeziUstedu() {
  $('#ustedaIznos').textContent = eur(Math.round(S.usteda.ukupno || 0));
}

function oglas() {
  if (S.premium) return '';
  return `<aside class="oglas" aria-label="Oglas"><b>Oglas</b><span>Ovdje će biti mali, nenametljiv oglas. Trgovine ne mogu platiti bolji položaj u rezultatima.</span></aside>`;
}

// ---------------------------------------------------------------- POPIS
function opisStavke(s) {
  if (s.g >= 0) {
    const g = P.grupe[s.g];
    const pod = s.pg >= 0 ? g.pod[s.pg].naziv : 'sve vrste';
    if (s.samoTaj && s.proizvod != null) return `${g.ikona} točno ovaj proizvod`;
    if (s.filtar) {
      const ima = P.baza.filtarPronaden(s);
      return `${g.naziv} · ${ima ? `samo „${esc(s.filtar)}”` : `${pod} <span class="upozorenje">(„${esc(s.filtar)}” nije pronađeno)</span>`}`;
    }
    // ne ponavljaj ime: "Mlijeko" + "sve vrste", a ne "Mlijeko" + "Mlijeko · sve vrste"
    return nazivStavke(s).toLowerCase() === g.naziv.toLowerCase() ? pod : `${g.naziv} · ${pod}`;
  }
  if (s.samoTaj && s.proizvod != null) return 'točno ovaj proizvod';
  const n = P.baza.trazi(s.upit || s.tekst, 1).length;
  return n ? `traži „${s.upit || s.tekst}” u nazivima proizvoda` : '<span class="upozorenje">nije pronađeno – dodirni za ispravak</span>';
}
function ikonaStavke(s) { return s.g >= 0 ? P.grupe[s.g].ikona || '🛒' : '🔎'; }
function nazivStavke(s) {
  if (s.samoTaj && s.proizvod != null) return P.baza.p[s.proizvod][0];
  if (s.g >= 0 && s.pg >= 0) return P.grupe[s.g].pod[s.pg].naziv.replace(/^./, (z) => z.toUpperCase());
  if (s.g >= 0 && !s.filtar) return P.grupe[s.g].naziv;      // "mlijeka" -> "Mlijeko"
  return s.tekst.replace(/^./, (z) => z.toUpperCase());
}

// Odjeli trgovine redom kojim se obično prolazi (kao Bring!): na zaključanom popisu stavke su po odjelima.
const ODJELI = [
  ['Voće i povrće', ['banane', 'jabuke', 'naranca', 'limun', 'voce-ostalo', 'krumpir', 'luk', 'mrkva', 'rajcica', 'krastavci', 'paprika', 'salata', 'kupus']],
  ['Kruh i peciva', ['kruh', 'peciva', 'kolaci']],
  ['Mliječno i jaja', ['mlijeko', 'biljni-napitak', 'jogurt', 'vrhnje', 'maslac', 'sir', 'jaja']],
  ['Meso, riba i suhomesnato', ['piletina', 'meso', 'riba', 'suhomesnato', 'gotova-jela']],
  ['Smrznuto', ['smrznuto', 'pomfrit', 'sladoled']],
  ['Namirnice', ['riza', 'tjestenina', 'brasno', 'secer', 'sol', 'ulje', 'ocat', 'zacini', 'grah', 'zimnica', 'rajcica-konzerva', 'zitarice', 'dzem']],
  ['Kava, čaj i slatko', ['kava', 'caj', 'napici', 'cokolada', 'keksi', 'slatkisi', 'grickalice', 'proteini']],
  ['Pića', ['voda', 'sok', 'pivo', 'vino', 'zestoka']],
  ['Dom, higijena i ostalo', ['bebe', 'ljubimci', 'higijena', 'kozmetika', 'toaletni-papir', 'deterdzent', 'posude', 'ciscenje', 'kucanstvo', 'osvjezivaci', 'insekti']],
];
function odjelStavke(s) {
  if (s.g < 0) return ODJELI.length;                 // pretraga po nazivu: na kraju
  const id = P.grupe[s.g].id;
  const i = ODJELI.findIndex(([, grupe]) => grupe.includes(id));
  return i < 0 ? ODJELI.length : i;
}

const ZADANE_BRZE = ['kruh', 'mlijeko', 'jaja', 'krumpir', 'banane', 'kava', 'piletina', 'toaletni-papir', 'sir', 'jogurt'];

// "Često kupuješ": najčešće dodavane grupe/podgrupe korisnika, dopunjene uobičajenima (kao Listonic/Bring!)
function cestoKupujes() {
  const out = [];
  const vec = new Set(S.stavke.map((s) => `${s.g}|${s.pg}`));
  const kljucevi = Object.entries(S.povijest || {}).sort((x, y) => y[1] - x[1]).map(([k]) => k);
  for (const k of [...kljucevi, ...ZADANE_BRZE]) {
    const [gid, pid] = k.split('/');
    const g = P.grupe.findIndex((x) => x.id === gid);
    if (g < 0) continue;
    const pg = pid ? P.grupe[g].pod.findIndex((x) => x.id === pid) : -1;
    if (pid && pg < 0) continue;
    if (vec.has(`${g}|${pg}`) || out.some((x) => x.g === g && x.pg === pg)) continue;
    out.push({ g, pg, naziv: pg >= 0 ? P.grupe[g].pod[pg].naziv : P.grupe[g].naziv, ikona: P.grupe[g].ikona });
    if (out.length >= 10) break;
  }
  return out;
}

function zapamtiPovijest(stavke) {
  S.povijest = S.povijest || {};
  for (const s of stavke) {
    if (s.g < 0 || s.samoTaj) continue;
    const k = P.grupe[s.g].id + (s.pg >= 0 ? '/' + P.grupe[s.g].pod[s.pg].id : '');
    S.povijest[k] = (S.povijest[k] || 0) + 1;
  }
}

function zaslonPopis(el) {
  const stavke = S.stavke;
  const prazan = !stavke.length;
  const brze = cestoKupujes();
  const imaPovijest = Object.keys(S.povijest || {}).length > 0;
  const uKosari = stavke.filter((s) => s.uKosari).length;
  // redoslijed: još nekupljeno gore, u košarici dolje (način kupnje)
  const poredane = [...stavke].sort((x, y) => (S.zakljucano ? odjelStavke(x) - odjelStavke(y) : 0) || (x.uKosari ? 1 : 0) - (y.uKosari ? 1 : 0));
  const naslovOdjela = (s, k) => {
    if (!S.zakljucano) return '';
    const o = odjelStavke(s);
    if (k > 0 && odjelStavke(poredane[k - 1]) === o) return '';
    return `<li class="odjel">${esc(o < ODJELI.length ? ODJELI[o][0] : 'Ostalo')}</li>`;
  };
  el.innerHTML = `<div class="zaslon">
    ${gumbLokacije()}
    ${S.zakljucano ? `<div class="zakljucano">${IKONE.lokot}<span class="razmak">Popis je zaključan. U trgovini označi što je u košarici.</span><button class="gumb mali" data-akcija="otkljucaj">Uredi</button></div>` : `
    <section class="kartica glas ${prazan ? '' : 'sazeto'}">
      ${prazan ? `<h2>Što trebaš kupiti?</h2>
      <ol class="koraci"><li><b>1</b> Reci ili upiši popis</li><li><b>2</b> Zaključaj popis</li><li><b>3</b> Vidi gdje je najjeftinije</li></ol>` : ''}
      <div class="glas-red">
        <button class="mikrofon" id="mikrofon" aria-label="Govori popis">${IKONE.mikrofon}</button>
        <div class="glas-tekst"><div class="stanje-glasa" id="stanjeGlasa">${prazan ? 'Dodirni i reci, npr. „kruh, dvije litre mlijeka i deset jaja”' : 'Dodirni i dodaj još'}</div>
        <div class="prijepis" id="prijepis"></div></div>
      </div>
      <form class="upis" id="upis" autocomplete="off">
        <input id="upisPolje" type="text" inputmode="text" enterkeyhint="done" placeholder="ili upiši: kruh, mlijeko, 1 kg krumpira" aria-label="Upiši stavku" aria-autocomplete="list" aria-controls="prijedlozi">
        <button class="gumb glavni" aria-label="Dodaj">${IKONE.plus}</button>
      </form>
      <div class="prijedlozi" id="prijedlozi" role="listbox" hidden></div>
      <div class="brze-naslov">${imaPovijest ? 'Često kupuješ' : 'Brzo dodaj'}</div>
      <div class="cipovi vodoravno">${brze.map((x) => `<button class="cip" data-akcija="brzo" data-g="${x.g}" data-pg="${x.pg}">${x.ikona} ${esc(x.naziv.replace(/^./, (z) => z.toUpperCase()))}</button>`).join('')}</div>
    </section>`}
    <section class="kartica">
      <div class="redak"><h3 class="razmak">Moj popis${stavke.length ? ` <span class="oznaka">${stavke.length}</span>` : ''}</h3>
      ${uKosari ? `<span class="oznaka zelena">${IKONE.kvacica} ${uKosari} od ${stavke.length} u košarici</span>` : ''}
      ${stavke.length && !S.zakljucano ? '<button class="gumb mali" data-akcija="isprazni">Isprazni</button>' : ''}</div>
      ${stavke.length ? `<ul class="stavke" style="margin-top:6px">${poredane.map((s, k) => `${naslovOdjela(s, k)}
        <li class="stavka ${s.uKosari ? 'u-kosari' : ''}">
          <button class="kvacica-kosara" data-akcija="u-kosaru" data-id="${s.id}" role="checkbox" aria-checked="${!!s.uKosari}" aria-label="${s.uKosari ? 'Makni iz košarice' : 'Stavi u košaricu'}">${s.uKosari ? IKONE.kvacica : ''}</button>
          <span class="stavka-ikona" aria-hidden="true">${ikonaStavke(s)}</span>
          <button class="stavka-tekst" data-akcija="uredi" data-id="${s.id}" ${S.zakljucano ? 'disabled' : ''}>
            <span class="stavka-naziv">${esc(nazivStavke(s))}</span>
            <span class="stavka-opis">${opisStavke(s)}</span>
          </button>
          <div class="kolicina">
            ${S.zakljucano ? '' : `<button data-akcija="manje" data-id="${s.id}" aria-label="Manje">−</button>`}
            <span>${esc(prikazKolicine(s.kolicina, s.jedinica))}${s.zadano ? '<br><span class="zadano">zadano</span>' : ''}</span>
            ${S.zakljucano ? '' : `<button data-akcija="vise" data-id="${s.id}" aria-label="Više">+</button>`}
          </div>
        </li>`).join('')}</ul>` : `<div class="prazno"><div class="velika">🧺</div><p>Popis je prazan. Reci, upiši ili dodirni nešto iz „${imaPovijest ? 'Često kupuješ' : 'Brzo dodaj'}”.</p></div>`}
    </section>
    ${stavke.length ? plociceDijeljenja() : plocicePrecaca()}
    ${stavke.length ? (S.zakljucano
      ? `<button class="gumb glavni puni" data-idi="rezultati">Pogledaj rezultate</button>`
      : `<button class="gumb glavni puni" data-akcija="zakljucaj">${IKONE.lokot} Zaključaj popis i usporedi cijene</button>
         <p class="sitno" style="text-align:center">Količinu bez broja aplikacija postavlja na uobičajenu (npr. mlijeko 1 l, krumpir 1 kg) – promijeni je gumbima − i +. U trgovini dodirni kružić pokraj stavke kad je u košarici.</p>`) : ''}
  </div>`;
  if (!S.zakljucano) {
    const polje = $('#upisPolje');
    $('#upis').onsubmit = (e) => {
      e.preventDefault();
      if (dodajTekst(polje.value)) polje.value = '';
    };
    polje.oninput = () => prikaziPrijedloge(polje.value);
    pripremiGlas();
  }
}

// Velike šarene pločice: slanje popisa (WhatsApp, imenik, Viber, ostalo)
function plociceDijeljenja() {
  const t = encodeURIComponent(tekstPopisa());
  return `<section class="kartica dijeli-kartica">
    <h3>Pošalji popis obitelji</h3>
    <div class="plocice">
      <a class="plocica wa" href="https://wa.me/?text=${t}" target="_blank" rel="noopener" data-dijeli="whatsapp"><span class="pl-ik">${IKONE.whatsapp}</span><b>WhatsApp</b><span>odaberi osobu ili grupu</span></a>
      <button class="plocica imenik" data-akcija="imenik"><span class="pl-ik">${IKONE.imenik}</span><b>Iz imenika</b><span>dodirni osobu iz kontakata</span></button>
      <a class="plocica viber" href="viber://forward?text=${t}" data-dijeli="viber"><span class="pl-ik">${IKONE.viber}</span><b>Viber</b><span>pošalji u Viberu</span></a>
      <button class="plocica ostalo" data-akcija="podijeli-popis"><span class="pl-ik">${IKONE.podijeli}</span><b>SMS i ostalo</b><span>poruka, e-mail, kopiraj</span></button>
    </div>
    <p class="sitno">Primatelj dobije popis i poveznicu – kad je dodirne, isti popis otvori se u njegovoj aplikaciji.</p>
  </section>`;
}

// Kad je popis prazan: glavne funkcije na dohvat prsta
function plocicePrecaca() {
  return `<div class="plocice precaci">
    <button class="plocica akcije" data-idi="akcije"><span class="pl-ik">${IKONE.akcija}</span><b>Akcije tjedna</b><span>najveći popusti</span></button>
    <button class="plocica skener" data-idi="skener"><span class="pl-ik">${IKONE.barkod}</span><b>Skeniraj barkod</b><span>cijena u trgovini</span></button>
    <button class="plocica favoriti" data-idi="favoriti"><span class="pl-ik">${IKONE.zvijezda}</span><b>Favoriti</b><span>${(S.favoriti || []).length} praćenih</span></button>
    <button class="plocica obitelj" data-idi="obitelj"><span class="pl-ik">${IKONE.obitelj}</span><b>Obiteljski popis</b><span>primi ili pošalji</span></button>
  </div>`;
}

// Tekst popisa za slanje (isti za WhatsApp, Viber, SMS i imenik)
function tekstPopisa() {
  const link = `${location.origin}${location.pathname}#popis=${kodPopisa()}`;
  return `🛒 Popis za kupovinu (${S.stavke.length}): ${S.stavke.map(nazivStavke).join(', ')}\nOtvori u aplikaciji Najjeftinija košarica:\n${link}`;
}

// Imenik: Contact Picker (Chrome na Androidu); inače izbor osobe u WhatsAppu/SMS-u
async function posaljiIzImenika() {
  const tekst = tekstPopisa();
  if (!('contacts' in navigator && navigator.contacts && typeof navigator.contacts.select === 'function')) {
    ponudiDijeljenje(tekst, 'Pošalji popis');
    poruka('Ovaj preglednik ne otvara imenik – osobu odaberi u WhatsAppu, Viberu ili SMS-u.');
    return;
  }
  let kontakti;
  try {
    kontakti = await navigator.contacts.select(['name', 'tel'], { multiple: false });
  } catch (e) {
    zabiljezi('imenik', e.name, e.message);
    ponudiDijeljenje(tekst, 'Pošalji popis');
    return;
  }
  if (!kontakti || !kontakti.length) return;       // korisnik je odustao
  const k = kontakti[0];
  const ime = (k.name && k.name[0]) || 'Kontakt';
  const brojevi = [...new Set((k.tel || []).map((x) => String(x).trim()).filter(Boolean))];
  if (!brojevi.length) { poruka(`${ime} nema broj telefona u imeniku.`); return; }
  const t = encodeURIComponent(tekst);
  otvoriPlocu(`<h3>Pošalji popis: ${esc(ime)}</h3>
    ${brojevi.map((b) => `<div class="kontakt-red"><span class="razmak"><b>${esc(b)}</b></span></div>
      <div class="plocice">
        <a class="plocica wa" href="https://wa.me/${brojZaWhatsApp(b)}?text=${t}" target="_blank" rel="noopener"><span class="pl-ik">${IKONE.whatsapp}</span><b>WhatsApp</b><span>${esc(ime)}</span></a>
        <a class="plocica ostalo" href="sms:${encodeURIComponent(b)}?&body=${t}"><span class="pl-ik">${IKONE.poruka}</span><b>SMS</b><span>${esc(ime)}</span></a>
      </div>`).join('')}`);
}

// Prijedlozi dok korisnik tipka (grupe i podgrupe koje počinju upisanim, uključujući ijekavski/ekavski zapis)
function prijedloziZa(tekst) {
  const zadnji = tekst.split(/,|\bi\b/).pop().trim();
  const n = kanon(zadnji);
  const nn = norm(zadnji);
  if (nn.length < 2) return [];
  // vrijedi i obični zapis ("mli" → mlijeko) i ijekavski/ekavski ("mle" → mlijeko)
  const pocinje = (ime) => { const a = norm(ime); const b = kanon(ime); return a.startsWith(nn) || b.startsWith(n); };
  const sadrzi = (ime) => norm(ime).split(' ').some((r) => r.startsWith(nn)) || kanon(ime).split(' ').some((r) => r.startsWith(n));
  const out = [];
  P.grupe.forEach((g, gi) => {
    const kandidati = [[g.naziv, -1], ...(g.rijeci || []).map((r) => [r, -1]), ...(g.pod || []).map((p, pi) => [p.naziv, pi])];
    for (const [ime, pg] of kandidati) {
      if (!(pocinje(ime) || sadrzi(ime))) continue;
      if (out.some((x) => x.g === gi && x.pg === pg)) continue;
      out.push({ g: gi, pg, naziv: pg >= 0 ? g.pod[pg].naziv : g.naziv, ikona: g.ikona, grupa: g.naziv, pocinje: pocinje(ime) });
    }
  });
  out.sort((x, y) => (y.pocinje - x.pocinje) || (x.pg - y.pg) || x.naziv.length - y.naziv.length);
  return out.slice(0, 6);
}

function prikaziPrijedloge(tekst) {
  const el = $('#prijedlozi');
  if (!el) return;
  const p = prijedloziZa(tekst);
  if (!p.length) { el.hidden = true; el.innerHTML = ''; return; }
  el.innerHTML = p.map((x) => `<button type="button" role="option" class="prijedlog" data-akcija="prijedlog" data-g="${x.g}" data-pg="${x.pg}">
    <span>${x.ikona}</span><span class="razmak"><b>${esc(x.naziv.replace(/^./, (z) => z.toUpperCase()))}</b>${x.pg >= 0 ? `<span class="sitno"> · ${esc(x.grupa)}</span>` : '<span class="sitno"> · sve vrste</span>'}</span></button>`).join('');
  el.hidden = false;
}

function dodajGrupu(g, pg) {
  const grupa = P.grupe[g];
  const [k, j] = grupa.zadano;
  const n = { id: novaStavkaId(), tekst: pg >= 0 ? grupa.pod[pg].naziv : grupa.naziv, g, pg, upit: '', filtar: '', kolicina: k, jedinica: j, zadano: true };
  const ista = S.stavke.find((s) => s.g === g && s.pg === pg && !s.samoTaj && !s.filtar && s.jedinica === j);
  if (ista) { ista.kolicina = Math.round((ista.kolicina + k) * 1000) / 1000; ista.zadano = false; } else S.stavke.push(n);
  zapamtiPovijest([n]);
  promjenaPopisa();
  poruka(`Dodano: ${nazivStavke(n)}`);
}

function dodajTekst(tekst) {
  const nove = rastavi(tekst);
  if (!nove.length) { poruka('Nisam razumio. Pokušaj, npr. „kruh i mlijeko”.'); return false; }
  zapamtiPovijest(nove);
  for (const n of nove) {
    const ista = S.stavke.find((s) => s.g === n.g && s.pg === n.pg && s.g >= 0 && !s.samoTaj && s.jedinica === n.jedinica && (s.filtar || '') === (n.filtar || ''));
    if (ista) { ista.kolicina = Math.round((ista.kolicina + n.kolicina) * 1000) / 1000; ista.zadano = false; } else S.stavke.push(n);
  }
  promjenaPopisa();
  poruka(`Dodano: ${nove.map((n) => nazivStavke(n)).join(', ')}`);
  return true;
}

function promjenaPopisa() {
  zadnjiIzracun = null;
  spremi();
  prikazi();
}

// ---------------------------------------------------------------- glas
let prepoznavanje = null;
function pripremiGlas() {
  const gumb = $('#mikrofon');
  const stanje = $('#stanjeGlasa');
  const prijepis = $('#prijepis');
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    stanje.textContent = 'Glasovni unos nije podržan u ovom pregledniku – upiši popis ispod.';
    gumb.disabled = true;
    gumb.style.opacity = '.45';
    return;
  }
  gumb.onclick = () => {
    if (prepoznavanje) { prepoznavanje.stop(); return; }
    const r = new SR();
    r.lang = 'hr-HR';
    r.interimResults = true;
    r.continuous = false;
    r.maxAlternatives = 1;
    let konacno = '';
    prepoznavanje = r;
    gumb.classList.add('slusa');
    stanje.className = 'stanje-glasa';
    stanje.textContent = 'Slušam… govori sada';
    prijepis.textContent = '';
    r.onresult = (e) => {
      let privremeno = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) konacno += e.results[i][0].transcript + ' ';
        else privremeno += e.results[i][0].transcript;
      }
      prijepis.textContent = (konacno + privremeno).trim();
    };
    r.onerror = (e) => {
      const poruke = {
        'not-allowed': 'Mikrofon nije dopušten. U Chromeu dodirni lokot pokraj adrese → Dopuštenja → Mikrofon → Dopusti.',
        'service-not-allowed': 'Glasovni unos nije dopušten na ovom uređaju. Upiši popis ispod.',
        'no-speech': 'Nisam ništa čuo. Dodirni mikrofon i pokušaj ponovno.',
        'audio-capture': 'Mikrofon nije pronađen.',
        network: 'Za glasovni unos treba internet. Upiši popis ispod.',
        aborted: '',
      };
      stanje.className = 'stanje-glasa greska';
      stanje.textContent = poruke[e.error] ?? `Glasovni unos nije uspio (${e.error}).`;
      if (e.error !== 'aborted' && e.error !== 'no-speech') zabiljezi('glas', e.error, e.message || '');
    };
    // sigurnosni sat: neki Android preglednici nikad ne jave kraj – mikrofon se ne smije zaglaviti u "Slušam…"
    const sat = setTimeout(() => {
      if (prepoznavanje !== r) return;
      try { r.abort(); } catch { /* već zaustavljeno */ }
      r.onend && r.onend();
    }, 15000);
    r.onend = () => {
      clearTimeout(sat);
      if (prepoznavanje !== r && !gumb.classList.contains('slusa')) return;
      r.onend = null;
      prepoznavanje = null;
      gumb.classList.remove('slusa');
      const tekst = (konacno || prijepis.textContent).trim();
      if (tekst) {
        stanje.className = 'stanje-glasa';
        dodajTekst(tekst);
        // zaslon se nakon dodavanja iscrta iznova: prikaži što je čuto i na novom elementu
        const novo = $('#stanjeGlasa');
        if (novo) { novo.className = 'stanje-glasa'; novo.textContent = `Razumio sam: „${tekst}”`; }
      } else if (!stanje.classList.contains('greska')) {
        stanje.textContent = 'Dodirni i govori';
      }
    };
    try { r.start(); } catch (e) {
      prepoznavanje = null;
      gumb.classList.remove('slusa');
      stanje.textContent = 'Glasovni unos se nije pokrenuo. Pokušaj ponovno ili upiši.';
      zabiljezi('glas', 'start nije uspio', e.message);
    }
  };
}

// ---------------------------------------------------------------- uređivanje stavke
function urediStavku(id) {
  const s = S.stavke.find((x) => x.id === id);
  if (!s) return;
  const g = s.g >= 0 ? P.grupe[s.g] : null;
  const jedinice = ['g', 'kg', 'ml', 'l', 'kom', 'pak'];
  otvoriPlocu(`
    <div class="redak"><span class="stavka-ikona">${ikonaStavke(s)}</span><div class="razmak"><h3>${esc(nazivStavke(s))}</h3><p class="sitno">${g ? `Grupa: ${esc(g.naziv)}` : 'Pretraga po nazivu'}</p></div></div>
    ${g && !s.samoTaj ? `<div><p class="sitno" style="margin-bottom:8px">Koja vrsta? (aplikacija traži najjeftiniju unutar odabranog)</p>
      <div class="cipovi"><button class="cip" data-akcija="podgrupa" data-id="${s.id}" data-pg="-1" aria-pressed="${s.pg < 0}">Sve vrste</button>
      ${g.pod.map((p, pi) => `<button class="cip" data-akcija="podgrupa" data-id="${s.id}" data-pg="${pi}" aria-pressed="${s.pg === pi}">${esc(p.naziv)}</button>`).join('')}</div></div>` : ''}
    <div><p class="sitno" style="margin-bottom:8px">Koliko?</p>
      <div class="redak"><input class="polje" id="kolicinaPolje" type="number" inputmode="decimal" min="0" step="any" value="${s.kolicina}" style="max-width:130px">
      <select class="polje" id="jedinicaPolje" style="max-width:150px">${jedinice.map((j) => `<option value="${j}" ${j === s.jedinica ? 'selected' : ''}>${j === 'pak' ? 'pakiranja' : j}</option>`).join('')}</select></div></div>
    <div><p class="sitno" style="margin-bottom:8px">Drugi naziv (npr. „kruh sa sjemenkama”, „Dukat mlijeko”)</p>
      <input class="polje" id="tekstPolje" value="${esc(s.samoTaj ? '' : s.tekst)}" placeholder="upiši naziv"></div>
    <div class="redak"><button class="gumb glavni razmak" data-akcija="spremi-stavku" data-id="${s.id}">Spremi</button>
      <button class="gumb" data-akcija="obrisi" data-id="${s.id}" aria-label="Obriši">${IKONE.brisi} Obriši</button></div>`);
}

function spremiStavku(id) {
  const s = S.stavke.find((x) => x.id === id);
  if (!s) return;
  const tekst = $('#tekstPolje').value.trim();
  const k = parseFloat(String($('#kolicinaPolje').value).replace(',', '.'));
  const j = $('#jedinicaPolje').value;
  if (tekst && norm(tekst) !== norm(s.tekst)) {
    const [nova] = rastavi(tekst);
    if (nova) Object.assign(s, { tekst: nova.tekst, g: nova.g, pg: nova.pg, upit: nova.upit, filtar: nova.filtar, proizvod: null, samoTaj: false, odbijeni: [] });
  }
  if (k > 0) { s.kolicina = Math.round(k * 1000) / 1000; s.jedinica = j; s.zadano = false; }
  zatvoriPlocu();
  promjenaPopisa();
}

// ---------------------------------------------------------------- prodavači (lanci ili poslovnice u krugu)
function poslovniceUKrugu() {
  const { lat, lon, radijus } = S.lokacija;
  const lanci = new Set(odabraniLanci());
  const out = [];
  for (const p of P.poslovnice) {
    if (!lanci.has(p[0]) || p[5] == null) continue;
    const km = udaljenost(lat, lon, p[5], p[6]);
    if (km <= radijus) out.push({ p, km });
  }
  out.sort((a, b) => a.km - b.km);
  return out;
}

async function prodavaci() {
  const lanci = odabraniLanci();
  if (!(S.lokacija.ukljucena && S.lokacija.lat != null)) {
    return { nacin: 'lanci', popis: lanci.map((id) => ({ id, lanac: id, naziv: nazivLanca(id), cijena: P.baza.lanci[id].procjena })) };
  }
  const krug = poslovniceUKrugu();
  const odabrane = krug.slice(0, NAJVISE_POSLOVNICA);
  const { datoteke, neuspjele } = await ucitajPoslovnice(S.drzava, odabrane.map((x) => x.p[7]), {
    napredak: (n, ukupno) => { const el = $('#napredakPoslovnica'); if (el) el.textContent = `Učitavam cijene trgovina u krugu: ${n} od ${ukupno}`; },
  });
  const popis = [];
  for (const { p, km } of odabrane) {
    const d = datoteke.get(p[7]);
    if (!d || !P.baza.lanci[p[0]]) continue;
    popis.push({ id: `${p[0]}:${p[1]}`, lanac: p[0], naziv: nazivLanca(p[0]), adresa: [p[2], p[3]].filter(Boolean).join(', '), km, lat: p[5], lon: p[6],
      cijena: P.baza.cijenePoslovnice(p[0], d) });
  }
  if (!popis.length && odabrane.length) {
    // nijedna trgovina u krugu se nije učitala na vrijeme (slaba veza): ne ostavljaj prazan zaslon –
    // pokaži uobičajene cijene lanaca i jasno reci zašto, uz "Pokušaj ponovno"
    return { nacin: 'lanci', popis: lanci.map((id) => ({ id, lanac: id, naziv: nazivLanca(id), cijena: P.baza.lanci[id].procjena })),
      krugNijeUcitan: odabrane.length };
  }
  return { nacin: 'poslovnice', popis, uKrugu: krug.length, odrezano: Math.max(0, krug.length - NAJVISE_POSLOVNICA), neuspjele: neuspjele.length };
}

function kljucIzracuna() {
  return JSON.stringify([S.stavke.map((s) => [s.g, s.pg, s.upit, s.filtar, s.tekst, s.kolicina, s.jedinica, s.odbijeni, s.proizvod, s.samoTaj]),
    odabraniLanci(), S.lokacija.ukljucena && [S.lokacija.lat, S.lokacija.lon, S.lokacija.radijus], P.meta.verzija]);
}

async function izracunaj() {
  const kljuc = kljucIzracuna();
  if (zadnjiIzracun && zadnjiIzracun.kljuc === kljuc) return zadnjiIzracun;
  const pr = await prodavaci();
  const a = rezultatA(P.baza, S.stavke, pr.popis);
  const b = rezultatB(P.baza, S.stavke, pr.popis);
  const c = rezultatC(b);
  zadnjiIzracun = { kljuc, pr, a, b, c };
  return zadnjiIzracun;
}

// ---------------------------------------------------------------- REZULTATI
function znakTrgovine(pr, sAdresom = true) {
  return `<span class="trgovina-znak" style="--boja:${boja(pr.lanac)}"><i></i>${esc(pr.naziv)}</span>${sAdresom && pr.adresa ? `<span>${esc(pr.adresa)}${pr.km != null ? ` · ${pr.km.toLocaleString('hr-HR', { maximumFractionDigits: 1 })} km` : ''}</span>` : ''}`;
}

// Navigacija do stvarne poslovnice (Google Karte otvaraju se u aplikaciji na mobitelu)
function gumbUputa(pr) {
  if (!pr || pr.lat == null || pr.lon == null) return '';
  const url = `https://www.google.com/maps/dir/?api=1&destination=${pr.lat},${pr.lon}&travelmode=driving`;
  return `<a class="gumb mali upute" href="${url}" target="_blank" rel="noopener">${IKONE.lokacija} Upute do trgovine</a>`;
}

function oznakaCijene(raspon, cijena) {
  const o = ocjenaCijene(raspon, cijena);
  if (!o) return '';
  return o.tip === 'najniza'
    ? '<span class="oznaka zelena" title="Prema službenom cjeniku trgovine">✓ najniža cijena u 30 dana</span>'
    : `<span class="oznaka zuta" title="Prema službenom cjeniku trgovine">u 30 dana bilo i ${eur(o.najniza30)}</span>`;
}

function redakPonude(stavka, ponuda, { prodavac, nacin, ostali = 0, prikaziTrgovinu = true } = {}) {
  const trazeno = `${nazivStavke(stavka)} · ${prikazKolicine(stavka.kolicina, stavka.jedinica)}`;
  if (!ponuda) {
    return `<div class="ponuda"><div class="ponuda-tijelo"><span class="ponuda-trazeno">${esc(trazeno)}</span>
      <p class="nema-ponude">Nema u ${prodavac ? esc(prodavac.naziv) : 'odabranim trgovinama'}${stavka.odbijeni && stavka.odbijeni.length ? ' (ili su svi preostali proizvodi odbijeni)' : ''}.</p></div>
      ${stavka.odbijeni && stavka.odbijeni.length ? `<button class="gumb mali" data-akcija="vrati-sve" data-id="${stavka.id}">Vrati odbijene</button>` : ''}</div>`;
  }
  const p = P.baza.p[ponuda.i];
  const [naziv, marka, kol, vrsta, g, pg] = p;
  const pakiranje = prikazPakiranja(kol, vrsta);
  const pr = prodavac || ponuda.prodavac;
  const raspon = nacin === 'lanci' ? P.baza.raspon(pr.lanac, ponuda.i) : null;
  const akcija = raspon && raspon.redovna > ponuda.cijena;
  const vrstaNaziv = g >= 0 && pg >= 0 ? P.grupe[g].pod[pg].naziv : g >= 0 ? P.grupe[g].naziv : '';
  return `<div class="ponuda">
    <button class="ponuda-gumb" data-akcija="zamijeni" data-id="${stavka.id}" data-i="${ponuda.i}" aria-label="Zamijeni sljedećim najjeftinijim">
      <div class="ponuda-tijelo">
        <span class="ponuda-trazeno">${esc(trazeno)}</span>
        <span class="ponuda-naziv">${esc(naziv)}</span>
        <div class="ponuda-detalji">
          ${marka ? `<span><b>${esc(marka)}</b></span>` : ''}
          ${pakiranje ? `<span class="oznaka">${esc(pakiranje)}</span>` : '<span class="oznaka zuta">količina nije objavljena</span>'}
          ${vrstaNaziv ? `<span>${esc(vrstaNaziv)}</span>` : ''}
          ${ponuda.poPakiranju && stavka.jedinica !== 'pak' && stavka.jedinica !== 'kom' ? '<span class="oznaka zuta">uspoređeno po pakiranju</span>' : ''}
          ${akcija ? '<span class="oznaka crvena">akcija</span>' : ''}
          ${akcija ? oznakaCijene(raspon, ponuda.cijena) : ''}
        </div>
        ${prikaziTrgovinu ? `<div class="ponuda-detalji" style="margin-top:5px">${znakTrgovine(pr)}${ostali ? `<span>i još ${ostali} po istoj cijeni</span>` : ''}</div>` : ''}
        ${raspon && raspon.min !== raspon.max ? `<div class="ponuda-detalji"><span>U poslovnicama ${esc(nazivLanca(pr.lanac))}: ${eur(raspon.min)} – ${eur(raspon.max)}</span></div>` : ''}
      </div>
      <div class="ponuda-cijena">
        <b>${eur(ponuda.trosak)}</b>
        ${ponuda.pakiranja > 1 ? `<span>${ponuda.pakiranja} × ${eur(ponuda.cijena)}</span>` : ''}
        ${akcija ? `<span class="precrtano">${eur(raspon.redovna * ponuda.pakiranja)}</span>` : ''}
        ${kol && vrsta ? `<span>${jedinicnaCijena(ponuda.cijena, kol, vrsta)}</span>` : ''}
      </div>
    </button>
    <button class="ikona-gumb mali" data-akcija="proizvod" data-i="${ponuda.i}" aria-label="Detalji i prijava cijene">${IKONE.info}</button>
  </div>`;
}

async function zaslonRezultati(el) {
  if (!S.stavke.length) {
    el.innerHTML = `<div class="zaslon"><div class="kartica prazno"><div class="velika">📋</div><p>Prvo složi popis za kupovinu.</p>
      <button class="gumb glavni" style="margin-top:14px" data-idi="popis">Na popis</button></div></div>`;
    return;
  }
  el.innerHTML = `<div class="zaslon"><div class="ucitavanje"><div class="vrtuljak"></div><p>Uspoređujem cijene…</p><p class="sitno" id="napredakPoslovnica"></p></div></div>`;
  let r;
  try {
    r = await izracunaj();
  } catch (e) {
    zabiljezi('izracun', e.message, e.stack);
    el.innerHTML = karticaGreske('Usporedba se nije mogla izračunati.');
    return;
  }
  if (S.zaslon !== 'rezultati') return;
  const { pr, a, b, c } = r;
  const tab = S.rezTab;
  const lanciTekst = `${odabraniLanci().length} od ${sviLanci().length} lanaca`;
  const mjesto = pr.krugNijeUcitan
    ? `Cijene trgovina u krugu ${S.lokacija.radijus} km nisu se učitale na vrijeme (slaba veza) – prikazujem uobičajene cijene lanaca za cijelu Hrvatsku`
    : pr.nacin === 'poslovnice'
    ? `U krugu ${S.lokacija.radijus} km: ${pr.popis.length} poslovnica${pr.odrezano ? ` (najbližih ${NAJVISE_POSLOVNICA} od ${pr.uKrugu})` : ''}`
    : 'Cijela Hrvatska · uobičajene cijene lanaca';
  let tijelo = '';
  if (!pr.popis.length) {
    tijelo = `<div class="kartica prazno"><div class="velika">📍</div><p>${pr.nacin === 'poslovnice' ? `U krugu od ${S.lokacija.radijus} km nema poslovnica odabranih lanaca s poznatom lokacijom.` : 'Nijedan lanac nije odabran.'}</p>
      <div class="redak" style="justify-content:center;margin-top:12px">${pr.nacin === 'poslovnice' ? '<button class="gumb mali" data-idi="karta">Povećaj krug</button>' : ''}<button class="gumb mali" data-idi="trgovine">Odaberi trgovine</button></div></div>`;
  } else if (tab === 'A') tijelo = prikazA(a, b, pr);
  else if (tab === 'B') tijelo = prikazB(b, pr);
  else tijelo = prikazC(c, b, pr);

  el.innerHTML = `<div class="zaslon">
    <div class="zakljucano">${IKONE.lokot}<span class="razmak">${S.stavke.length} ${S.stavke.length === 1 ? 'stavka' : 'stavki'} · popis zaključan</span><button class="gumb mali" data-akcija="otkljucaj">Uredi</button></div>
    <div class="segment" role="group" aria-label="Vrsta rezultata">
      <button data-akcija="tab" data-tab="A" aria-pressed="${tab === 'A'}">A · Po stavci<small>najjeftinije svugdje</small></button>
      <button data-akcija="tab" data-tab="B" aria-pressed="${tab === 'B'}">B · Jedna trgovina<small>sve na jednom mjestu</small></button>
      <button data-akcija="tab" data-tab="C" aria-pressed="${tab === 'C'}">C · Dvije trgovine<small>najbolji par</small></button>
    </div>
    <div class="redak sitno" style="flex-wrap:wrap">
      <button class="cip" data-idi="trgovine">${IKONE.trgovina} ${lanciTekst}</button>
      <button class="cip" data-akcija="lokacija">${IKONE.lokacija} ${S.lokacija.ukljucena ? `${S.lokacija.radijus} km` : 'Cijela HR'}</button>
    </div>
    <p class="sitno">${esc(mjesto)}${pr.krugNijeUcitan ? ' <button class="gumb mali" data-akcija="ponovno-poslovnice">Pokušaj ponovno</button>' : ''}${pr.neuspjele ? ` · <span class="upozorenje">${pr.neuspjele} trgovina se nije učitalo na vrijeme (slaba veza) i nisu u usporedbi</span> <button class="gumb mali" data-akcija="ponovno-poslovnice">Pokušaj ponovno</button>` : ''}</p>
    ${tijelo}
    ${pr.popis.length ? `<p class="savjet">${IKONE.zamijeni}<span>Dodirni proizvod za <b>sljedeći najjeftiniji</b> iz iste grupe. ${pr.nacin === 'lanci' ? 'Cijene su uobičajene cijene lanca (najčešća cijena u poslovnicama). Uključi lokaciju na karti za cijene stvarnih poslovnica blizu tebe.' : 'Cijene su iz cjenika svake pojedine poslovnice.'}</span></p>` : ''}
    ${oglas()}
  </div>`;
}

function gumbiKupnje(iznos, prosjek, opis) {
  const kljuc = kljucIzracuna() + S.rezTab;
  const vec = S.kupljenoKljuc === kljuc;
  return `<div class="redak" style="flex-wrap:wrap">
    <button class="gumb naglaseni razmak" data-akcija="kupljeno" data-iznos="${iznos}" data-prosjek="${prosjek}" data-opis="${esc(opis)}" ${vec ? 'disabled' : ''}>
      ${vec ? `${IKONE.kvacica} Ušteda je zabilježena` : `${IKONE.novac} Kupio/la sam – zabilježi uštedu`}</button>
    <button class="gumb" data-akcija="podijeli-rezultat">${IKONE.podijeli} Pošalji</button></div>`;
}

function prikazA(a, b, pr) {
  const ukupno = a.reduce((s, x) => s + (x.najbolja ? x.najbolja.trosak : 0), 0);
  const nedostaje = a.filter((x) => !x.najbolja).length;
  const u = procjenaUstede(b, ukupno);
  const trgovine = new Set(a.filter((x) => x.najbolja).map((x) => x.najbolja.prodavac.id));
  return `<section class="sazetak">
      <div class="oznaka-mala">Najjeftinije po stavci</div>
      <div class="iznos">${eur(ukupno)}</div>
      <div class="gdje">u ${trgovine.size} ${trgovine.size === 1 ? 'trgovini' : 'trgovina'}${nedostaje ? ` · ${nedostaje} nije pronađeno` : ''}</div>
      ${u.usteda > 0 ? `<div class="ustedi">Štediš ${eur(u.usteda)} u odnosu na prosjek trgovina</div>` : ''}
    </section>
    <section class="kartica">${a.map((x) => redakPonude(x.stavka, x.najbolja, { nacin: pr.nacin, ostali: x.najbolja ? x.najbolja.istaCijena.length - 1 : 0 })).join('')}</section>
    ${gumbiKupnje(ukupno, u.prosjek, `Najjeftinije po stavci (${trgovine.size} trgovina)`)}`;
}

function prikazB(b, pr) {
  const najbolji = b[0];
  const u = procjenaUstede(b, najbolji.ukupno);
  const otvoren = S.otvorenB && b.find((r) => r.prodavac.id === S.otvorenB) ? S.otvorenB : najbolji.prodavac.id;
  const prvi = b.slice(0, 12);
  const potpuni = b.filter((r) => r.nedostaje === 0).length;
  return `<section class="sazetak">
      <div class="oznaka-mala">${pr.nacin === 'poslovnice' ? 'Cijeli popis u jednoj poslovnici' : 'Cijeli popis u jednom lancu (procjena)'}</div>
      <div class="iznos">${eur(najbolji.ukupno)}</div>
      <div class="gdje">${esc(najbolji.prodavac.naziv)}${najbolji.prodavac.adresa ? ` · ${esc(najbolji.prodavac.adresa)}` : ''}${najbolji.nedostaje ? ` · nema ${najbolji.nedostaje} ${najbolji.nedostaje === 1 ? 'stavku' : 'stavki'}` : ''}</div>
      ${u.usteda > 0 ? `<div class="ustedi">Štediš ${eur(u.usteda)} u odnosu na prosjek · do ${eur(Math.max(0, u.najskuplje - najbolji.ukupno))} prema najskupljoj</div>` : ''}
    </section>
    ${!potpuni ? '<p class="savjet">' + IKONE.info + '<span>Nijedna trgovina nema sve stavke. Poredak: najprije one kojima nedostaje najmanje.</span></p>' : ''}
    <section class="kartica">
      ${prvi.map((r, k) => `
        <button class="trgovina-red ${k === 0 ? 'prva' : ''}" data-akcija="otvori-b" data-id="${esc(r.prodavac.id)}" aria-expanded="${r.prodavac.id === otvoren}">
          <span class="mjesto">${k + 1}</span>
          <span class="razmak"><span style="display:block">${znakTrgovine(r.prodavac, false)}</span>
            <span class="sitno">${r.prodavac.adresa ? esc(r.prodavac.adresa) + (r.prodavac.km != null ? ` · ${r.prodavac.km.toLocaleString('hr-HR', { maximumFractionDigits: 1 })} km` : '') : ''}
            ${r.nedostaje ? `<span class="razlika">nema ${r.nedostaje}</span>` : ''}</span></span>
          <span style="text-align:right"><span class="iznos">${eur(r.ukupno)}</span>${k > 0 && r.nedostaje === najbolji.nedostaje ? `<br><span class="razlika">+${eur(r.ukupno - najbolji.ukupno)}</span>` : ''}</span>
        </button>
        ${r.prodavac.id === otvoren ? `<div class="otvoreno">${gumbUputa(r.prodavac)}${S.stavke.map((s, i) => redakPonude(s, r.stavke[i], { prodavac: r.prodavac, nacin: pr.nacin, prikaziTrgovinu: false })).join('')}</div>` : ''}`).join('')}
      ${b.length > prvi.length ? `<p class="sitno" style="margin-top:8px">I još ${b.length - prvi.length} skupljih.</p>` : ''}
    </section>
    ${gumbiKupnje(najbolji.ukupno, u.prosjek, `Jedna trgovina: ${najbolji.prodavac.naziv}`)}`;
}

function prikazC(c, b, pr) {
  if (!c.length) return '<div class="kartica prazno"><p>Za kombinaciju trebaju barem dvije trgovine u kojima se nešto može kupiti.</p></div>';
  const naj = c[0];
  const jednaB = b[0];
  const u = procjenaUstede(b, naj.ukupno);
  const usporedbaB = jednaB.nedostaje === naj.nedostaje ? jednaB.ukupno - naj.ukupno : 0;
  const dio = (k) => naj.podjela.map((x, i) => (x && x.kod === k ? redakPonude(S.stavke[i], x.ponuda, { prodavac: naj.prodavaci[k], nacin: pr.nacin, prikaziTrgovinu: false }) : '')).join('');
  const zbroj = (k) => naj.podjela.reduce((s, x) => s + (x && x.kod === k ? x.ponuda.trosak : 0), 0);
  const nema = naj.podjela.map((x, i) => (x ? '' : redakPonude(S.stavke[i], null, {}))).join('');
  return `<section class="sazetak">
      <div class="oznaka-mala">Najbolja kombinacija dviju ${pr.nacin === 'poslovnice' ? 'poslovnica' : 'trgovina'}</div>
      <div class="iznos">${eur(naj.ukupno)}</div>
      <div class="gdje">${esc(naj.prodavaci[0].naziv)} + ${esc(naj.prodavaci[1].naziv)}${naj.nedostaje ? ` · nema ${naj.nedostaje}` : ''}</div>
      ${usporedbaB > 0 ? `<div class="ustedi">${eur(usporedbaB)} jeftinije nego sve u ${esc(jednaB.prodavac.naziv)}</div>` : u.usteda > 0 ? `<div class="ustedi">Štediš ${eur(u.usteda)} u odnosu na prosjek</div>` : ''}
    </section>
    ${[0, 1].map((k) => `<section class="kartica"><div class="redak"><span class="razmak">${znakTrgovine(naj.prodavaci[k], false)}<br><span class="sitno">${esc(naj.prodavaci[k].adresa || '')}</span></span><b>${eur(zbroj(k))}</b></div>${gumbUputa(naj.prodavaci[k])}${dio(k)}</section>`).join('')}
    ${nema ? `<section class="kartica">${nema}</section>` : ''}
    ${c.length > 1 ? `<section class="kartica"><h3>Druge dobre kombinacije</h3>${c.slice(1).map((x) => `<div class="trgovina-red"><span class="razmak">${esc(x.prodavaci[0].naziv)} + ${esc(x.prodavaci[1].naziv)}${x.nedostaje ? ` <span class="razlika">nema ${x.nedostaje}</span>` : ''}</span><span class="iznos">${eur(x.ukupno)}</span></div>`).join('')}</section>` : ''}
    ${gumbiKupnje(naj.ukupno, u.prosjek, `Dvije trgovine: ${naj.prodavaci[0].naziv} + ${naj.prodavaci[1].naziv}`)}`;
}

function zamijeni(id, i) {
  const s = S.stavke.find((x) => x.id === id);
  if (!s) return;
  if (s.samoTaj) { s.samoTaj = false; }
  s.odbijeni = [...(s.odbijeni || []), i];
  zadnjiIzracun = null;
  spremi();
  prikazi();
  poruka('Prikazan je sljedeći najjeftiniji.', { tekst: 'Vrati', radi: () => { s.odbijeni = s.odbijeni.filter((x) => x !== i); zadnjiIzracun = null; spremi(); prikazi(); } });
}

function tekstRezultata() {
  const r = zadnjiIzracun;
  const red = [`🛒 Najjeftinija košarica – ${new Date().toLocaleDateString('hr-HR')}`];
  if (!r || !r.pr.popis.length) {
    red.push(...S.stavke.map((s) => `• ${nazivStavke(s)} – ${prikazKolicine(s.kolicina, s.jedinica)}`));
    return red.join('\n');
  }
  const opisP = (s, p) => {
    if (!p) return `• ${nazivStavke(s)} – nema`;
    const x = P.baza.p[p.i];
    return `• ${x[0]}${x[1] ? ` (${x[1]})` : ''}${x[2] ? `, ${prikazPakiranja(x[2], x[3])}` : ''}${p.pakiranja > 1 ? ` × ${p.pakiranja}` : ''} – ${eur(p.trosak)}`;
  };
  if (S.rezTab === 'A') {
    const ukupno = r.a.reduce((s, x) => s + (x.najbolja ? x.najbolja.trosak : 0), 0);
    red.push(`Najjeftinije po stavci: ${eur(ukupno)}`);
    r.a.forEach((x) => red.push(`${opisP(x.stavka, x.najbolja)}${x.najbolja ? ` @ ${x.najbolja.prodavac.naziv}` : ''}`));
  } else if (S.rezTab === 'C' && r.c.length) {
    const c = r.c[0];
    red.push(`Dvije trgovine: ${c.prodavaci[0].naziv} + ${c.prodavaci[1].naziv} = ${eur(c.ukupno)}`);
    for (const k of [0, 1]) {
      red.push(`— ${c.prodavaci[k].naziv}${c.prodavaci[k].adresa ? `, ${c.prodavaci[k].adresa}` : ''}`);
      c.podjela.forEach((x, i) => { if (x && x.kod === k) red.push(opisP(S.stavke[i], x.ponuda)); });
    }
  } else {
    const b = r.b[0];
    red.push(`Sve u jednoj trgovini: ${b.prodavac.naziv}${b.prodavac.adresa ? `, ${b.prodavac.adresa}` : ''} = ${eur(b.ukupno)}`);
    S.stavke.forEach((s, i) => red.push(opisP(s, b.stavke[i])));
  }
  red.push('', `Cijene od ${datumHR(P.meta.datum)}. Aplikacija: ${location.origin}${location.pathname}`);
  return red.join('\n');
}

function ponudiDijeljenje(tekst, naslov = 'Pošalji') {
  const t = encodeURIComponent(tekst);
  otvoriPlocu(`<h3>${esc(naslov)}</h3>
    <div class="izbor" style="grid-template-columns:1fr 1fr">
      <a class="gumb" href="https://wa.me/?text=${t}" target="_blank" rel="noopener">WhatsApp</a>
      <a class="gumb" href="viber://forward?text=${t}">Viber</a>
      <a class="gumb" href="sms:?&body=${t}">SMS</a>
      <button class="gumb" data-akcija="kopiraj-tekst">${IKONE.kopiraj} Kopiraj</button>
    </div>
    ${navigator.share ? `<button class="gumb glavni puni" data-akcija="dijeli-sustav">${IKONE.podijeli} Više mogućnosti…</button>` : ''}
    <textarea class="izvjesce" readonly style="min-height:140px">${esc(tekst)}</textarea>`, (ploca) => {
    const kop = ploca.querySelector('[data-akcija="kopiraj-tekst"]');
    if (kop) kop.onclick = () => kopiraj(tekst);
    const sus = ploca.querySelector('[data-akcija="dijeli-sustav"]');
    if (sus) sus.onclick = () => navigator.share({ title: 'Najjeftinija košarica', text: tekst }).catch(() => {});
  });
}

// ---------------------------------------------------------------- proizvod: sve cijene i prijava
function kljucFavorita(i) {
  const p = P.baza.p[i];
  return p[6] || `${p[0]}|${p[1]}`;
}
function indeksFavorita(k) {
  if (P.baza.poBarkodu.has(k)) return P.baza.poBarkodu.get(k);
  if (!indeksFavorita.mapa) indeksFavorita.mapa = new Map(P.baza.p.map((p, i) => [`${p[0]}|${p[1]}`, i]));
  return indeksFavorita.mapa.get(k);
}
function jeFavorit(i) { return (S.favoriti || []).includes(kljucFavorita(i)); }
// najniža uobičajena cijena među odabranim lancima
function najjeftinijeKod(i) {
  let naj = null;
  for (const id of odabraniLanci()) {
    const c = P.baza.lanci[id] && P.baza.lanci[id].cijena[i];
    if (c && P.baza.prihvatljiva(i, c) && (!naj || c < naj.c)) naj = { c, lanac: id, raspon: P.baza.raspon(id, i) };
  }
  return naj;
}

function prikaziProizvod(i, izSkenera = false) {
  const p = P.baza.p[i];
  const [naziv, marka, kol, vrsta, g, pg, barkod] = p;
  const sviRedovi = Object.keys(P.baza.lanci).map((id) => ({ id, c: P.baza.lanci[id].cijena[i], raspon: P.baza.raspon(id, i) })).filter((x) => x.c);
  const redovi = sviRedovi.filter((x) => P.baza.prihvatljiva(i, x.c)).sort((a, b) => a.c - b.c);
  const izostavljeno = sviRedovi.length - redovi.length;
  const blizu = zadnjiIzracun && zadnjiIzracun.pr.nacin === 'poslovnice'
    ? zadnjiIzracun.pr.popis.filter((x) => P.baza.prihvatljiva(i, x.cijena[i])).map((x) => ({ x, c: x.cijena[i] })).sort((a, b) => a.c - b.c).slice(0, 6) : [];
  otvoriPlocu(`
    <div class="redak"><div class="razmak"><h3>${esc(naziv)}</h3></div>
      <button class="gumb mali zvjezdica ${jeFavorit(i) ? 'aktivna' : ''}" data-akcija="favorit" data-i="${i}" aria-pressed="${jeFavorit(i)}">${jeFavorit(i) ? '★ U favoritima' : '☆ Prati cijenu'}</button></div>
    <div><p class="sitno">${[marka, prikazPakiranja(kol, vrsta), g >= 0 ? P.grupe[g].naziv + (pg >= 0 ? ' · ' + P.grupe[g].pod[pg].naziv : '') : '', barkod ? 'barkod ' + barkod : ''].filter(Boolean).map(esc).join(' · ')}</p></div>
    <table class="tablica"><thead><tr><th>Lanac</th><th class="broj">Uobičajeno</th><th class="broj">Raspon</th></tr></thead><tbody>
      ${redovi.map((x) => `<tr><td>${znakTrgovine({ lanac: x.id, naziv: nazivLanca(x.id) }, false)}${x.raspon.redovna > x.c ? ' <span class="oznaka crvena">akcija</span>' : ''}</td>
        <td class="broj"><b>${eur(x.c)}</b>${kol && vrsta ? `<br><span class="sitno">${jedinicnaCijena(x.c, kol, vrsta)}</span>` : ''}${x.raspon.najniza30 ? `<br><span class="sitno">najniža u 30 d: ${eur(x.raspon.najniza30)}</span>` : ''}${x.raspon.sidrena ? `<br><span class="sitno">sidrena: ${eur(x.raspon.sidrena)}</span>` : ''}</td>
        <td class="broj sitno">${x.raspon.min !== x.raspon.max ? `${eur(x.raspon.min)}–${eur(x.raspon.max)}` : '–'}<br>${x.raspon.poslovnica} posl.</td></tr>`).join('')}
    </tbody></table>
    ${izostavljeno ? `<p class="sitno">${izostavljeno} ${izostavljeno === 1 ? 'cijena nije prikazana jer je' : 'cijene nisu prikazane jer su'} neobično niske (vjerojatno greška u cjeniku trgovine).</p>` : ''}
    ${blizu.length ? `<div><h3>Blizu tebe</h3>${blizu.map(({ x, c }) => `<div class="trgovina-red"><span class="razmak">${znakTrgovine(x)}</span><b>${eur(c)}</b></div>`).join('')}</div>` : ''}
    <div class="redak" style="flex-wrap:wrap">
      ${izSkenera ? `<button class="gumb glavni razmak" data-akcija="dodaj-proizvod" data-i="${i}">${IKONE.plus} Dodaj na popis</button>` : ''}
      <button class="gumb razmak" data-akcija="prijavi" data-i="${i}">${IKONE.zastava} Prijavi pogrešnu cijenu</button>
    </div>
    <p class="sitno">„Najniža u 30 d” i „sidrena” (cijena na dan 2.5.2025.) objavljuju trgovine po Odluci NN 75/2025 – tako vidiš je li akcija stvarna.</p>
    <p class="sitno">Cijene su iz službenih dnevnih cjenika trgovina od ${datumHR(P.meta.datum)}. U trgovini može biti drukčije ako je cjenik u međuvremenu promijenjen.</p>`);
}

function prijaviCijenu(i) {
  const p = P.baza.p[i];
  otvoriPlocu(`<h3>Prijavi pogrešnu cijenu</h3>
    <p class="sitno">${esc(p[0])}${p[1] ? ' · ' + esc(p[1]) : ''}</p>
    <label class="sitno" for="prijavaTrgovina">Trgovina</label>
    <select class="polje" id="prijavaTrgovina">${Object.keys(P.baza.lanci).filter((id) => P.baza.lanci[id].cijena[i]).map((id) => `<option value="${id}">${esc(nazivLanca(id))} – ${eur(P.baza.lanci[id].cijena[i])}</option>`).join('')}</select>
    <label class="sitno" for="prijavaRazlog">Što nije u redu?</label>
    <select class="polje" id="prijavaRazlog">
      <option>Cijena u trgovini je drukčija</option><option>Pogrešna količina ili pakiranje</option><option>Pogrešan proizvod ili grupa</option><option>Proizvoda nema u trgovini</option><option>Nešto drugo</option></select>
    <input class="polje" id="prijavaCijena" inputmode="decimal" placeholder="Cijena koju si vidio/la (npr. 1,99) – nije obavezno">
    <button class="gumb glavni puni" data-akcija="posalji-prijavu" data-i="${i}">Pošalji prijavu</button>
    <p class="sitno">Prijava se otvara kao prijedlog na GitHubu (treba besplatni račun). Bez računa: dodirni „Kopiraj” i pošalji tekst vlasniku aplikacije.</p>
    <button class="gumb puni" data-akcija="kopiraj-prijavu" data-i="${i}">${IKONE.kopiraj} Kopiraj prijavu</button>`);
}

function tekstPrijave(i) {
  const p = P.baza.p[i];
  const lanac = $('#prijavaTrgovina').value;
  return [`Proizvod: ${p[0]}${p[1] ? ` (${p[1]})` : ''}`, `Barkod: ${p[6] || '-'}`, `Količina u aplikaciji: ${prikazPakiranja(p[2], p[3]) || 'nije objavljena'}`,
    `Trgovina: ${nazivLanca(lanac)}`, `Cijena u aplikaciji: ${eur(P.baza.lanci[lanac].cijena[i])}`, `Problem: ${$('#prijavaRazlog').value}`,
    `Viđena cijena: ${$('#prijavaCijena').value || '-'}`, `Datum cjenika: ${P.meta.datum}`, `Verzija podataka: ${P.meta.verzija}`].join('\n');
}

// ---------------------------------------------------------------- AKCIJE
let filterAkcija = { grupa: -1, upit: '', prave: false };
function favoritiNaAkciji() {
  const na = [];
  for (const k of S.favoriti || []) {
    const i = indeksFavorita(k);
    if (i == null) continue;
    const n = najjeftinijeKod(i);
    if (n && n.raspon && n.raspon.redovna > n.c) na.push({ i, ...n });
  }
  if (!na.length) return (S.favoriti || []).length ? '<p class="sitno">★ Nijedan tvoj favorit danas nije na akciji.</p>' : '';
  return `<section class="kartica favoriti-akcija"><h3>★ Tvoji favoriti na akciji</h3>${na.map((x) => {
    const p = P.baza.p[x.i];
    return `<button class="akcija" data-akcija="proizvod" data-i="${x.i}"><span class="popust">−${Math.round((1 - x.c / x.raspon.redovna) * 100)}%</span>
      <span class="razmak"><b style="display:block">${esc(p[0])}</b>${znakTrgovine({ lanac: x.lanac, naziv: nazivLanca(x.lanac) }, false)}</span>
      <span class="ponuda-cijena"><b>${eur(x.c)}</b><span class="precrtano">${eur(x.raspon.redovna)}</span></span></button>`;
  }).join('')}</section>`;
}

function zaslonFavoriti(el) {
  const fav = (S.favoriti || []).map((k) => ({ k, i: indeksFavorita(k) }));
  el.innerHTML = `<div class="zaslon">${natrag()}
    <div class="naslov-zaslona"><div><h2>★ Moji favoriti</h2><p>Proizvodi kojima pratiš cijenu. Kad su na akciji, pokazuju se na vrhu zaslona Akcije.</p></div></div>
    <section class="kartica">${fav.length ? fav.map(({ k, i }) => {
      if (i == null) return `<div class="trgovina-red"><span class="razmak">${esc(k.split('|')[0])}<br><span class="sitno">danas nije u cjenicima</span></span><button class="gumb mali" data-akcija="favorit-makni" data-k="${esc(k)}">Makni</button></div>`;
      const p = P.baza.p[i]; const n = najjeftinijeKod(i);
      const akc = n && n.raspon && n.raspon.redovna > n.c;
      return `<button class="akcija" data-akcija="proizvod" data-i="${i}"><span class="razmak"><b style="display:block">${esc(p[0])}</b>
        <span class="sitno">${esc([p[1], prikazPakiranja(p[2], p[3])].filter(Boolean).join(' · '))}</span><br>${n ? znakTrgovine({ lanac: n.lanac, naziv: nazivLanca(n.lanac) }, false) : '<span class="sitno">nema u odabranim trgovinama</span>'}</span>
        <span class="ponuda-cijena">${n ? `<b>${eur(n.c)}</b>${akc ? `<span class="precrtano">${eur(n.raspon.redovna)}</span><span class="oznaka crvena">akcija</span>` : ''}` : ''}</span></button>`;
    }).join('') : '<div class="prazno"><div class="velika">☆</div><p>Još nemaš favorita. Otvori bilo koji proizvod (ⓘ u rezultatima, akcijama ili skeneru) i dodirni „☆ Prati cijenu”.</p></div>'}</section>
  </div>`;
}

function zaslonAkcije(el) {
  const sve = akcije(P.baza, odabraniLanci(), filterAkcija);
  // "Samo prave akcije": cijena je najniža u zadnjih 30 dana (ako lanac to objavljuje)
  const lista = filterAkcija.prave ? sve.filter((x) => { const o = ocjenaCijene(P.baza.raspon(x.lanac, x.i), x.cijena); return o && o.tip === 'najniza'; }) : sve;
  const grupeSAkcijom = [...new Set(akcije(P.baza, odabraniLanci(), { najvise: 5000 }).map((x) => P.baza.p[x.i][4]).filter((g) => g >= 0))];
  el.innerHTML = `<div class="zaslon">
    <div class="naslov-zaslona"><div><h2>Akcije ovog tjedna</h2><p>Proizvodi kojima je cijena niža od redovne u većini poslovnica lanca.</p></div></div>
    <div class="redak"><input class="polje" id="akcijeUpit" placeholder="Traži akciju (npr. kava)" value="${esc(filterAkcija.upit)}">
      <select class="polje" id="akcijeGrupa" style="max-width:44%"><option value="-1">Sve grupe</option>${grupeSAkcijom.sort((a, b) => P.grupe[a].naziv.localeCompare(P.grupe[b].naziv, 'hr')).map((g) => `<option value="${g}" ${g === filterAkcija.grupa ? 'selected' : ''}>${esc(P.grupe[g].naziv)}</option>`).join('')}</select></div>
    <label class="kvacica" style="margin-top:2px"><input type="checkbox" id="praveAkcije" ${filterAkcija.prave ? 'checked' : ''}><span class="razmak"><b>Samo prave akcije</b><br><span class="sitno">cijena je najniža u zadnjih 30 dana (podatak iz službenog cjenika)</span></span></label>
    ${favoritiNaAkciji()}
    ${oglas()}
    <section class="kartica">${lista.length ? lista.slice(0, 150).map((x) => {
      const p = P.baza.p[x.i];
      return `<button class="akcija" data-akcija="proizvod" data-i="${x.i}">
        <span class="popust">−${Math.round(x.popust * 100)}%</span>
        <span class="razmak"><b style="display:block">${esc(p[0])}</b><span class="sitno">${esc([p[1], prikazPakiranja(p[2], p[3])].filter(Boolean).join(' · '))}</span><br>${znakTrgovine({ lanac: x.lanac, naziv: nazivLanca(x.lanac) }, false)} ${oznakaCijene(P.baza.raspon(x.lanac, x.i), x.cijena)}</span>
        <span class="ponuda-cijena"><b>${eur(x.cijena)}</b><span class="precrtano">${eur(x.redovna)}</span></span></button>`;
    }).join('') : '<div class="prazno"><p>Nema akcija za odabrani filtar.</p></div>'}</section>
    ${lista.length > 150 ? '<p class="sitno">Prikazano je 150 najvećih popusta. Suzi pretragu za više.</p>' : ''}
  </div>`;
  let sat;
  $('#akcijeUpit').oninput = (e) => { clearTimeout(sat); sat = setTimeout(() => { filterAkcija.upit = e.target.value; prikazi(); const u = $('#akcijeUpit'); u.focus(); u.setSelectionRange(u.value.length, u.value.length); }, 350); };
  $('#akcijeGrupa').onchange = (e) => { filterAkcija.grupa = Number(e.target.value); prikazi(); };
  $('#praveAkcije').onchange = (e) => { filterAkcija.prave = e.target.checked; prikazi(); };
}

// ---------------------------------------------------------------- KARTA
async function zaslonKarta(el) {
  const L0 = S.lokacija;
  const sKoord = P.poslovnice.filter((p) => p[5] != null && odabraniLanci().includes(p[0]));
  const krug = L0.ukljucena && L0.lat != null ? poslovniceUKrugu() : [];
  el.innerHTML = `<div class="zaslon">
    <div class="naslov-zaslona"><div><h2>Trgovine na karti</h2><p>${sKoord.length} poslovnica s poznatom lokacijom${L0.ukljucena && L0.lat != null ? ` · ${krug.length} u krugu ${L0.radijus} km` : ''}</p></div></div>
    <div class="kartica ravna">
      <div class="redak" style="flex-wrap:wrap">
        <button class="gumb ${L0.ukljucena ? '' : 'glavni'} mali" data-akcija="moja-lokacija">${IKONE.lokacija} ${L0.lat != null ? 'Osvježi moju lokaciju' : 'Koristi moju lokaciju'}</button>
        ${L0.ukljucena ? '<button class="gumb mali" data-akcija="iskljuci-lokaciju">Isključi (cijela HR)</button>' : ''}
      </div>
      <div class="cipovi" style="margin-top:10px" role="group" aria-label="Polumjer">${RADIJUSI.map((r) => `<button class="cip" data-akcija="radijus" data-r="${r}" aria-pressed="${L0.ukljucena && L0.radijus === r}">${r} km</button>`).join('')}</div>
      <p class="sitno" style="margin-top:8px">${L0.ukljucena ? `Rezultati koriste stvarne cijene poslovnica u krugu ${L0.radijus} km od ${L0.izvor === 'karta' ? 'odabrane točke' : 'tvoje lokacije'}.` : 'Lokacija je isključena: rezultati koriste uobičajene cijene lanaca za cijelu Hrvatsku.'} Možeš i dodirnuti kartu da odabereš točku.</p>
    </div>
    <div id="karta" class="karta" aria-label="Karta poslovnica"></div>
    ${krug.length ? `<section class="kartica"><h3>Najbliže</h3>${krug.slice(0, 12).map(({ p, km }) => `<div class="trgovina-red"><span class="razmak">${znakTrgovine({ lanac: p[0], naziv: nazivLanca(p[0]), adresa: [p[2], p[3]].filter(Boolean).join(', '), km })}</span></div>`).join('')}</section>` : ''}
  </div>`;
  try {
    const { nacrtajKartu } = await import('./karta.js');
    if (S.zaslon !== 'karta') return;
    karta = await nacrtajKartu($('#karta'), {
      poslovnice: sKoord, lokacija: L0, boja, naziv: nazivLanca,
      odaberi: (lat, lon) => { S.lokacija = { ...S.lokacija, ukljucena: true, lat, lon, izvor: 'karta' }; zadnjiIzracun = null; spremi(); prikazi(); },
    });
  } catch (e) {
    zabiljezi('karta', e.message, e.stack);
    const k = $('#karta');
    if (k) k.innerHTML = '<div class="prazno"><p>Karta se ne može prikazati (možda nema interneta). Lokacija i krug i dalje rade.</p></div>';
  }
}

// ---------------------------------------------------------------- LOKACIJA (jedan gumb na glavnom zaslonu)
// Dodir -> odmah traži lokaciju i otvara izbor kruga 2/5/10/20 km -> odabir kruga -> natrag na popis.
// Karta i rezultati koriste iste poslovnice u krugu. Lokacija nije obavezna ("Bez lokacije").
let lokStanje = { traziSe: false, greska: '' };
let lokSat = null;

function krugoviPoBroju() {
  const { lat, lon } = S.lokacija;
  const lanci = new Set(odabraniLanci());
  const broj = Object.fromEntries(RADIJUSI.map((r) => [r, 0]));
  if (lat == null) return broj;
  for (const p of P.poslovnice) {
    if (!lanci.has(p[0]) || p[5] == null) continue;
    const km = udaljenost(lat, lon, p[5], p[6]);
    for (const r of RADIJUSI) if (km <= r) broj[r]++;
  }
  return broj;
}

function gumbLokacije() {
  const L0 = S.lokacija;
  const ukljucena = L0.ukljucena && L0.lat != null;
  const n = ukljucena ? poslovniceUKrugu().length : 0;
  return `<button class="lokacija-gumb ${ukljucena ? 'aktivna' : ''}" data-akcija="lokacija" aria-label="Lokacija i krug trgovina">
    <span class="lok-ikona">${IKONE.lokacija}</span>
    <span class="razmak"><b>${ukljucena ? `U krugu ${L0.radijus} km · ${n} ${n === 1 ? 'trgovina' : n >= 2 && n <= 4 ? 'trgovine' : 'trgovina'}` : 'Trgovine u blizini'}</b>
    <span class="sitno">${ukljucena ? (L0.izvor === 'karta' ? 'oko odabrane točke na karti' : 'oko tvoje lokacije') + ' · dodirni za promjenu' : 'Cijela Hrvatska · dodirni za lokaciju'}</span></span>
  </button>`;
}

function htmlLokacije() {
  const L0 = S.lokacija;
  const broj = krugoviPoBroju();
  const stanje = lokStanje.traziSe
    ? '<p class="lok-stanje"><span class="vrtuljak malo"></span> Tražim tvoju lokaciju…</p>'
    : lokStanje.greska
      ? `<p class="lok-stanje upozorenje">${esc(lokStanje.greska)}</p><button class="gumb mali" data-akcija="lok-trazi">Pokušaj ponovno</button>`
      : L0.lat != null ? `<p class="lok-stanje">${L0.izvor === 'karta' ? 'Odabrana točka na karti.' : 'Lokacija pronađena.'} Odaberi krug:</p>` : '';
  const mozeOdabrati = L0.lat != null && !lokStanje.traziSe;
  return `<div class="lok-ploca"><h3>${IKONE.lokacija} Trgovine u blizini</h3>
    ${stanje}
    <div class="lok-krugovi" role="group" aria-label="Krug">${RADIJUSI.map((r) => `<button class="lok-krug" data-akcija="lok-r" data-r="${r}" ${mozeOdabrati ? '' : 'disabled'} aria-pressed="${L0.ukljucena && L0.radijus === r}">
      <b>${r} km</b><span>${mozeOdabrati ? `${broj[r]} ${broj[r] === 1 ? 'trgovina' : broj[r] >= 2 && broj[r] <= 4 ? 'trgovine' : 'trgovina'}` : '…'}</span></button>`).join('')}</div>
    <div class="redak" style="margin-top:12px;flex-wrap:wrap">
      <button class="gumb mali" data-akcija="lok-iskljuci">Bez lokacije (cijela Hrvatska)</button>
      ${L0.lat != null ? '<button class="gumb mali" data-akcija="lok-karta">Pogledaj na karti</button>' : ''}
    </div>
    <p class="sitno" style="margin-top:10px">Lokacija nije obavezna. Koristi se samo u ovom pregledniku za izbor najbližih trgovina.</p></div>`;
}

function osvjeziPlocuLokacije() {
  const sadrzaj = $('#ploca .ploca-sadrzaj');
  if (!$('#ploca').hidden && sadrzaj && sadrzaj.querySelector('.lok-ploca')) sadrzaj.innerHTML = htmlLokacije();
}

function traziLokaciju() {
  clearTimeout(lokSat);
  if (!navigator.geolocation) { lokStanje = { traziSe: false, greska: 'Ovaj uređaj ne podržava lokaciju. Možeš odabrati točku na karti.' }; osvjeziPlocuLokacije(); return; }
  lokStanje = { traziSe: true, greska: '' };
  osvjeziPlocuLokacije();
  let gotovo = false;
  const zavrsi = (greska, pos) => {
    if (gotovo) return;
    gotovo = true;
    clearTimeout(lokSat);
    if (pos) {
      S.lokacija = { ...S.lokacija, lat: pos.coords.latitude, lon: pos.coords.longitude, izvor: 'gps' };
      spremi();
    }
    lokStanje = { traziSe: false, greska };
    osvjeziPlocuLokacije();
    if (!$('#ploca').hidden) return;
    prikazi();
  };
  // vlastiti sat: neki preglednici nikad ne pozovu ni uspjeh ni grešku (npr. zatvoren upit za dopuštenje)
  lokSat = setTimeout(() => zavrsi('Traženje lokacije je predugo trajalo. Provjeri je li lokacija uključena na mobitelu.'), 20000);
  navigator.geolocation.getCurrentPosition((pos) => zavrsi('', pos), (e) => {
    const p = { 1: 'Lokacija nije dopuštena. U Chromeu: lokot pokraj adrese → Dopuštenja → Lokacija → Dopusti.', 2: 'Lokacija trenutno nije dostupna. Uključi lokaciju na mobitelu.', 3: 'Traženje lokacije je predugo trajalo.' };
    zavrsi(p[e.code] || 'Lokacija nije dostupna.');
  }, { enableHighAccuracy: false, timeout: 15000, maximumAge: 300000 });
}

function otvoriLokaciju() {
  lokStanje = { traziSe: false, greska: '' };
  otvoriPlocu(htmlLokacije());
  traziLokaciju();          // jedan dodir = traži lokaciju
}

function postaviKrug(r) {
  S.lokacija = { ...S.lokacija, radijus: r, ukljucena: true };
  zadnjiIzracun = null;
  spremi();
  zatvoriPlocu();
  const krug = poslovniceUKrugu();
  pripremiPoslovnice(S.drzava, krug.slice(0, NAJVISE_POSLOVNICA).map((x) => x.p[7]));   // rezultati odmah spremni
  if (S.zaslon !== 'rezultati') S.zaslon = 'popis';                                         // natrag na popis
  prikazi();
  poruka(krug.length ? `Koristim ${krug.length} ${krug.length === 1 ? 'trgovinu' : krug.length <= 4 ? 'trgovine' : 'trgovina'} u krugu ${r} km.` : `U krugu ${r} km nema trgovina s poznatom lokacijom – odaberi veći krug.`);
}

function iskljuciLokaciju() {
  S.lokacija = { ...S.lokacija, ukljucena: false };
  zadnjiIzracun = null;
  spremi();
  zatvoriPlocu();
  prikazi();
  poruka('Lokacija isključena: uspoređujem cijene za cijelu Hrvatsku.');
}

// ---------------------------------------------------------------- VIŠE i podzasloni
function zaslonVise(el) {
  const st = P.meta.lanci.filter((l) => l.status !== 'ok').length;
  const kartice = [
    ['usteda', IKONE.novac, 'Moja ušteda', `${eur(Math.round(S.usteda.ukupno))} ukupno`],
    ['favoriti', '<span style="font-size:1.4rem;line-height:1">★</span>', 'Moji favoriti', `${(S.favoriti || []).length} proizvoda · obavijest o akciji`],
    ['obitelj', IKONE.obitelj, 'Obiteljski popis', 'Podijeli popis s ukućanima'],
    ['skener', IKONE.barkod, 'Skeniraj barkod', 'Provjeri cijenu u trgovini'],
    ['status', IKONE.status, 'Status podataka', `Cijene od ${datumHR(P.meta.datum)}${st ? ` · ${st} upozorenja` : ''}`],
    ['trgovine', IKONE.trgovina, 'Moje trgovine', `${odabraniLanci().length} od ${sviLanci().length} lanaca`],
    ['postavke', IKONE.postavke, 'Postavke', 'Država, Premium, izgled'],
    ['greska', IKONE.greska, 'Prijavi grešku', 'Izvješće za popravak'],
    ['o', IKONE.srce, 'O aplikaciji', 'Poštene usporedbe'],
  ];
  el.innerHTML = `<div class="zaslon">
    <div class="velika-usteda" data-idi="usteda" role="button"><div class="sitno" style="color:inherit;opacity:.75;font-weight:700;text-transform:uppercase;letter-spacing:.06em">Ukupno ušteđeno</div><div class="iznos">${eur(Math.round(S.usteda.ukupno))}</div><div>${S.usteda.kupnje.length} ${S.usteda.kupnje.length === 1 ? 'kupnja' : 'kupnji'} zabilježeno</div></div>
    ${instalacija ? `<button class="gumb glavni puni" data-akcija="instaliraj">${IKONE.plus} Instaliraj aplikaciju na mobitel</button>` : ''}
    <div class="izbor">${kartice.map(([id, ik, n, o]) => `<button data-idi="${id}"><span class="ik">${ik}</span><b>${esc(n)}</b><span>${esc(o)}</span></button>`).join('')}</div>
    <p class="sitno" style="text-align:center;margin-top:14px">Verzija aplikacije ${VERZIJA_APLIKACIJE} · podaci ${esc(P.meta.verzija)} (${datumHR(P.meta.datum)})</p>
  </div>`;
}

const natrag = (kamo = 'vise') => `<button class="natrag" data-idi="${kamo}">${IKONE.natrag} Natrag</button>`;

function zaslonUsteda(el) {
  const k = [...S.usteda.kupnje].reverse();
  const mjesec = new Date().toISOString().slice(0, 7);
  const ovajMjesec = S.usteda.kupnje.filter((x) => x.datum.startsWith(mjesec)).reduce((s, x) => s + x.usteda, 0);
  el.innerHTML = `<div class="zaslon">${natrag()}
    <div class="velika-usteda"><div class="sitno" style="color:inherit;opacity:.75;font-weight:700;text-transform:uppercase;letter-spacing:.06em">Ukupno ušteđeno</div>
      <div class="iznos">${eur(Math.round(S.usteda.ukupno))}</div><div>Ovaj mjesec: <b>${eur(Math.round(ovajMjesec))}</b></div></div>
    <p class="savjet">${IKONE.info}<span>Ušteda = koliko bi isti popis prosječno koštao u trgovinama koje imaju sve stavke, minus koliko je koštao kod tebe. Bilježi se kad nakon usporedbe dodirneš „Kupio/la sam”.</span></p>
    <section class="kartica"><h3>Kupnje</h3>${k.length ? `<table class="tablica"><tbody>${k.slice(0, 50).map((x) => `<tr><td>${datumHR(x.datum)}<br><span class="sitno">${esc(x.opis)}</span></td><td class="broj">${eur(x.iznos)}<br><span class="sitno" style="color:var(--uspjeh)">−${eur(x.usteda)}</span></td></tr>`).join('')}</tbody></table>` : '<p class="prigusen" style="margin-top:6px">Još nema zabilježenih kupnji.</p>'}</section>
    ${k.length ? '<button class="gumb puni" data-akcija="ponisti-ustedu">Obriši povijest uštede</button>' : ''}
  </div>`;
}

function kodPopisa() {
  const min = S.stavke.map((s) => ({ t: s.tekst, g: s.g >= 0 ? P.grupe[s.g].id : '', p: s.g >= 0 && s.pg >= 0 ? P.grupe[s.g].pod[s.pg].id : '', k: s.kolicina, j: s.jedinica, b: s.samoTaj && s.proizvod != null ? P.baza.p[s.proizvod][6] : '' }));
  const json = JSON.stringify({ v: 1, s: min });
  return btoa(unescape(encodeURIComponent(json))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
function procitajKod(kod) {
  const json = decodeURIComponent(escape(atob(kod.replace(/-/g, '+').replace(/_/g, '/'))));
  const d = JSON.parse(json);
  return (d.s || []).slice(0, 100).map((x) => {
    const gi = x.g ? P.grupe.findIndex((g) => g.id === x.g) : -1;
    const pg = gi >= 0 && x.p ? P.grupe[gi].pod.findIndex((p) => p.id === x.p) : -1;
    const pr = x.b ? P.baza.poBarkodu.get(x.b) : undefined;
    return { id: novaStavkaId(), tekst: String(x.t || '').slice(0, 80), g: gi, pg, upit: gi >= 0 ? '' : String(x.t || ''), kolicina: Number(x.k) > 0 ? Number(x.k) : 1,
      jedinica: ['g', 'kg', 'ml', 'l', 'kom', 'pak'].includes(x.j) ? x.j : 'pak', zadano: false, proizvod: pr ?? null, samoTaj: pr != null };
  });
}

function zaslonObitelj(el) {
  el.innerHTML = `<div class="zaslon">${natrag()}
    <div class="naslov-zaslona"><div><h2>Obiteljski popis</h2><p>Pošalji popis ukućanima. Kad otvore poveznicu, popis im se doda u aplikaciju.</p></div></div>
    <section class="kartica">
      ${S.stavke.length ? `<p>${S.stavke.length} stavki: ${esc(S.stavke.slice(0, 6).map(nazivStavke).join(', '))}${S.stavke.length > 6 ? '…' : ''}</p>
        <button class="gumb glavni puni" style="margin-top:12px" data-akcija="podijeli-popis">${IKONE.podijeli} Pošalji popis obitelji</button>` : '<p class="prigusen">Popis je prazan. Najprije dodaj stavke.</p>'}
    </section>
    <section class="kartica ravna"><h3>Primio/la sam popis</h3><p class="sitno" style="margin:6px 0 10px">Ako poveznica nije otvorila aplikaciju, zalijepi je ovdje:</p>
      <div class="redak"><input class="polje" id="kodPolje" placeholder="zalijepi poveznicu"><button class="gumb" data-akcija="uvezi-kod">Dodaj</button></div></section>
    <p class="savjet">${IKONE.info}<span>Zajednički popis koji se sam usklađuje na svim mobitelima u stvarnom vremenu bit će dio Premiuma.</span></p>
  </div>`;
}

function uveziPopis(kod) {
  try {
    const nove = procitajKod(kod);
    osvjeziStavke(nove);
    if (!nove.length) throw new Error('prazno');
    otvoriPlocu(`<h3>Primljen popis (${nove.length})</h3><p class="sitno">${esc(nove.map((s) => s.tekst || (s.proizvod != null ? P.baza.p[s.proizvod][0] : '')).join(', '))}</p>
      <button class="gumb glavni puni" data-akcija="uvoz-dodaj">Dodaj na moj popis</button><button class="gumb puni" data-akcija="uvoz-zamijeni">Zamijeni moj popis</button>`, (pl) => {
      pl.querySelector('[data-akcija="uvoz-dodaj"]').onclick = () => { S.stavke.push(...nove); S.zakljucano = false; zatvoriPlocu(); idi('popis'); promjenaPopisa(); };
      pl.querySelector('[data-akcija="uvoz-zamijeni"]').onclick = () => { S.stavke = nove; S.zakljucano = false; zatvoriPlocu(); idi('popis'); promjenaPopisa(); };
    });
  } catch (e) {
    zabiljezi('uvoz-popisa', e.message);
    poruka('Poveznica popisa nije ispravna.');
  }
}

let skenerTok = null;
function zaustaviSkener() { if (skenerTok) { skenerTok.getTracks().forEach((t) => t.stop()); skenerTok = null; } }
function zaslonSkener(el) {
  const podrzano = 'BarcodeDetector' in window && navigator.mediaDevices;
  el.innerHTML = `<div class="zaslon">${natrag()}
    <div class="naslov-zaslona"><div><h2>Skeniraj barkod</h2><p>Usmjeri kameru na barkod proizvoda u trgovini.</p></div></div>
    ${podrzano ? '<video id="skenerVideo" class="skener-video" playsinline muted></video><p class="stanje-glasa" id="skenerStanje">Pokrećem kameru…</p>' : '<div class="kartica ravna"><p>Ovaj preglednik ne podržava skeniranje kamerom. Upiši brojeve ispod barkoda.</p></div>'}
    <form class="upis" id="barkodForma"><input id="barkodPolje" inputmode="numeric" placeholder="ili upiši barkod (npr. 3850104000011)"><button class="gumb glavni">Traži</button></form>
  </div>`;
  $('#barkodForma').onsubmit = (e) => { e.preventDefault(); pronadiBarkod($('#barkodPolje').value); };
  if (podrzano) pokreniSkener();
}
function pronadiBarkod(vrijednost) {
  let b = String(vrijednost || '').replace(/\D/g, '');
  if (b.length === 12) b = '0' + b;
  const i = P.baza.poBarkodu.get(b) ?? P.baza.poBarkodu.get(b.replace(/^0/, ''));
  if (i == null) { poruka(`Proizvod s barkodom ${b} nije u današnjim cjenicima.`); return false; }
  prikaziProizvod(i, true);
  return true;
}
async function pokreniSkener() {
  const stanje = $('#skenerStanje');
  try {
    const detektor = new window.BarcodeDetector({ formats: ['ean_13', 'ean_8', 'upc_a', 'upc_e'] });
    skenerTok = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
    const video = $('#skenerVideo');
    if (!video) { zaustaviSkener(); return; }
    video.srcObject = skenerTok;
    await video.play();
    stanje.textContent = 'Tražim barkod…';
    let zadnji = '';
    const petlja = async () => {
      if (!skenerTok || S.zaslon !== 'skener') { zaustaviSkener(); return; }
      try {
        const kodovi = await detektor.detect(video);
        if (kodovi.length && kodovi[0].rawValue !== zadnji) {
          zadnji = kodovi[0].rawValue;
          stanje.textContent = `Pročitano: ${zadnji}`;
          if (navigator.vibrate) navigator.vibrate(60);
          pronadiBarkod(zadnji);
        }
      } catch { /* pojedinačni okvir nije uspio */ }
      setTimeout(petlja, 280);
    };
    petlja();
  } catch (e) {
    stanje.className = 'stanje-glasa greska';
    stanje.textContent = e.name === 'NotAllowedError' ? 'Kamera nije dopuštena. Dopusti kameru u postavkama preglednika ili upiši barkod.' : 'Kamera se ne može pokrenuti. Upiši barkod ispod.';
    zabiljezi('skener', e.name, e.message);
  }
}

function zaslonStatus(el) {
  const m = P.meta;
  const znak = { ok: '<span class="oznaka zelena">svježe</span>', stari: '<span class="oznaka zuta">stariji cjenik</span>', nema: '<span class="oznaka crvena">nema podataka</span>' };
  el.innerHTML = `<div class="zaslon">${natrag()}
    <div class="naslov-zaslona"><div><h2>Status podataka</h2><p>Cijene se svaki dan automatski preuzimaju iz službenih cjenika trgovina.</p></div></div>
    <section class="kartica">
      <table class="tablica"><tbody>
        <tr><td>Datum cjenika</td><td class="broj"><b>${datumHR(m.datum)}</b></td></tr>
        <tr><td>Obrađeno</td><td class="broj">${vrijemeHR(m.generirano)}</td></tr>
        <tr><td>Proizvoda (bez duplikata)</td><td class="broj">${m.proizvoda.toLocaleString('hr-HR')}</td></tr>
        <tr><td>Poslovnica</td><td class="broj">${m.poslovnica.toLocaleString('hr-HR')}</td></tr>
        <tr><td>Na ovom mobitelu</td><td class="broj">${P.izSpremista ? 'spremljene cijene (bez interneta)' : 'svježe učitano'}<br><span class="sitno">${vrijemeHR(P.ucitano)}</span></td></tr>
      </tbody></table>
      <button class="gumb mali" style="margin-top:10px" data-akcija="osvjezi-podatke">Provjeri ima li novijih cijena</button>
    </section>
    <section class="kartica"><h3>Po trgovini</h3>
      <table class="tablica"><thead><tr><th>Lanac</th><th>Stanje</th><th class="broj">Proizvoda</th><th class="broj">Posl.</th></tr></thead><tbody>
      ${m.lanci.map((l) => `<tr><td>${znakTrgovine({ lanac: l.id, naziv: l.naziv }, false)}<br><span class="sitno">${l.datum ? datumHR(l.datum) : ''}</span></td><td>${znak[l.status] || esc(l.status)}${l.napomena ? `<br><span class="sitno">${esc(l.napomena)}</span>` : ''}</td><td class="broj">${l.proizvoda.toLocaleString('hr-HR')}</td><td class="broj">${l.poslovnica}<br><span class="sitno">${l.s_koordinatama} na karti</span></td></tr>`).join('')}
      </tbody></table></section>
    ${m.upozorenja && m.upozorenja.length ? `<section class="kartica ravna"><h3>Napomene uvoza</h3><ul class="sitno">${m.upozorenja.map((u) => `<li>${esc(u)}</li>`).join('')}</ul></section>` : ''}
    <section class="kartica ravna"><h3>Automatski popravci</h3><p class="sitno" style="margin-top:6px">Preskočeno neispravnih cijena: ${Object.entries(m.preskoceno || {}).map(([k, v]) => `${esc(k)}: ${Number(v).toLocaleString('hr-HR')}`).join(' · ') || '–'}.</p>
      <p class="sitno" style="margin-top:6px">Izvor: ${esc(m.izvor)}.</p></section>
  </div>`;
}

function zaslonTrgovine(el) {
  const odabrani = new Set(odabraniLanci());
  el.innerHTML = `<div class="zaslon">${natrag()}
    <div class="naslov-zaslona"><div><h2>Moje trgovine</h2><p>Pretražuju se samo označeni lanci.</p></div></div>
    <div class="redak"><button class="gumb mali" data-akcija="lanci-svi">Označi sve</button><button class="gumb mali" data-akcija="lanci-nijedan">Ukloni sve</button></div>
    <section class="kartica">${P.meta.lanci.filter((l) => P.baza.lanci[l.id]).map((l) => `<label class="kvacica"><input type="checkbox" data-lanac="${l.id}" ${odabrani.has(l.id) ? 'checked' : ''}>
      <span class="razmak">${znakTrgovine({ lanac: l.id, naziv: l.naziv }, false)}<br><span class="sitno">${l.proizvoda.toLocaleString('hr-HR')} proizvoda · ${l.poslovnica} poslovnica</span></span></label>`).join('')}</section>
  </div>`;
  el.querySelectorAll('input[data-lanac]').forEach((c) => {
    c.onchange = () => {
      const sad = new Set(odabraniLanci());
      if (c.checked) sad.add(c.dataset.lanac); else sad.delete(c.dataset.lanac);
      S.lanci = sad.size === sviLanci().length ? null : [...sad];
      zadnjiIzracun = null; spremi();
    };
  });
}

function zaslonPostavke(el) {
  el.innerHTML = `<div class="zaslon">${natrag()}
    <h2>Postavke</h2>
    <section class="kartica"><label class="sitno" for="drzava">Država</label>
      <select class="polje" id="drzava" style="margin-top:6px">${DRZAVE.map((d) => `<option value="${d.id}" ${d.id === S.drzava ? 'selected' : ''} ${d.aktivna ? '' : 'disabled'}>${esc(d.naziv)}${d.aktivna ? '' : ' (uskoro)'}</option>`).join('')}</select></section>
    <section class="kartica"><label class="sitno" for="tema">Izgled</label>
      <select class="polje" id="tema" style="margin-top:6px"><option value="auto">Kao na mobitelu</option><option value="svijetla">Svijetli</option><option value="tamna">Tamni</option></select></section>
    <section class="kartica">
      <div class="redak"><h3 class="razmak">Premium</h3><span class="oznaka zuta">uskoro · 1,99 €/mj</span></div>
      <ul class="sitno" style="margin:8px 0 0;padding-left:18px"><li>bez oglasa</li><li>zajednički obiteljski popis u stvarnom vremenu</li><li>obavijest kad tvoji proizvodi budu na akciji</li><li>povijest cijena</li></ul>
      <p class="sitno" style="margin-top:8px">Premium nikad ne mijenja poredak rezultata. Trgovine ne mogu platiti da izgledaju jeftinije.</p>
      <button class="gumb puni" style="margin-top:10px" disabled>Pretplata uskoro</button>
    </section>
    <section class="kartica ravna"><h3>Podaci na mobitelu</h3><p class="sitno" style="margin:6px 0 10px">Popis, odabrane trgovine i ušteda spremaju se samo na ovom mobitelu.</p>
      <button class="gumb mali" data-akcija="obrisi-sve">Obriši sve moje podatke</button></section>
  </div>`;
  $('#tema').value = S.tema;
  $('#tema').onchange = (e) => { S.tema = e.target.value; primijeniTemu(); spremi(); };
  $('#drzava').onchange = (e) => { S.drzava = e.target.value; spremi(); location.reload(); };
}

function zaslonGreska(el) {
  const tekst = izvjesce({ podaci: P ? `${P.meta.datum} (${P.meta.verzija})` : '', drzava: S.drzava, zaslon: S.zaslon, stavki: S.stavke.length, lokacija: S.lokacija.ukljucena });
  el.innerHTML = `<div class="zaslon">${natrag()}
    <div class="naslov-zaslona"><div><h2>Izvješće o grešci</h2><p>Aplikacija sama ponavlja neuspjela preuzimanja, preskače loše cijene i koristi zadnje dobre podatke. Ako nešto i dalje ne radi, kopiraj ovo izvješće i pošalji ga.</p></div></div>
    <textarea class="izvjesce" readonly id="izvjesceTekst">${esc(tekst)}</textarea>
    <div class="redak"><button class="gumb glavni razmak" data-akcija="kopiraj-izvjesce">${IKONE.kopiraj} Kopiraj izvješće</button>
      <a class="gumb" target="_blank" rel="noopener" href="${REPOZITORIJ}/issues/new?title=${encodeURIComponent('Greška u aplikaciji')}&body=${encodeURIComponent(tekst.slice(0, 6000))}">GitHub</a></div>
    <button class="gumb mali" data-akcija="obrisi-greske">Obriši zabilježene greške</button>
  </div>`;
}

function zaslonO(el) {
  el.innerHTML = `<div class="zaslon">${natrag()}
    <h2>O aplikaciji</h2>
    <section class="kartica"><p><b>Najjeftinija košarica</b> uspoređuje cijene iz službenih dnevnih cjenika koje trgovački lanci u Hrvatskoj moraju objavljivati (Odluka NN 75/2025).</p>
      <ul class="sitno" style="margin:10px 0 0;padding-left:18px;display:grid;gap:4px">
        <li><b>Pošteno:</b> trgovine ne plaćaju za položaj. Poredak ovisi samo o cijeni.</li>
        <li><b>Cijena i količina zajedno:</b> uvijek vidiš pakiranje, broj pakiranja, cijenu po kg/l i marku.</li>
        <li><b>Bez izmišljanja:</b> ako trgovina nije objavila količinu, to piše.</li>
        <li><b>Lanac ili poslovnica:</b> bez lokacije vidiš uobičajenu cijenu lanca; s lokacijom stvarne cijene poslovnica u krugu.</li>
        <li><b>Privatnost:</b> popis i lokacija ostaju na tvom mobitelu.</li>
      </ul></section>
    <p class="sitno">Verzija ${VERZIJA_APLIKACIJE} · podaci ${esc(P.meta.verzija)} · izvor podataka: ${esc(P.meta.izvor)}</p>
  </div>`;
}

// ---------------------------------------------------------------- događaji
document.addEventListener('click', (e) => {
  const navEl = e.target.closest('[data-idi]');
  if (navEl && !e.target.closest('[data-akcija]')) {
    if (S.zaslon === 'skener') zaustaviSkener();
    zatvoriPlocu();
    idi(navEl.dataset.idi);
    return;
  }
  if (e.target.closest('[data-zatvori]')) { const lok = !!$('#ploca .lok-ploca'); zatvoriPlocu(); if (lok) prikazi(); return; }
  const a = e.target.closest('[data-akcija]');
  if (!a) return;
  const id = a.dataset.id;
  const stavka = id ? S.stavke.find((s) => s.id === id) : null;
  switch (a.dataset.akcija) {
    case 'brzo': case 'prijedlog': {
      dodajGrupu(Number(a.dataset.g), Number(a.dataset.pg ?? -1));
      if (a.dataset.akcija === 'prijedlog') {
        // upisani dio zamijeni odabranim prijedlogom; prethodne stavke iz istog upisa ostaju u polju
        const polje = $('#upisPolje');
        if (polje) { polje.value = ''; polje.focus(); }
      }
      break;
    }
    case 'favorit': {
      const i = Number(a.dataset.i);
      const k = kljucFavorita(i);
      S.favoriti = S.favoriti || [];
      if (S.favoriti.includes(k)) { S.favoriti = S.favoriti.filter((x) => x !== k); poruka('Maknuto iz favorita.'); } else { S.favoriti.push(k); poruka('★ Dodano u favorite – javit ćemo kad bude na akciji (zaslon Akcije).'); }
      spremi();
      a.classList.toggle('aktivna', jeFavorit(i));
      a.setAttribute('aria-pressed', String(jeFavorit(i)));
      a.textContent = jeFavorit(i) ? '★ U favoritima' : '☆ Prati cijenu';
      break;
    }
    case 'favorit-makni': S.favoriti = (S.favoriti || []).filter((x) => x !== a.dataset.k); spremi(); prikazi(); break;
    case 'u-kosaru': {
      if (!stavka) break;
      stavka.uKosari = !stavka.uKosari;
      spremi();
      prikazi();
      const sve = S.stavke.length && S.stavke.every((s) => s.uKosari);
      if (sve) poruka('Sve je u košarici. Dodirni „Kupio/la sam” u rezultatima da zabilježiš uštedu.');
      break;
    }
    case 'manje': case 'vise': {
      if (!stavka) break;
      const korak = korakKolicine(stavka.jedinica);
      const nova = stavka.kolicina + (a.dataset.akcija === 'vise' ? korak : -korak);
      if (nova <= 0) {
        const kopija = { ...stavka };
        const poz = S.stavke.indexOf(stavka);
        S.stavke.splice(poz, 1);
        promjenaPopisa();
        poruka('Stavka je uklonjena.', { tekst: 'Vrati', radi: () => { S.stavke.splice(poz, 0, kopija); promjenaPopisa(); } });
        break;
      }
      stavka.kolicina = Math.round(nova * 1000) / 1000;
      stavka.zadano = false;
      promjenaPopisa();
      break;
    }
    case 'uredi': urediStavku(id); break;
    case 'podgrupa':
      if (stavka) { stavka.pg = Number(a.dataset.pg); stavka.odbijeni = []; zatvoriPlocu(); promjenaPopisa(); }
      break;
    case 'spremi-stavku': spremiStavku(id); break;
    case 'obrisi':
      S.stavke = S.stavke.filter((s) => s.id !== id); zatvoriPlocu(); promjenaPopisa();
      break;
    case 'isprazni': {
      const stare = S.stavke;
      S.stavke = []; promjenaPopisa();
      poruka('Popis je ispražnjen.', { tekst: 'Vrati', radi: () => { S.stavke = stare; promjenaPopisa(); } });
      break;
    }
    case 'zakljucaj': S.zakljucano = true; S.otvorenB = null; spremi(); idi('rezultati'); break;
    case 'otkljucaj': S.zakljucano = false; spremi(); idi('popis'); break;
    case 'tab': S.rezTab = a.dataset.tab; spremi(); prikazi(); break;
    case 'otvori-b': S.otvorenB = a.dataset.id; spremi(); prikazi(); break;
    case 'zamijeni': zamijeni(id, Number(a.dataset.i)); break;
    case 'vrati-sve': if (stavka) { stavka.odbijeni = []; zadnjiIzracun = null; spremi(); prikazi(); } break;
    case 'proizvod': prikaziProizvod(Number(a.dataset.i)); break;
    case 'prijavi': prijaviCijenu(Number(a.dataset.i)); break;
    case 'posalji-prijavu': {
      const t = tekstPrijave(Number(a.dataset.i));
      window.open(`${REPOZITORIJ}/issues/new?labels=${encodeURIComponent('pogrešna cijena')}&title=${encodeURIComponent('Pogrešna cijena: ' + P.baza.p[Number(a.dataset.i)][0])}&body=${encodeURIComponent(t)}`, '_blank', 'noopener');
      zatvoriPlocu(); poruka('Hvala! Prijava je otvorena.');
      break;
    }
    case 'kopiraj-prijavu': kopiraj(tekstPrijave(Number(a.dataset.i))); break;
    case 'dodaj-proizvod': {
      const i = Number(a.dataset.i);
      const p = P.baza.p[i];
      S.stavke.push({ id: novaStavkaId(), tekst: p[0], g: p[4], pg: p[5], upit: '', kolicina: 1, jedinica: 'pak', zadano: false, proizvod: i, samoTaj: true });
      S.zakljucano = false; zatvoriPlocu(); promjenaPopisa(); poruka('Dodano na popis.');
      break;
    }
    case 'kupljeno': {
      const iznos = Number(a.dataset.iznos);
      const prosjek = Number(a.dataset.prosjek);
      const usteda = Math.max(0, Math.round(prosjek - iznos));
      S.usteda.ukupno += usteda;
      S.usteda.kupnje.push({ datum: new Date().toISOString(), iznos, usteda, opis: a.dataset.opis });
      S.kupljenoKljuc = kljucIzracuna() + S.rezTab;
      spremi(); prikazi();
      poruka(usteda > 0 ? `Bravo! Ušteđeno ${eur(usteda)}.` : 'Kupnja je zabilježena.');
      break;
    }
    case 'ponisti-ustedu': if (confirm('Obrisati povijest uštede?')) { S.usteda = { ukupno: 0, kupnje: [] }; spremi(); prikazi(); } break;
    case 'podijeli-rezultat': ponudiDijeljenje(tekstRezultata(), 'Pošalji popis i rezultat'); break;
    case 'podijeli-popis': ponudiDijeljenje(tekstPopisa(), 'Pošalji popis obitelji'); break;
    case 'imenik': posaljiIzImenika(); break;
    case 'uvezi-kod': {
      const v = $('#kodPolje').value.trim();
      uveziPopis(v.includes('#popis=') ? v.split('#popis=')[1] : v);
      break;
    }
    case 'lokacija': otvoriLokaciju(); break;
    case 'lok-trazi': traziLokaciju(); break;
    case 'lok-r': postaviKrug(Number(a.dataset.r)); break;
    case 'lok-iskljuci': iskljuciLokaciju(); break;
    case 'lok-karta': zatvoriPlocu(); S.zaslon = 'karta'; prikazi(); break;
    case 'ponovno-poslovnice': zadnjiIzracun = null; prikazi(); break;
    case 'moja-lokacija': otvoriLokaciju(); break;
    case 'iskljuci-lokaciju': iskljuciLokaciju(); break;
    case 'radijus':
      // na karti: s poznatom lokacijom krug se odmah primjenjuje, inače isti izbor kao na glavnom zaslonu
      if (S.lokacija.lat == null) { S.lokacija.radijus = Number(a.dataset.r); otvoriLokaciju(); } else {
        S.lokacija = { ...S.lokacija, radijus: Number(a.dataset.r), ukljucena: true }; zadnjiIzracun = null; spremi(); prikazi();
      }
      break;
    case 'lanci-svi': S.lanci = null; zadnjiIzracun = null; spremi(); prikazi(); break;
    case 'lanci-nijedan': S.lanci = []; zadnjiIzracun = null; spremi(); prikazi(); break;
    case 'kopiraj-izvjesce': kopiraj($('#izvjesceTekst').value); break;
    case 'obrisi-greske': obrisiGreske(); prikazi(); break;
    case 'obrisi-sve':
      if (confirm('Obrisati popis, odabrane trgovine i povijest uštede s ovog mobitela?')) { S = structuredClone(POCETNO); spremi(); location.reload(); }
      break;
    case 'osvjezi-podatke': pokreni(true); break;
    case 'ponovno': prikazi(); break;
    case 'instaliraj':
      if (instalacija) { instalacija.prompt(); instalacija.userChoice.finally(() => { instalacija = null; prikazi(); }); }
      break;
    default: break;
  }
});

window.addEventListener('beforeinstallprompt', (e) => { e.preventDefault(); instalacija = e; });

function primijeniTemu() {
  if (S.tema === 'auto') document.documentElement.removeAttribute('data-tema');
  else document.documentElement.setAttribute('data-tema', S.tema);
}

function obavijest(html) {
  const o = $('#obavijest');
  if (!html) { o.hidden = true; return; }
  o.innerHTML = html;
  o.hidden = false;
}

// ---------------------------------------------------------------- pokretanje
async function pokreni(rucno = false) {
  primijeniTemu();
  try {
    const d = await ucitajPodatke(S.drzava);
    const baza = new Baza(d.proizvodi, d.grupe);
    const novo = !P || P.meta.verzija !== d.meta.verzija;
    P = { ...d, baza, ucitano: new Date().toISOString() };
    pripremiGrupe(d.grupe);
    // stavke spremljene sa starijim podacima: indeksi proizvoda više ne vrijede
    if (S.verzijaPodataka && S.verzijaPodataka !== d.meta.verzija) {
      for (const s of S.stavke) {
        if (s.proizvod != null) { const b = s.barkod; s.proizvod = b ? baza.poBarkodu.get(b) ?? null : null; if (s.proizvod == null) s.samoTaj = false; }
        s.odbijeni = [];
      }
    }
    for (const s of S.stavke) if (s.proizvod != null) s.barkod = baza.p[s.proizvod][6];
    if (osvjeziStavke(S.stavke)) zadnjiIzracun = null;      // stare stavke ("mljeko") ponovno prepoznate
    S.verzijaPodataka = d.meta.verzija;
    spremi();
    zadnjiIzracun = null;
    const dana = Math.floor((Date.now() - new Date(d.meta.datum + 'T12:00:00')) / 86400000);
    if (d.izSpremista) obavijest(`Nema veze s internetom – prikazujem spremljene cijene od ${datumHR(d.meta.datum)}.`);
    else if (dana >= 2) obavijest(`Cijene su od ${datumHR(d.meta.datum)}. Noviji cjenici trenutno nisu dostupni; prikazuju se zadnji dobri podaci.`);
    else obavijest('');
    const hash = location.hash.match(/#popis=([\w-]+)/);
    if (hash) { history.replaceState(null, '', location.pathname); uveziPopis(hash[1]); }
    if (rucno) poruka(novo ? 'Učitane su nove cijene.' : 'Cijene su već najnovije.');
    idi(S.zaslon === 'skener' ? 'vise' : S.zaslon);
  } catch (e) {
    zabiljezi('ucitavanje', e.message, e.stack);
    if (P) { poruka('Nove cijene se trenutno ne mogu učitati. Koristim postojeće.'); return; }
    $('#sadrzaj').innerHTML = `<div class="zaslon"><div class="kartica greska-kartica"><h3>Cijene se ne mogu učitati</h3>
      <p class="prigusen" style="margin-top:6px">Provjeri internetsku vezu i pokušaj ponovno. Aplikacija je već tri puta pokušala.</p>
      <div class="redak" style="margin-top:12px;flex-wrap:wrap"><button class="gumb glavni" onclick="location.reload()">Pokušaj ponovno</button></div></div>
      <p class="sitno">Ako se ponavlja, kopiraj izvješće i pošalji ga:</p>
      <textarea class="izvjesce" readonly>${esc(izvjesce({ drzava: S.drzava, zaslon: 'ucitavanje' }))}</textarea></div>`;
  }
}

if ('serviceWorker' in navigator) {
  const imaoKontrolora = !!navigator.serviceWorker.controller;
  navigator.serviceWorker.register('sw.js', { scope: './' }).catch((e) => zabiljezi('sw', 'Registracija nije uspjela', e.message));
  // nova verzija aplikacije je preuzela upravljanje: osvježi jednom da se ne miješaju stara i nova
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (imaoKontrolora && !sessionStorage.getItem('kosarica-osvjezeno')) { sessionStorage.setItem('kosarica-osvjezeno', '1'); location.reload(); }
  });
}
pokreni();
