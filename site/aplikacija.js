"use strict";

// ---------- Stanje aplikacije (sprema se u mobitel) ----------
const SPREMISTE = "kosarica-v1";
let stanje = {
  popis: [],          // [{ naziv, kom, kupljeno, marka }] - marka: null = bilo koja, inače samo ta stvarna marka
  zakljucano: false,
  odabir: {},         // grupa -> redni broj ponude
  odabirSvi: {},      // odabir iz pregleda svih trgovina; referentna količina za usporedbu
  nacin: "jedinica",  // Poredak uvijek određuje jedinična cijena.
  iskljuceni: [],     // nazivi lanaca koji korisniku ne odgovaraju
  jedna: null,        // naziv lanca ako se kupuje sve u jednoj trgovini
  // Odabrana točka (ostaje samo u ovom pregledniku, ne šalje se nikamo) i polumjer kruga u km.
  lokacija: null,     // { lat, lon, naziv, priblizno }
  radijus: 20,
};
try { Object.assign(stanje, JSON.parse(localStorage.getItem(SPREMISTE)) || {}); } catch (e) {}
// Starija verzija je spremala popis kao obične tekstove.
stanje.popis = (Array.isArray(stanje.popis) ? stanje.popis : [])
  .map((s) => typeof s === "string" ? { naziv: s, kom: 1, kupljeno: false } : s)
  .filter((s) => s && typeof s.naziv === "string" && s.naziv.trim())
  .map((s) => ({ naziv: s.naziv, kom: Math.min(99, Math.max(1, Math.floor(Number(s.kom) || 1))), kupljeno: !!s.kupljeno,
    // Stari zapis nema marku: bilo koja marka.
    marka: typeof s.marka === "string" && s.marka.trim() ? s.marka.trim() : null }));
stanje.iskljuceni = Array.isArray(stanje.iskljuceni) ? stanje.iskljuceni : [];
stanje.odabir = stanje.odabir && typeof stanje.odabir === "object" ? stanje.odabir : {};
stanje.nacin = "jedinica";
// Svako otvaranje započinje usporedbom svih lanaca.
stanje.iskljuceni = [];
stanje.jedna = null;
stanje.odabir = {};
stanje.odabirSvi = {};
delete stanje.grad;
delete stanje.poslovnice;
const RADIJUSI = [5, 10, 20, 30, 50];
stanje.radijus = RADIJUSI.includes(stanje.radijus) ? stanje.radijus : 20;
stanje.lokacija = valjanaLokacija(stanje.lokacija);
function valjanaLokacija(l) {
  return l && Number.isFinite(l.lat) && Number.isFinite(l.lon) && Math.abs(l.lat) <= 90 && Math.abs(l.lon) <= 180
    ? { lat: l.lat, lon: l.lon, naziv: typeof l.naziv === "string" ? l.naziv.slice(0, 200) : "", priblizno: !!l.priblizno } : null;
}
function spremi() {
  try { localStorage.setItem(SPREMISTE, JSON.stringify(stanje)); } catch (e) {}
}

// ---------- Podaci o cijenama ----------
// { datum, lanci: [...], poslovnice: [[lanac, store_id, adresa, grad], ...],
//   proizvodi: [[naziv, količina, iznos, jedinica, riječi marke, [lanac, cijena, ...], [ponuda, ...]], ...] }
// Cijena lanca je najniža valjana cijena jedne stvarne poslovnice; ponuda = [poslovnica, broj poslovnica s valjanom
// cijenom, najviša od njih, akcija]. Cijene po poslovnici su u data/poslovnice/<poslovnica>.json.
let podaci = null;
let klasifikacija = null;
let rijeci = [];       // za svaki proizvod: normalizirane riječi naziva
const pogociCache = new Map();
const ponudeCache = new Map();
const cjeniciPoslovnica = new Map();  // poslovnica -> Map(proizvod -> cijena u centima), null dok se učitava, false greška
const retciPoslovnica = new Map();    // poslovnica -> Map(proizvod -> redak u službenoj datoteci)
// Provjerene koordinate stvarnih poslovnica (OpenStreetMap): "Lanac|store_id" -> [lat, lon, osm, kvaliteta].
let lokacije = null;
// Krug oko odabrane točke: stvarne poslovnice s provjerenim koordinatama unutar polumjera (od najbliže).
// stanje: "nacionalno" (bez lokacije), "ucitava", "spremno", "prazno", "greska", "bez-koordinata".
let krug = { kljuc: "", stanje: "nacionalno", poslovnice: [], bezKoordinata: 0, neucitane: 0 };
let generacijaKruga = 0;
const lokalneCijene = new Map();      // proizvod -> [cijene, ponude] samo iz poslovnica u krugu

const $ = (id) => document.getElementById(id);
const euro = (x) => x.toFixed(2).replace(".", ",") + " €";

// "Mlijeko Trajno" -> "mlijeko trajno", "šećer" -> "secer"
function normaliziraj(tekst) {
  return tekst.toLowerCase().replace(/đ/g, "d").normalize("NFD")
    .replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]+/g, " ").trim();
}

// Korijen riječi da "mlijeko" nađe i "mlijeka", "jaja" i "jaje" itd.
function korijen(rijec) {
  return rijec.length >= 4 ? rijec.replace(/[aeiou]+$/, "") : rijec;
}

// Padežni i množinski nastavci. "sir" tako nađe "sira", ali ne i "sirup".
const NASTAVCI = new Set(["", "a", "e", "i", "o", "u", "om", "em", "im", "ima", "ama", "ih", "oj", "og",
  "ov", "ova", "ove", "ovi", "ovo", "ev", "eva", "eve", "evi", "ja", "je", "ji", "ju", "jom",
  "ka", "ke", "ki", "ko", "ku", "ica", "ice", "ici"]);
// Riječ iza ovih ne opisuje sam proizvod: "čokolada s mlijekom", "jogurt od jagode".
const PRIJEDLOZI = new Set(["s", "sa", "od", "za", "u", "na", "bez", "iz", "po"]);

async function ucitajPodatke() {
  $("ponovi").hidden = true;
  $("status").textContent = "Učitavam cijene…";
  $("status").parentElement.classList.remove("greska", "spremno");
  try {
    const odgovor = await fetch("data/proizvodi.json", { cache: "no-cache" });
    if (!odgovor.ok) throw new Error(odgovor.status);
    const novi = await odgovor.json();
    if (!novi || !Array.isArray(novi.proizvodi) || !novi.proizvodi.length || !Array.isArray(novi.lanci)
        || !novi.lanci.length || !/^\d{4}-\d{2}-\d{2}$/.test(novi.datum)) throw new Error("Neispravan cjenik");
    podaci = novi;
    pogociCache.clear();
    ponudeCache.clear();
    if (podaci.verzija !== 2) {
      // Stari oblik: [naziv, količina, lanac, cijena]
      podaci.proizvodi = podaci.proizvodi.map(([n, k, l, c]) => [n, k, 0, "", 0, [l, c]]);
    }
    // Zaštita i za stare/offline cjenike: ne prikazuj ponude od jednog centa. Proizvodi ostaju na svojim mjestima
    // (indeksi vrijede i za datoteke poslovnica i za skupine).
    podaci.proizvodi = podaci.proizvodi.map((p) => {
      const cijene = [];
      const ponude = [];
      for (let k = 0; k < p[5].length; k += 2) {
        const c = p[5][k + 1];
        if (typeof c === "number" && Number.isFinite(c) && Math.round(c * 100) > 1) {
          cijene.push(p[5][k], c);
          ponude.push(Array.isArray(p[6]) ? p[6][k / 2] : null);
        }
      }
      return [...p.slice(0, 5), cijene, ponude, Number.isInteger(p[7]) ? p[7] : -1];
    });
    if (!podaci.proizvodi.some((p) => p[5].length)) throw new Error("Nema valjanih cijena");
    podaci.poslovnice = Array.isArray(podaci.poslovnice) ? podaci.poslovnice : [];
    podaci.marke = Array.isArray(podaci.marke) ? podaci.marke : [];
    cjeniciPoslovnica.clear();
    retciPoslovnica.clear();
    krug = { kljuc: "", stanje: "nacionalno", poslovnice: [], bezKoordinata: 0, neucitane: 0 };
    rijeci = podaci.proizvodi.map((p) => normaliziraj(p[0]).split(" "));
    klasifikacija = null;
    if (typeof Skupine !== "undefined") {
      try {
        const indeksOdgovor = await fetch("data/skupine.json", { cache: "no-cache" });
        if (indeksOdgovor.ok) klasifikacija = Skupine.pripremi(podaci.proizvodi, await indeksOdgovor.json(), rijeci);
      } catch (e) { /* Cjenik ostaje dostupan i ako indeks nedostaje ili je zastario. */ }
    }
    const [g, m, d] = podaci.datum.split("-");
    $("status").textContent =
      `Cijene od ${d}.${m}.${g}. · ${podaci.proizvodi.length.toLocaleString("hr-HR")} proizvoda · ${podaci.lanci.length} lanaca`
      + (podaci.provjereno_prema_sluzbenom_izvoru
        ? ` · iz službenih cjenika lanaca: ${podaci.provjereno_prema_sluzbenom_izvoru.toLocaleString("hr-HR")} ponuda; ostalo iz arhive cijene.dev (neprovjereno)`
        : podaci.izvor ? " · izvor: arhiva cijene.dev, nije izravno provjereno sa službenim cjenikom" : "");
    lokacije = null;
    try {
      const l = await fetch("data/lokacije.json", { cache: "no-cache" });
      if (l.ok) {
        const d = await l.json();
        lokacije = new Map();
        for (const x of Array.isArray(d.poslovnice) ? d.poslovnice : []) {
          if (Array.isArray(x) && Number.isFinite(x[2]) && Number.isFinite(x[3])) lokacije.set(`${x[0]}|${x[1]}`, [x[2], x[3], x[4], x[5]]);
        }
        $("karta-izvor").textContent = `Lokacije poslovnica: ${d.izvor || "OpenStreetMap"} · ${lokacije.size} poslovnica s provjerenom adresom.`;
      }
    } catch (e) { lokacije = null; }
    $("status").parentElement.classList.add("spremno");
  } catch (e) {
    podaci = null;
    klasifikacija = null;
    rijeci = [];
    $("ponovi").hidden = false;
    $("status").parentElement.classList.add("greska");
    $("status").textContent = "Cijene nisu dostupne. Tvoj popis ostaje spremljen.";
  }
  prikaziPostavke();
  prikazi();
}

// ---------- Pretraživanje ----------
// Indeksi proizvoda koji odgovaraju grupi (npr. "mlijeko"); uz "Samo ova marka" samo proizvodi te stvarne marke.
function pogoci(grupa) {
  const marka = markaStavke(grupa);
  const kljuc = grupa + "|" + (marka || "");
  if (pogociCache.has(kljuc)) return pogociCache.get(kljuc);
  let rezultat = [];
  const prepoznati = klasifikacija ? klasifikacija.pogoci(grupa) : null;
  if (prepoznati !== null) rezultat = [...prepoznati, ...klasifikacija.moguciPogoci(grupa)];
  else {
    const korijeni = normaliziraj(grupa).split(" ").filter(Boolean).map(korijen);
    if (korijeni.length) {
      rezultat = trazi(korijeni, (w, k) => w.startsWith(k) && NASTAVCI.has(w.slice(k.length)));
      if (!rezultat.length) rezultat = trazi(korijeni, (w, k) => w.startsWith(k));
    }
  }
  // Nepoznata marka ne zadovoljava strogi filtar; nema zamjene drugom markom.
  if (marka) rezultat = rezultat.filter((i) => istaMarka(markaProizvoda(i), marka));
  pogociCache.set(kljuc, rezultat);
  return rezultat;
}

// Stvarna marka proizvoda iz cjenika ili null kad je cjenik ne navodi.
function markaProizvoda(i) {
  const m = podaci && podaci.proizvodi[i] ? podaci.proizvodi[i][7] : -1;
  return Number.isInteger(m) && m >= 0 && typeof podaci.marke[m] === "string" && podaci.marke[m].trim() ? podaci.marke[m] : null;
}
const istaMarka = (a, b) => !!a && !!b && normaliziraj(a) === normaliziraj(b);
function markaStavke(grupa) {
  const s = stanje.popis.find((x) => x.naziv === grupa);
  return s && s.marka ? s.marka : null;
}

function trazi(korijeni, odgovara) {
  const razine = [[], [], []];
  for (let i = 0; i < rijeci.length; i++) {
    const r = rijeci[i];
    if (!korijeni.every((k) => r.some((w) => odgovara(w, k)))) continue;
    const marka = podaci.proizvodi[i][4];
    const mjesto = r.findIndex((w) => odgovara(w, korijeni[0]));
    // 0: naziv počinje traženom riječi (ne računajući marku), npr. "Dukat Mlijeko…"
    // 1: riječ je negdje u nazivu, 2: riječ je iza prijedloga ("…s mlijekom")
    const razina = mjesto <= marka ? 0 : PRIJEDLOZI.has(r[mjesto - 1]) ? 2 : 1;
    razine[razina].push(i);
  }
  return razine.find((r) => r.length) || [];
}

// ---------- Ponude ----------
function sviLanci() {
  if (!podaci) return new Set();
  const iskljuceni = new Set(stanje.iskljuceni);
  return new Set(podaci.lanci.map((_, i) => i).filter((i) => !iskljuceni.has(podaci.lanci[i])));
}

function dozvoljeniLanci() {
  const svi = sviLanci();
  const jedna = podaci ? podaci.lanci.indexOf(stanje.jedna) : -1;
  return jedna >= 0 && svi.has(jedna) ? new Set([jedna]) : svi;
}

// [cijene, ponude] proizvoda: bez lokacije najniža cijena lanca u cijeloj Hrvatskoj; s lokacijom samo cijene stvarnih
// poslovnica unutar kruga (najniža po lancu, uz tu poslovnicu). Dok se krug učitava ili je prazan: nema ponuda.
function cijeneProizvoda(i) {
  if (!stanje.lokacija) return [podaci.proizvodi[i][5], podaci.proizvodi[i][6]];
  if (krug.stanje !== "spremno") return [[], []];
  if (lokalneCijene.has(i)) return lokalneCijene.get(i);
  const poLancu = new Map();
  for (const { idx } of krug.poslovnice) {
    const cjenik = cjeniciPoslovnica.get(idx);
    const c = cjenik instanceof Map ? cjenik.get(i) : undefined;
    if (!Number.isInteger(c) || c <= 1) continue;
    const l = podaci.poslovnice[idx][0];
    const x = poLancu.get(l);
    if (!x) poLancu.set(l, { c, idx, n: 1, max: c });
    else {
      x.n++;
      if (c > x.max) x.max = c;
      if (c < x.c) { x.c = c; x.idx = idx; } // jednaka cijena: ostaje bliža poslovnica (krug je od najbliže)
    }
  }
  const cijene = [];
  const ponude = [];
  for (const [l, x] of [...poLancu].sort((a, b) => a[1].c - b[1].c)) {
    const redak = retciPoslovnica.get(x.idx)?.get(i);
    cijene.push(l, x.c / 100);
    ponude.push([x.idx, x.n, x.max / 100, 0, Number.isInteger(redak) ? redak : 0, ""]);
  }
  const r = [cijene, ponude];
  lokalneCijene.set(i, r);
  return r;
}

// Ponuda nosi stvarnu poslovnicu čija je to cijena (ili zadanu poslovnicu kad se zbraja jedna poslovnica).
function ponuda(i, lanac, cijena, poslovnica = null) {
  const [, , iznos, jedinica] = podaci.proizvodi[i];
  const [cijene, ponude] = cijeneProizvoda(i);
  let meta = null;
  if (poslovnica === null && ponude) {
    for (let k = 0; k < cijene.length; k += 2) if (cijene[k] === lanac) { meta = ponude[k / 2]; break; }
  }
  const posl = poslovnica !== null ? poslovnica : meta ? meta[0] : null;
  return { i, lanac, cijena, jedinica, poJedinici: iznos ? cijena / iznos : null,
    poslovnica: posl,
    // Potvrđena je samo cijena poslovnice s valjanim tragom službene datoteke. Stari ili offline oblik bez traga
    // (ili s neispravnim tragom) ostaje vidljiv, ali nije potvrđen i ne sudjeluje u poretku ni zbrojevima.
    sluzbena: posl !== null && izvorPoslovnice(posl) !== null,
    brojPoslovnica: meta ? meta[1] : null, najvisa: meta ? meta[2] : null, akcija: !!(meta && meta[3]),
    redak: meta && Number.isInteger(meta[4]) ? meta[4] : null, nazivAkcije: meta && meta[5] ? meta[5] : "",
    vrstaNejasna: !!klasifikacija && !klasifikacija.vrstaProizvoda(i) };
}

// [URL službene datoteke, datum] iz koje su cijene poslovnice, ili null (arhiva cijene.dev).
function izvorPoslovnice(idx) {
  const p = podaci && Array.isArray(podaci.poslovnice) ? podaci.poslovnice[idx] : null;
  const i = Array.isArray(p) && Number.isInteger(p[4]) ? p[4] : -1;
  const izvor = i >= 0 && Array.isArray(podaci.izvori) ? podaci.izvori[i] : null;
  // Valjan trag: [https URL službene datoteke, datum GGGG-MM-DD].
  return Array.isArray(izvor) && /^https?:\/\/\S+$/.test(String(izvor[0] || "")) && /^\d{4}-\d{2}-\d{2}$/.test(String(izvor[1] || ""))
    ? izvor : null;
}

function opisPoslovnice(idx) {
  const p = podaci && (podaci.poslovnice || [])[idx];
  if (!p) return "";
  return [p[2], p[3]].filter(Boolean).join(", ") || `poslovnica ${p[1]}`;
}

// Gdje je cijena objavljena i koliko se razlikuje u drugim poslovnicama lanca (samo oznaka za provjeru).
function opisIzvoraCijene(p) {
  if (p.poslovnica === null) return "";
  const dijelovi = [`Poslovnica: ${opisPoslovnice(p.poslovnica)}`];
  const izvor = izvorPoslovnice(p.poslovnica);
  dijelovi.push(izvor ? `službeni cjenik${p.redak ? `, redak ${p.redak}` : ""}` : "arhiva cijene.dev, nije provjereno sa službenim cjenikom");
  if (p.akcija) dijelovi.push(p.nazivAkcije ? `akcija: ${p.nazivAkcije}` : "akcijska cijena");
  if (p.najvisa && Math.round(p.najvisa * 100) > Math.round(p.cijena * 100)) {
    dijelovi.push(`u drugim poslovnicama lanca do ${euro(p.najvisa)} (provjeri)`);
  }
  return dijelovi.join(" · ");
}

// U poretku, najpovoljnijem i zbrojevima sudjeluju samo ponude potvrđene službenim cjenikom (kad cjenik nosi trag
// izvora). Ponuda iz arhive cijene.dev ostaje vidljiva i označena, ali ne pobjeđuje i ne ulazi u potvrđeni zbroj.
function imaJedinicnu(p) {
  return !p.vrstaNejasna && p.sluzbena && Number.isFinite(p.poJedinici) && p.poJedinici > 0 && ["kg", "l", "kom"].includes(p.jedinica);
}

// Različite jedinice ne smiju sakriti cijelu skupinu niti se uspoređivati brojčano.
// Najzastupljenija jedinica ide prva; sve druge i nepoznate količine ostaju dostupne.
function jediniceGrupe(grupa) {
  const broj = new Map();
  for (const i of pogoci(grupa)) {
    const cijene = cijeneProizvoda(i)[0];
    for (let k = 0; k < cijene.length; k += 2) {
      const p = ponuda(i, cijene[k], cijene[k + 1]);
      if (imaJedinicnu(p)) { broj.set(p.jedinica, (broj.get(p.jedinica) || 0) + 1); break; }
    }
  }
  return [...broj.keys()].sort((a, b) => broj.get(b) - broj.get(a) || a.localeCompare(b));
}

function usporedba(jedinice) {
  const red = (p) => imaJedinicnu(p) ? jedinice.indexOf(p.jedinica) : jedinice.length;
  return (a, b) => red(a) - red(b)
    || (imaJedinicnu(a) && imaJedinicnu(b) && a.jedinica === b.jedinica
      ? a.poJedinici - b.poJedinici || a.cijena - b.cijena
      : podaci.proizvodi[a.i][0].localeCompare(podaci.proizvodi[b.i][0], "hr"));
}

// Sve ponude za jednu grupu, od najisplativije prema skupljoj.
// Svaki proizvod se pojavljuje samo jednom, u najjeftinijem dopuštenom lancu.
function ponudeZaGrupu(grupa, lanci = dozvoljeniLanci()) {
  const kljuc = grupa + "|" + (markaStavke(grupa) || "") + "|" + [...lanci].join(",");
  if (ponudeCache.has(kljuc)) return ponudeCache.get(kljuc);
  const ponude = [];
  for (const i of pogoci(grupa)) {
    const cijene = cijeneProizvoda(i)[0];
    // Ponuda proizvoda: najjeftinija potvrđena službenim cjenikom; nepotvrđena samo ako potvrđene nema.
    let najjeftinija = null;
    for (let k = 0; k < cijene.length; k += 2) {
      if (!lanci.has(cijene[k])) continue;
      const p = ponuda(i, cijene[k], cijene[k + 1]);
      if (!najjeftinija || (p.sluzbena && !najjeftinija.sluzbena)
          || (p.sluzbena === najjeftinija.sluzbena && p.cijena < najjeftinija.cijena)) najjeftinija = p;
    }
    if (najjeftinija) ponude.push(najjeftinija);
  }
  ponude.sort(usporedba(jediniceGrupe(grupa)));
  ponudeCache.set(kljuc, ponude);
  return ponude;
}

// Za "sve u jednoj trgovini": najbolja ponuda za grupu u svakom lancu.
// Najbolja ponuda svake trgovine za stavku. S navedenom stavkom bira se najmanji stvarni iznos za istu referentnu
// količinu (cijena × cijela pakiranja), ne najniža jedinična cijena: 1 l za 1,00 € pobjeđuje 2 l za 1,60 €.
function najboljePoLancu(grupa, lanci, trazenaJedinica = null, stavka = null) {
  const sve = [];
  for (const i of pogoci(grupa)) {
    const cijene = cijeneProizvoda(i)[0];
    for (let k = 0; k < cijene.length; k += 2) {
      if (lanci.has(cijene[k])) sve.push(ponuda(i, cijene[k], cijene[k + 1]));
    }
  }
  // Osnovna jedinica ne ovisi o odabranoj trgovini ni broju pakiranja.
  const jedinica = trazenaJedinica || jediniceGrupe(grupa)[0] || null;
  const usporedi = usporedba(jediniceGrupe(grupa));
  const najbolje = new Map();
  const trosak = (p) => (stavka ? centi(p.cijena * brojPakiranja(stavka, p, true)) : 0);
  for (const p of sve.filter((p) => imaJedinicnu(p) && p.jedinica === jedinica)) {
    const dosad = najbolje.get(p.lanac);
    if (!dosad || trosak(p) - trosak(dosad) < 0 || (trosak(p) === trosak(dosad) && usporedi(p, dosad) < 0)) najbolje.set(p.lanac, p);
  }
  return { najbolje, usporedi };
}

// Pregled jedne trgovine zadržava referentni odabir; promjena dopuštenih trgovina ga briše.
function promijeniPostavke(zadrziReferencu = false) {
  ponudeCache.clear();
  stanje.odabir = {};
  if (!zadrziReferencu) stanje.odabirSvi = {};
  else if (!stanje.jedna) stanje.odabir = { ...stanje.odabirSvi };
  else if (podaci) stanje.odabir = odabirJedneTrgovine();
  spremi();
  prikazi();
}

// ---------- Dodavanje stavki (glasom ili rukom) ----------
const BROJEVI = {
  jedan: 1, jedna: 1, jedno: 1, jednu: 1, dva: 2, dvije: 2, dvoje: 2, tri: 3, troje: 3,
  cetiri: 4, pet: 5, sest: 6, sedam: 7, osam: 8, devet: 9, deset: 10,
};
const RE_BROJ = "(\\d+|" + Object.keys(BROJEVI).join("|") + ")";
const RE_KOMADA = "(?:x|×|puta|komada|komad|kom|pakiranja|pakiranje|paketa|paket|boce|bocu|boca|vrecice|limenke)";
// "2 litre mlijeka" = 2 pakiranja; "500 g sira" = 1 pakiranje.
const RE_MJERA = /^(kg|kila|kilu|kile|kilograma?|l|lit|litra|litre|litru|litara)\s+(.+)$/;
const RE_SITNA_MJERA = /^(g|gr|grama|dag|deka|dkg|ml|dl|decilitra|cl)\s+(.+)$/;

// "2 mlijeka" -> { naziv: "mlijeka", kom: 2 }; "kruh" -> { naziv: "kruh", kom: null }
function rastavi(dio) {
  let tekst = dio.toLowerCase().replace(/č|ć/g, "c").replace(/š/g, "s");
  const izvorno = dio;
  let kom = null;
  let m = tekst.match(new RegExp(`^${RE_BROJ}\\s*${RE_KOMADA}?\\s+(.+)$`));
  let ostatak = izvorno;
  if (m) {
    kom = BROJEVI[m[1]] || parseInt(m[1], 10);
    ostatak = izvorno.slice(izvorno.length - m[2].length);
    tekst = m[2];
    const mjera = tekst.match(RE_MJERA);
    const sitna = tekst.match(RE_SITNA_MJERA);
    if (mjera) ostatak = ostatak.slice(ostatak.length - mjera[2].length);
    else if (sitna) { ostatak = ostatak.slice(ostatak.length - sitna[2].length); kom = 1; }
  } else if ((m = tekst.match(new RegExp(`^(.+?)\\s+(?:x\\s*(\\d+)|(\\d+)\\s*(?:x|komada|kom))$`)))) {
    kom = parseInt(m[2] || m[3], 10);
    ostatak = izvorno.slice(0, m[1].length);
  }
  if (kom !== null) kom = Math.min(Math.max(kom, 1), 99);
  return { naziv: ostatak.trim(), kom };
}

const kljucStavke = (naziv) => normaliziraj(naziv).split(" ").map(korijen).join(" ");

function dodajIzTeksta(tekst) {
  const dijelovi = tekst
    .split(/,|;|\.(?!\d)|\s+i\s+|\s+pa\s+|\s+te\s+|\s+onda\s+/i)
    .map((s) => s.trim().replace(/^(i|još|jos|pa)\s+/i, ""))
    .filter(Boolean);
  for (const d of dijelovi) {
    const { naziv: n, kom } = rastavi(d);
    if (!normaliziraj(n)) continue;
    const naziv = n.charAt(0).toUpperCase() + n.slice(1).toLowerCase();
    const postojeca = stanje.popis.find((p) => kljucStavke(p.naziv) === kljucStavke(naziv));
    if (postojeca) { if (kom) postojeca.kom = kom; }
    else stanje.popis.push({ naziv, kom: kom || 1, kupljeno: false });
  }
  spremi();
  prikazi();
}

function ukloni(i) {
  stanje.popis.splice(i, 1);
  spremi();
  prikazi();
}

function promijeniKolicinu(i, za) {
  const s = stanje.popis[i];
  s.kom = Math.min(Math.max(s.kom + za, 1), 99);
  spremi();
  prikazi();
}

// ---------- Prepoznavanje govora ----------
const Prepoznavanje = window.SpeechRecognition || window.webkitSpeechRecognition;
let slusac = null;

// Granice artikala prepoznaj iz poznatih naziva, a višerječne nazive zadrži.
// Neprepoznati dijelovi ostaju u tekstu; korisnik ih može urediti na popisu.
function razdvojiGlasovniPopis(tekst) {
  const poznati = [
    ...(typeof Skupine !== "undefined" ? Skupine.definicije.map((d) => d.naziv) : []),
    "sok", "crno vino", "bijelo vino", "crveno vino", "svježe mlijeko", "trajno mlijeko",
    "bijeli kruh", "crni kruh", "polubijeli kruh", "maslinovo ulje", "suncokretovo ulje",
  ].map((s) => normaliziraj(s).split(" ").map(korijen)).sort((a, b) => b.length - a.length);
  return tekst.split(/[,;.!?]|\s+(?:i|pa|te|onda)\s+/i).flatMap((dio) => {
    const rijeci = dio.trim().split(/\s+/).filter(Boolean);
    const norm = rijeci.map((r) => normaliziraj(r));
    const granice = [0];
    for (let i = 0; i < rijeci.length; i++) {
      const hit = poznati.find((p) => p.every((k, j) => norm[i+j]
        && norm[i+j].startsWith(k) && NASTAVCI.has(norm[i+j].slice(k.length))));
      if (!hit || (i && PRIJEDLOZI.has(norm[i-1]))) continue;
      let pocetak = i;
      // Količina pripada sljedećem artiklu, npr. „kruh dva mlijeka”.
      if (i && (/^\d+$/.test(norm[i-1]) || BROJEVI[norm[i-1]])) pocetak--;
      if (pocetak > granice[granice.length - 1]) granice.push(pocetak);
      i += hit.length - 1;
    }
    return granice.map((p, j) => rijeci.slice(p, granice[j+1] ?? rijeci.length).join(" ")).filter(Boolean);
  });
}

// Jedan pritisak = jedan artikl, kao prije kontinuiranog nabrajanja.
// Rezultat se odmah dodaje i sprema. Završetak nikad ne pokreće novi mikrofon.
function alternativniUnos() { $("unos").focus(); }

function pokreniSlusanje() {
  const poruka = $("glasovni-nacrt");
  const javi = (tekst) => { poruka.hidden = !tekst; poruka.textContent = tekst; };
  if (!Prepoznavanje) {
    javi("Ovaj preglednik ne podržava glasovni unos. Proizvod možeš upisati u polje ispod.");
    alternativniUnos();
    return;
  }
  if (slusac) { try { slusac.stop(); } catch (e) { slusac.onend(); } return; }
  let novi;
  try { novi = new Prepoznavanje(); }
  catch (e) { javi("Glasovni unos nije dostupan. Pokušaj ponovno ili upiši proizvod."); return; }
  slusac = novi;
  novi.lang = "hr-HR";
  novi.continuous = false;
  novi.interimResults = false;
  novi.maxAlternatives = 1;
  let dodano = false;
  let greska = false;
  const vrijedi = () => slusac === novi;
  novi.onresult = (e) => {
    if (!vrijedi() || dodano) return;
    const tekst = e.results[0][0].transcript.trim();
    if (!tekst) return;
    dodano = true;
    dodajIzTeksta(tekst);
    javi("Dodano: " + tekst + ". Za sljedeći artikl ponovno dodirni mikrofon.");
  };
  novi.onerror = (e) => {
    if (!vrijedi()) return;
    greska = true;
    const poruke = {
      "not-allowed": "Dopusti pristup mikrofonu u postavkama preglednika.",
      "audio-capture": "Mikrofon nije dostupan. Provjeri koristi li ga druga aplikacija.",
      "network": "Usluga prepoznavanja govora trenutačno nije dostupna preko mreže.",
      "no-speech": "Nije prepoznat govor. Ponovno dodirni mikrofon i reci jedan artikl.",
      "service-not-allowed": "Preglednik ne dopušta prepoznavanje govora.",
    };
    javi(poruke[e.error] || "Glasovni unos je prekinut. Pokušaj ponovno ili upiši proizvod.");
  };
  novi.onend = () => {
    if (!vrijedi()) return;
    slusac = null;
    $("mikrofon").classList.remove("slusa");
    $("mikrofon").setAttribute("aria-pressed", "false");
    $("mikrofon-tekst").textContent = "Reci jedan artikl";
    if (!dodano && !greska) javi("Nije prepoznat artikl. Ponovno dodirni mikrofon i pokušaj.");
  };
  javi("Reci jedan artikl, primjerice mlijeko. Nakon upisa ponovno dodirni mikrofon za sljedeći.");
  $("mikrofon").classList.add("slusa");
  $("mikrofon").setAttribute("aria-pressed", "true");
  $("mikrofon-tekst").textContent = "Slušam… (dodirni za kraj)";
  try { novi.start(); }
  catch (e) { greska = true; javi("Glasovni unos nije dostupan. Pokušaj ponovno ili upiši proizvod."); novi.onend(); }
}

// ---------- Prikaz ----------
function gumb(tekst, klasa, naKlik, oznaka) {
  const b = document.createElement("button");
  b.type = "button";
  b.className = klasa;
  b.textContent = tekst;
  if (oznaka) b.setAttribute("aria-label", oznaka);
  b.onclick = naKlik;
  return b;
}

function prikazi() {
  pripremiKrug();
  prikaziLokaciju();
  $("lanci-info").textContent = podaci ? `${sviLanci().size} od ${podaci.lanci.length} trgovina odabrano` : "Trgovine će se prikazati nakon učitavanja cijena.";
  prikaziPopis();
}

function prikaziPopis() {
  $("prazno").hidden = stanje.popis.length > 0;
  const n = stanje.popis.length;
  $("broj-stavki").textContent = `${n} ${n % 10 === 1 && n % 100 !== 11 ? "stavka" : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14) ? "stavke" : "stavki"}`;
  prikaziRezultate();
}

// Količina na popisu uvijek označava broj cijelih pakiranja.
// Broj komada unutar pakiranja koristi se samo za jediničnu cijenu.
// Broj pakiranja prikazane ponude. U pregledu jedne trgovine to su cijela pakiranja za barem
// referentnu količinu iz pregleda svih trgovina, kako bi iznos odgovarao usporedbi trgovina.
function brojPakiranja(stavka, p, jednaTrgovina = !!stanje.jedna) {
  if (!jednaTrgovina || !imaJedinicnu(p)) return stavka.kom;
  const ref = referentnaPonuda(stavka.naziv);
  if (!ref || !imaJedinicnu(ref) || ref.jedinica !== p.jedinica) return stavka.kom;
  return Math.ceil(podaci.proizvodi[ref.i][2] * stavka.kom / podaci.proizvodi[p.i][2] - 1e-9);
}

// Referentni artikl uvijek dolazi iz pregleda svih dopuštenih trgovina, pa odabir
// jedne trgovine ne mijenja traženu fizičku količinu.
function referentnaPonuda(grupa) {
  const sve = ponudeZaGrupu(grupa, sviLanci());
  const rb = stanje.jedna ? stanje.odabirSvi[grupa] : stanje.odabir[grupa];
  return sve[(rb || 0) % sve.length];
}

// Ponuda koju kartica prikazuje kad se otvori trgovina l: odabrana alternativa u otvorenoj
// trgovini, inače najpovoljnija po jedinici za referentnu količinu, inače prva ponuda te trgovine.
function ponudaZaLanac(stavka, l, najbolje) {
  const lista = ponudeZaGrupu(stavka.naziv, new Set([l]));
  if (!lista.length) return null;
  if (stanje.jedna === podaci.lanci[l] && stanje.odabir[stavka.naziv] !== undefined) {
    return lista[stanje.odabir[stavka.naziv] % lista.length];
  }
  const p = najbolje.get(l);
  return (p && lista.find((x) => x.i === p.i)) || lista[0];
}

// Zadani odabir kartica pri otvaranju jedne trgovine: iste ponude kao u njezinom retku usporedbe.
function odabirJedneTrgovine() {
  const l = podaci.lanci.indexOf(stanje.jedna);
  const { najboljePoStavci } = usporedbaKosarice();
  const odabir = {};
  for (const stavka of stanje.popis) {
    const lista = ponudeZaGrupu(stavka.naziv, new Set([l]));
    const p = najboljePoStavci.get(stavka.naziv)?.get(l);
    const rb = p ? lista.findIndex((x) => x.i === p.i) : -1;
    if (rb > 0) odabir[stavka.naziv] = rb;
  }
  return odabir;
}

// Sve trgovine uspoređuju istu fizičku količinu referentnih artikala.
// Količina = broj odabranih pakiranja × sadržaj pakiranja; ne zaokružuje se za usporedbu.
function usporedbaKosarice() {
  const lanci = sviLanci();
  // usporedno: jedinične cijene × referentna količina (samo usporedba, nije iznos na blagajni).
  // ukupno: zbroj kartica kad se ta trgovina otvori (cijela pakiranja); nema: bez usporedive ponude.
  const zbroj = new Map([...lanci].map((l) => [l, { usporedno: 0, ukupno: 0, nema: [], neusporedivo: [] }]));
  const najboljePoStavci = new Map();
  let najboljeMijesano = 0;
  let sveMijesanoIma = true;
  const jedinice = [];
  for (const stavka of stanje.popis) {
    const odabrana = referentnaPonuda(stavka.naziv);
    const kolicina = odabrana && imaJedinicnu(odabrana)
      ? podaci.proizvodi[odabrana.i][2] * stavka.kom : 0;
    const { najbolje, usporedi } = kolicina > 0
      ? najboljePoLancu(stavka.naziv, lanci, odabrana.jedinica, stavka)
      : { najbolje: new Map(), usporedi: () => 0 };
    najboljePoStavci.set(stavka.naziv, najbolje);
    const prva = [...najbolje.values()].sort(usporedi)[0];
    if (prva) {
      najboljeMijesano += prva.poJedinici * kolicina;
      jedinice.push(`${stavka.naziv}: ${Number(kolicina.toFixed(6)).toLocaleString("hr-HR")} ${prva.jedinica}`);
    } else sveMijesanoIma = false;
    for (const [l, z] of zbroj) {
      const p = najbolje.get(l);
      if (p) z.usporedno += p.poJedinici * kolicina;
      else z.nema.push(stavka.naziv);
      // Isti izračun kao kartica u otvorenoj trgovini, uključujući ponude bez usporedive količine.
      const kartica = ponudaZaLanac(stavka, l, najbolje);
      if (kartica && !kartica.sluzbena) {
        z.neusporedivo.push(stavka.naziv); // nepotvrđena cijena ne ulazi u zbroj lanca
      } else if (kartica) {
        z.ukupno += kartica.cijena * brojPakiranja(stavka, kartica, true);
        if (!p || kartica.i !== p.i) z.neusporedivo.push(stavka.naziv);
      }
    }
  }
  return { zbroj, najboljeMijesano, sveMijesanoIma, jedinice, najboljePoStavci };
}

function opisJedinicne(p) {
  if (!Number.isFinite(p.poJedinici) || p.poJedinici <= 0 || !["kg", "l", "kom"].includes(p.jedinica)) return "";
  return `${euro(p.poJedinici)}/${p.jedinica}`;
}

function prikaziRezultate() {
  const ul = $("kartice");
  ul.innerHTML = "";
  let ukupno = 0;
  let preostalo = 0;
  let kupljeno = 0;
  let nedostaje = 0;
  let zaProvjeru = 0;
  let nepotvrdeno = 0;
  const poLancu = {};
  const lanciOk = sviLanci().size > 0;

  $("samo-trgovina").hidden = !(podaci && dozvoljeniLanci().size === 1 && stanje.jedna);
  $("samo-trgovina-naziv").textContent = stanje.jedna || "";

  for (const [stavkaIndex, stavka] of stanje.popis.entries()) {
    const grupa = stavka.naziv;
    const li = document.createElement("li");
    li.className = "kartica";
    if (stavka.kupljeno) { li.classList.add("kupljeno"); kupljeno++; }
    const ponude = podaci && lanciOk ? ponudeZaGrupu(grupa) : [];

    const kvacica = gumb(stavka.kupljeno ? "✓" : "", "kvacica", (e) => {
      e.stopPropagation();
      stavka.kupljeno = !stavka.kupljeno;
      spremi();
      prikaziRezultate();
    }, stavka.kupljeno ? `Vrati ${grupa}` : `Stavi ${grupa} u košaricu`);
    const sadrzaj = document.createElement("div");
    sadrzaj.className = "sadrzaj";
    li.append(kvacica, sadrzaj);

    const naslov = document.createElement("div");
    naslov.className = "grupa";
    naslov.textContent = stavka.kom > 1 ? `${grupa} · ${stavka.kom} kom` : grupa;
    sadrzaj.appendChild(naslov);
    const kontrole = document.createElement("div");
    kontrole.className = "kontrole";
    const manje = gumb("−", "kolicina-gumb", () => promijeniKolicinu(stavkaIndex, -1), `Manje ${grupa}`);
    manje.disabled = stavka.kom <= 1;
    const broj = document.createElement("span");
    broj.className = "broj";
    broj.textContent = `${stavka.kom}×`;
    kontrole.append(manje, broj,
      gumb("+", "kolicina-gumb", () => promijeniKolicinu(stavkaIndex, 1), `Više ${grupa}`),
      gumb("Ukloni", "ukloni", () => ukloni(stavkaIndex), `Ukloni ${grupa}`));
    sadrzaj.appendChild(kontrole);

    if (!ponude.length) {
      nedostaje++;
      li.classList.add("nema");
      const poruka = document.createElement("div");
      poruka.className = "naziv";
      poruka.textContent = !podaci ? "Cijene još nisu učitane."
        : !lanciOk ? "Odaberi barem jednu trgovinu iznad popisa."
        : krug.stanje === "ucitava" ? "Učitavam cijene poslovnica u krugu…"
        : krug.stanje === "prazno" ? `Nedostaje: u krugu od ${stanje.radijus} km nema poslovnica s provjerenom lokacijom.`
        : krug.stanje === "greska" ? "Nedostaje: cjenici poslovnica u krugu nisu dostupni."
        : krug.stanje === "bez-koordinata" ? "Nedostaje: lokacije poslovnica nisu dostupne, krug se ne može odrediti."
        : stavka.marka ? `Nedostaje: nema ponude marke ${stavka.marka}${stanje.jedna ? ` u trgovini ${stanje.jedna}` : stanje.lokacija ? " u krugu" : " u odabranim trgovinama"}.`
        : stanje.jedna ? `Nema u trgovini ${stanje.jedna}.`
        : stanje.lokacija ? `Nedostaje: nema ponude u poslovnicama unutar ${stanje.radijus} km.`
        : "Nema pronađenih ponuda u odabranim trgovinama.";
      sadrzaj.appendChild(poruka);
      if (podaci && lanciOk && stavka.marka) sadrzaj.appendChild(kontroleMarke(stavka, null));
      ul.appendChild(li);
      continue;
    }

    const rb = (stanje.odabir[grupa] || 0) % ponude.length;
    const p = ponude[rb];
    if (p.vrstaNejasna) zaProvjeru++;
    if (!p.sluzbena) nepotvrdeno++;
    const [naziv, kolicina] = podaci.proizvodi[p.i];
    const lanac = podaci.lanci[p.lanac];
    const pakiranja = brojPakiranja(stavka, p);
    const cijena = p.cijena * pakiranja;
    ukupno += cijena;
    if (!stavka.kupljeno) preostalo += cijena;
    poLancu[lanac] = (poLancu[lanac] || 0) + 1;

    sadrzaj.insertAdjacentHTML("beforeend", `
      <div class="naziv"></div>
      <div class="redak"><span class="trgovina"></span><span class="cijena"></span></div>
      <div class="detalji"><span class="kolicina"></span><span class="mjesto"></span></div>
      <div class="detalji izvor-cijene"></div>`);
    sadrzaj.querySelector(".naziv").textContent = naziv;
    sadrzaj.querySelector(".trgovina").textContent = lanac;
    sadrzaj.querySelector(".cijena").textContent = euro(cijena);
    sadrzaj.querySelector(".kolicina").textContent = [
      pakiranja > 1 ? `${pakiranja} × ${euro(p.cijena)}` : "",
      kolicina,
      p.vrstaNejasna ? "Moguće podudaranje · vrsta za provjeru"
        : !p.sluzbena ? "Cijena nije potvrđena službenim cjenikom · bez poretka"
        : imaJedinicnu(p) ? opisJedinicne(p) : "Količina nije poznata · bez poretka po jediničnoj cijeni",
    ].filter(Boolean).join(" · ");
    const izvorCijene = sadrzaj.querySelector(".izvor-cijene");
    izvorCijene.textContent = opisIzvoraCijene(p);
    const datoteka = p.poslovnica !== null ? izvorPoslovnice(p.poslovnica) : null;
    if (datoteka && /^https?:\/\//.test(datoteka[0])) {
      const a = document.createElement("a");
      a.href = datoteka[0].split("#")[0];
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.textContent = " · otvori cjenik";
      izvorCijene.appendChild(a);
    }
    const mjesto = sadrzaj.querySelector(".mjesto");
    if (rb > 0) {
      mjesto.appendChild(gumb(`◀ ${rb + 1}. od ${ponude.length}`, "natrag", (e) => {
        e.stopPropagation();
        promijeni(grupa, -1);
      }));
    } else {
      mjesto.textContent = `${ponude.length} pronađenih proizvoda`;
    }
    const poredak = document.createElement("div");
    poredak.className = "detalji";
    if (imaJedinicnu(p)) {
      const iste = ponude.filter((x) => imaJedinicnu(x) && x.jedinica === p.jedinica);
      const redni = iste.indexOf(p) + 1;
      poredak.textContent = `${redni === 1 ? "Najpovoljnije" : `${redni}. po cijeni`} po ${p.jedinica} · ${iste.length} ponuda s tom jedinicom`;
    } else {
      poredak.textContent = p.vrstaNejasna
        ? "Provjeri odgovara li proizvod tvojem popisu. Ne proglašavamo ga najpovoljnijim."
        : !p.sluzbena ? "Cijena je iz arhive cijene.dev, nije potvrđena službenim cjenikom lanca: ne proglašavamo je najpovoljnijom."
        : "Ponuda je dostupna; povoljnost se ne može usporediti bez količine.";
    }
    sadrzaj.appendChild(poredak);
    sadrzaj.appendChild(kontroleMarke(stavka, p));
    if (ponude.length > 1) {
      sadrzaj.appendChild(gumb("Sljedeći proizvod →", "sljedeci", (e) => {
        e.stopPropagation();
        promijeni(grupa, +1);
      }, `Sljedeći proizvod za ${grupa}`));
    }
    kvacica.setAttribute("aria-pressed", String(!!stavka.kupljeno));
    ul.appendChild(li);
  }

  $("napredak").textContent = stanje.popis.length ? `U košarici: ${kupljeno} od ${stanje.popis.length}` : "";
  // Bez ijedne pronađene ponude nema iznosa (ne lažna nula).
  $("ukupno").textContent = stanje.popis.length && nedostaje === stanje.popis.length ? "—" : euro(ukupno);
  $("ukupno-oznaka").textContent = nedostaje ? "Iznos pronađenih proizvoda"
    : zaProvjeru || nepotvrdeno ? "Iznos prikazanih ponuda" : "Za plaćanje · odabrana pakiranja";
  $("nedostaje").hidden = nedostaje === 0 && zaProvjeru === 0 && nepotvrdeno === 0;
  $("nedostaje").textContent = [
    nedostaje ? `Za ${nedostaje} od ${stanje.popis.length} stavki nema cijene. Iznos ne obuhvaća cijeli popis.` : "",
    zaProvjeru ? `Za ${zaProvjeru} stavki provjeri vrstu prikazanog proizvoda prije kupnje.` : "",
    nepotvrdeno ? `Za ${nepotvrdeno} stavki cijena nije potvrđena službenim cjenikom (arhiva cijene.dev).` : "",
  ].filter(Boolean).join(" ");
  $("preostalo").hidden = kupljeno === 0 || kupljeno === stanje.popis.length;
  $("preostalo-iznos").textContent = euro(preostalo);
  $("po-trgovinama").textContent = Object.entries(poLancu)
    .sort((a, b) => b[1] - a[1])
    .map(([l, n]) => `${l}: ${n}`)
    .join(" · ");
  prikaziJednuTrgovinu();
}

// Sve u jednom dućanu: ukupan iznos cijelog popisa u svakom lancu (cijela pakiranja, iste količine i jedinice
// kao kartice tog lanca) i najpovoljnija kombinacija više lanaca. Pobijediti može samo lanac s usporedivom ponudom
// za svaku stavku; nepotpuni se prikazuju zasebno i ne pobjeđuju.
const centi = (x) => Math.round(x * 100);

function sveUJednomDucanu() {
  const { zbroj, najboljePoStavci, jedinice } = usporedbaKosarice();
  const stavki = stanje.popis.length;
  let kombinacija = 0;
  let kombinacijaNedostaje = 0;
  for (const stavka of stanje.popis) {
    const iznosi = [...(najboljePoStavci.get(stavka.naziv) || new Map()).values()]
      .map((p) => p.cijena * brojPakiranja(stavka, p, true));
    if (iznosi.length) kombinacija += Math.min(...iznosi);
    else kombinacijaNedostaje++;
  }
  const potpune = [];
  const nepotpune = [];
  for (const [l, z] of zbroj) {
    const red = { lanac: l, ime: podaci.lanci[l], ukupno: z.ukupno, pokriveno: stavki - z.nema.length, stavki,
      nedostaje: z.nema, rucniOdabir: z.neusporedivo.filter((n) => !z.nema.includes(n)) };
    if (!z.nema.length) potpune.push(red);
    else nepotpune.push(red); // i lanci bez ijedne stavke (0/Y): korisnik vidi sve odabrane lance
  }
  potpune.sort((a, b) => centi(a.ukupno) - centi(b.ukupno) || a.ime.localeCompare(b.ime, "hr"));
  nepotpune.sort((a, b) => b.pokriveno - a.pokriveno || a.ukupno - b.ukupno || a.ime.localeCompare(b.ime, "hr"));
  const najmanje = potpune.length ? centi(potpune[0].ukupno) : null;
  for (const r of potpune) {
    r.najpovoljniji = centi(r.ukupno) === najmanje; // svi izjednačeni najpovoljniji
    r.razlika = kombinacijaNedostaje ? null : (centi(r.ukupno) - centi(kombinacija)) / 100;
  }
  return { potpune, nepotpune, stavki, jedinice, kombinacija: kombinacijaNedostaje ? null : kombinacija, kombinacijaNedostaje };
}

// ---------- Stvarne poslovnice u krugu ----------
// Cijeli popis zbraja se samo unutar stvarnih poslovnica kruga, njihovim cijenama. Potpuna je samo poslovnica koja
// za svaku stavku ima usporedivu potvrđenu ponudu; bez zajedničke poslovnice cijeli popis nije košarica u jednom dućanu.
function kljucPoslovnice(idx) {
  const p = podaci.poslovnice[idx];
  return `${podaci.lanci[p[0]]}|${p[1]}`;
}

// Zračna udaljenost (haversine), km.
function udaljenostKm(lat1, lon1, lat2, lon2) {
  const r = Math.PI / 180;
  const h = Math.sin((lat2 - lat1) * r / 2) ** 2 + Math.cos(lat1 * r) * Math.cos(lat2 * r) * Math.sin((lon2 - lon1) * r / 2) ** 2;
  return 2 * 6371.0088 * Math.asin(Math.sqrt(h));
}

function kljucKruga() {
  if (!stanje.lokacija || !podaci) return "";
  return [podaci.datum, stanje.lokacija.lat, stanje.lokacija.lon, stanje.radijus, lokacije ? lokacije.size : -1, ...sviLanci()].join("|");
}

// Promjena točke, polumjera, lanaca ili cjenika: novi krug, poništeni odabiri i ponude. Odgovori starijeg kruga
// (sporo učitavanje) se odbacuju.
function pripremiKrug() {
  const kljuc = kljucKruga();
  if (kljuc === krug.kljuc) return;
  const generacija = ++generacijaKruga;
  lokalneCijene.clear();
  ponudeCache.clear();
  stanje.odabir = {};
  stanje.odabirSvi = {};
  stanje.jedna = null;
  if (!kljuc) { krug = { kljuc, stanje: "nacionalno", poslovnice: [], bezKoordinata: 0, neucitane: 0 }; return; }
  if (!lokacije) { krug = { kljuc, stanje: "bez-koordinata", poslovnice: [], bezKoordinata: 0, neucitane: 0 }; return; }
  const lanci = sviLanci();
  const { lat, lon } = stanje.lokacija;
  const unutra = [];
  let bez = 0;
  podaci.poslovnice.forEach((p, idx) => {
    if (!lanci.has(p[0])) return;
    const k = lokacije.get(kljucPoslovnice(idx));
    if (!k) { bez++; return; } // bez provjerene lokacije: nikad u krugu
    const km = udaljenostKm(lat, lon, k[0], k[1]);
    if (km <= stanje.radijus) unutra.push({ idx, km, lat: k[0], lon: k[1], osm: k[2] });
  });
  unutra.sort((a, b) => a.km - b.km || a.idx - b.idx);
  krug = { kljuc, stanje: unutra.length ? "ucitava" : "prazno", poslovnice: unutra, bezKoordinata: bez, neucitane: 0, ucitano: 0 };
  if (!unutra.length) return;
  ucitajSve(unutra.map((x) => x.idx), (n) => {
    if (generacija !== generacijaKruga) return;
    krug.ucitano = n;
    prikaziStatusKruga();
  }).then(() => {
    if (generacija !== generacijaKruga) return;
    krug.neucitane = unutra.filter((x) => !(cjeniciPoslovnica.get(x.idx) instanceof Map)).length;
    krug.stanje = krug.neucitane === unutra.length ? "greska" : "spremno";
    lokalneCijene.clear();
    ponudeCache.clear();
    prikazi();
  });
}

// Poslovnice kruga s učitanim cjenikom, od najbliže.
function odabranePoslovnice() {
  if (!podaci || krug.stanje !== "spremno") return [];
  return krug.poslovnice.map((x) => x.idx).filter((idx) => cjeniciPoslovnica.get(idx) instanceof Map);
}

const ucitavanja = new Map();
function ucitajPoslovnicu(idx) {
  if (!ucitavanja.has(idx)) {
    ucitavanja.set(idx, (async () => {
      cjeniciPoslovnica.set(idx, null);
      const datum = podaci.datum;
      try {
        const odgovor = await fetch(`data/poslovnice/${idx}.json`, { cache: "no-cache" });
        if (!odgovor.ok) throw new Error(odgovor.status);
        const d = await odgovor.json();
        // Datoteka mora pripadati istom cjeniku (isti datum i isti popis proizvoda).
        if (!podaci || podaci.datum !== datum || d.datum !== datum || d.proizvoda !== podaci.proizvodi.length) throw new Error("Zastarjelo");
        const cjenik = new Map();
        const retci = new Map();
        let i = 0;
        for (let k = 0; k < d.c.length; k += 2) {
          i += d.c[k];
          cjenik.set(i, d.c[k + 1]);
          if (Array.isArray(d.r) && Number.isInteger(d.r[k / 2])) retci.set(i, d.r[k / 2]);
        }
        cjeniciPoslovnica.set(idx, cjenik);
        retciPoslovnica.set(idx, retci);
      } catch (e) {
        cjeniciPoslovnica.set(idx, false);
        ucitavanja.delete(idx); // sljedeći krug pokušava ponovno
      }
    })());
  }
  return ucitavanja.get(idx);
}

// Najviše 6 istodobnih preuzimanja.
async function ucitajSve(idxs, napredak) {
  let sljedeci = 0;
  let gotovo = 0;
  const radnik = async () => {
    while (sljedeci < idxs.length) {
      await ucitajPoslovnicu(idxs[sljedeci++]);
      napredak(++gotovo);
    }
  };
  await Promise.all(Array.from({ length: Math.min(6, idxs.length) }, radnik));
}

// Najmanji iznos za referentnu količinu stavke u jednoj poslovnici (cijela pakiranja), samo njezinim cijenama.
function najboljaUPoslovnici(stavka, idx, cjenik, jedinica) {
  const l = podaci.poslovnice[idx][0];
  const usporedi = usporedba(jediniceGrupe(stavka.naziv));
  const trosak = (p) => centi(p.cijena * brojPakiranja(stavka, p, true));
  let naj = null;
  for (const i of pogoci(stavka.naziv)) {
    const c = cjenik.get(i);
    if (c === undefined) continue;
    const p = ponuda(i, l, c / 100, idx);
    if (!imaJedinicnu(p) || p.jedinica !== jedinica) continue;
    if (!naj || trosak(p) < trosak(naj) || (trosak(p) === trosak(naj) && usporedi(p, naj) < 0)) naj = p;
  }
  return naj;
}

// Trošak svake stavke u svakoj poslovnici kruga: centi za cijela pakiranja ili Infinity (nema potvrđene usporedive ponude).
function troskoviPoslovnica() {
  const reference = stanje.popis.map((stavka) => {
    const ref = referentnaPonuda(stavka.naziv);
    return ref && imaJedinicnu(ref) ? ref.jedinica : null;
  });
  return odabranePoslovnice().map((idx) => {
    const cjenik = cjeniciPoslovnica.get(idx);
    const ponude = stanje.popis.map((stavka, j) => (reference[j] ? najboljaUPoslovnici(stavka, idx, cjenik, reference[j]) : null));
    return { idx, ponude, v: ponude.map((p, j) => (p ? centi(p.cijena * brojPakiranja(stanje.popis[j], p, true)) : Infinity)) };
  });
}

// Točan optimum: najmanji zbroj cijelog popisa uz najviše K stvarnih poslovnica (svaka stavka u najjeftinijoj od
// odabranih). Iste ili posvuda skuplje poslovnice izbacuju se prije pretrage (ne mijenja optimum); zatim se provjere
// sve kombinacije do K poslovnica. K = Infinity: svaka stavka u najjeftinijoj poslovnici kruga.
function najboljaKombinacija(troskovi, K) {
  const n = stanje.popis.length;
  if (!n || !troskovi.length) return null;
  const vidjeno = new Set();
  let kand = troskovi.filter((r) => { const k = r.v.join(","); if (vidjeno.has(k)) return false; vidjeno.add(k); return true; });
  kand = kand.filter((a) => !kand.some((b) => b !== a && b.v.every((x, j) => x <= a.v[j])));
  const najmanje = Array.from({ length: n }, (_, j) => Math.min(...kand.map((r) => r.v[j])));
  if (najmanje.some((x) => x === Infinity)) return null; // neka stavka nema ponude ni u jednoj poslovnici
  const donja = najmanje.reduce((a, b) => a + b, 0);
  const zbroj = (skup) => {
    let z = 0;
    for (let j = 0; j < n; j++) {
      let m = Infinity;
      for (const r of skup) if (r.v[j] < m) m = r.v[j];
      if (m === Infinity) return Infinity;
      z += m;
    }
    return z;
  };
  let naj = null;
  const probaj = (skup) => {
    const z = zbroj(skup);
    if (z < Infinity && (!naj || z < naj.ukupno)) naj = { ukupno: z, skup: [...skup] };
  };
  if (K === Infinity || kand.length <= K) probaj(kand);
  else {
    const skup = [];
    const rek = (od) => {
      if (naj && naj.ukupno === donja) return; // dosegnuta donja granica: bolje ne postoji
      if (skup.length) probaj(skup);
      if (skup.length === K) return;
      for (let i = od; i < kand.length; i++) { skup.push(kand[i]); rek(i + 1); skup.pop(); }
    };
    rek(0);
  }
  if (!naj) return null;
  // Dodjela: svaka stavka u najjeftinijoj odabranoj poslovnici (kod jednakih bliža); broje se samo korištene.
  const dodjela = stanje.popis.map((_, j) => naj.skup.reduce((a, r) => (r.v[j] < a.v[j] ? r : a)));
  const koristene = [...new Set(dodjela.map((r) => r.idx))];
  return { ukupno: naj.ukupno / 100, poslovnice: koristene, dodjela: dodjela.map((r, j) => ({ idx: r.idx, p: r.ponude[j] })) };
}

function usporedbaPoslovnica() {
  const stavki = stanje.popis.length;
  const troskovi = troskoviPoslovnica();
  const km = new Map(krug.poslovnice.map((x) => [x.idx, x.km]));
  const redovi = troskovi.map((t) => {
    const red = { poslovnica: t.idx, ime: podaci.lanci[podaci.poslovnice[t.idx][0]], adresa: opisPoslovnice(t.idx), km: km.get(t.idx),
      ukupno: 0, pokriveno: 0, stavki, nedostaje: [], ucitano: true, greska: false };
    t.v.forEach((c, j) => { if (c < Infinity) { red.ukupno += c / 100; red.pokriveno++; } else red.nedostaje.push(stanje.popis[j].naziv); });
    return red;
  });
  const potpune = redovi.filter((r) => !r.nedostaje.length)
    .sort((a, b) => centi(a.ukupno) - centi(b.ukupno) || a.km - b.km || a.ime.localeCompare(b.ime, "hr"));
  const najmanje = potpune.length ? centi(potpune[0].ukupno) : null;
  for (const r of potpune) r.najpovoljnija = centi(r.ukupno) === najmanje;
  const ostale = redovi.filter((r) => !potpune.includes(r))
    .sort((a, b) => b.pokriveno - a.pokriveno || a.ukupno - b.ukupno || a.km - b.km || a.ime.localeCompare(b.ime, "hr"));
  // Sve u jednom dućanu prema najjeftinijoj kombinaciji do 2, do 3 i bez ograničenja broja poslovnica.
  const kombinacije = [2, 3, Infinity].map((K) => ({ K, rez: najboljaKombinacija(troskovi, K) }));
  return { potpune, ostale, odabrano: redovi.length, kombinacije };
}

function redPoslovnice(r) {
  const li = document.createElement("li");
  li.className = "trgovina-red poslovnica-red" + (r.najpovoljnija ? " najpovoljniji" : "") + (r.nedostaje.length ? " nepotpun" : "");
  const lijevo = document.createElement("span");
  lijevo.className = "lijevo";
  if (r.najpovoljnija) {
    const znacka = document.createElement("span");
    znacka.className = "znacka";
    znacka.textContent = "★ Najpovoljnija poslovnica";
    lijevo.appendChild(znacka);
  }
  const naziv = document.createElement("strong");
  naziv.textContent = `${nazivLanca(r.ime)} · ${r.adresa}` + (Number.isFinite(r.km) ? ` · ${opisKm(r.km)}` : "");
  const opis = document.createElement("small");
  opis.textContent = r.nedostaje.length ? `Pokriva ${r.pokriveno}/${r.stavki} · nedostaje: ${r.nedostaje.join(", ")}`
    : `Ima sve (${r.stavki}/${r.stavki}) · cijene te poslovnice, cijela pakiranja`;
  lijevo.append(naziv, opis);
  const iznos = document.createElement("span");
  iznos.className = "iznos";
  iznos.textContent = r.pokriveno ? euro(r.ukupno) : "—";
  if (r.nedostaje.length && r.pokriveno) {
    const oznaka = document.createElement("small");
    oznaka.textContent = "djelomično, nije cijeli popis";
    iznos.appendChild(oznaka);
  }
  li.append(lijevo, iznos);
  return li;
}

const opisKm = (x) => (x < 10 ? x.toFixed(1).replace(".", ",") : String(Math.round(x))) + " km";
const NAJVISE_REDOVA = 8;

function opisKombinacije(k, jedna) {
  const naslov = k.K === Infinity ? "Bez ograničenja broja dućana" : `Najviše ${k.K} dućana`;
  if (!k.rez) return { naslov, tekst: "Nema potpune kombinacije: neka stavka nema potvrđene ponude ni u jednoj poslovnici kruga." };
  const n = k.rez.poslovnice.length;
  const usteda = jedna ? (centi(jedna.ukupno) - centi(k.rez.ukupno)) / 100 : null;
  const gdje = k.rez.poslovnice.map((idx) => {
    const x = krug.poslovnice.find((y) => y.idx === idx);
    return `${nazivLanca(podaci.lanci[podaci.poslovnice[idx][0]])}, ${opisPoslovnice(idx)}${x ? ` (${opisKm(x.km)})` : ""}`;
  });
  return { naslov, iznos: k.rez.ukupno,
    tekst: `${n} ${n === 1 ? "dućan" : "dućana"} · ` + (usteda === null ? "nijedna poslovnica nema sve, ušteda se ne računa"
      : usteda > 0 ? `ušteda ${euro(usteda)} prema jednom dućanu` : "jednako jednom dućanu") + ` · ${gdje.join(" + ")}` };
}

function prikaziPoslovnice() {
  const ul = $("poslovnice-usporedba");
  const ulK = $("kombinacije");
  ul.innerHTML = "";
  ulK.innerHTML = "";
  $("nema-potpune-poslovnice").hidden = true;
  const s = krug.stanje;
  $("poslovnice-status").textContent = s === "nacionalno" ? "Odaberi lokaciju (gore) za stvarne poslovnice u krugu i iznos cijelog popisa u jednoj poslovnici."
    : s === "bez-koordinata" ? "Lokacije poslovnica trenutačno nisu dostupne: stvarne poslovnice u krugu ne mogu se odrediti."
    : s === "ucitava" ? `Učitavam cjenike poslovnica u krugu (${krug.ucitano || 0}/${krug.poslovnice.length})…`
    : s === "prazno" ? `U krugu od ${stanje.radijus} km nema poslovnica s provjerenom lokacijom. Povećaj polumjer ili pomakni točku.`
    : s === "greska" ? "Cjenici poslovnica u krugu nisu dostupni. Pokušaj ponovno kasnije."
    : "";
  if (s !== "spremno") return null;
  const rez = usporedbaPoslovnica();
  const jedna = rez.potpune[0] || null;
  for (const r of rez.potpune.slice(0, NAJVISE_REDOVA)) ul.appendChild(redPoslovnice(r));
  const ostalo = Math.max(0, NAJVISE_REDOVA - Math.min(rez.potpune.length, NAJVISE_REDOVA));
  for (const r of rez.ostale.slice(0, Math.min(ostalo, 3))) ul.appendChild(redPoslovnice(r));
  $("nema-potpune-poslovnice").hidden = rez.potpune.length > 0;
  $("poslovnice-status").textContent = `${rez.odabrano} poslovnica u krugu od ${stanje.radijus} km (zračna udaljenost)`
    + `: ${rez.potpune.length} ima cijeli popis` + (rez.potpune.length > NAJVISE_REDOVA ? `, prikazano ${NAJVISE_REDOVA} najpovoljnijih` : "")
    + (krug.neucitane ? ` · ${krug.neucitane} bez dostupnog cjenika` : "") + ". Iznos je zbroj cijena te jedne poslovnice.";
  for (const k of rez.kombinacije) {
    const o = opisKombinacije(k, jedna);
    const li = document.createElement("li");
    li.className = "trgovina-red kombinacija-red";
    const lijevo = document.createElement("span");
    lijevo.className = "lijevo";
    const naslov = document.createElement("strong");
    naslov.textContent = o.naslov;
    const opis = document.createElement("small");
    opis.textContent = o.tekst;
    lijevo.append(naslov, opis);
    const iznos = document.createElement("span");
    iznos.className = "iznos";
    iznos.textContent = o.iznos !== undefined ? euro(o.iznos) : "—";
    li.append(lijevo, iznos);
    ulK.appendChild(li);
  }
  return rez;
}

function redTrgovine(r) {
  const li = document.createElement("li");
  const b = gumb("", "trgovina-red" + (r.najpovoljniji ? " najpovoljniji" : "") + (stanje.jedna === r.ime ? " odabrana" : "")
    + (r.nedostaje.length ? " nepotpun" : ""), () => {
    if (!stanje.jedna) stanje.odabirSvi = { ...stanje.odabir };
    stanje.jedna = stanje.jedna === r.ime ? null : r.ime;
    promijeniPostavke(true);
    window.scrollTo(0, 0);
  });
  const lijevo = document.createElement("span");
  lijevo.className = "lijevo";
  if (r.najpovoljniji) {
    const znacka = document.createElement("span");
    znacka.className = "znacka";
    znacka.textContent = "★ Najniža procjena lanca";
    lijevo.appendChild(znacka);
  }
  const naziv = document.createElement("strong");
  naziv.textContent = nazivLanca(r.ime);
  const opis = document.createElement("small");
  opis.textContent = r.nedostaje.length
    ? `Pokriva ${r.pokriveno}/${r.stavki} · nedostaje: ${r.nedostaje.join(", ")}`
    : `Ima sve (${r.stavki}/${r.stavki})` + (r.razlika === null ? ""
      : r.razlika > 0 ? ` · ${euro(r.razlika)} više od najpovoljnije kombinacije` : " · jednako najpovoljnijoj kombinaciji")
      + (r.rucniOdabir.length ? ` · uključuje ručno odabrane ponude: ${r.rucniOdabir.join(", ")}` : "");
  lijevo.append(naziv, opis);
  const iznos = document.createElement("span");
  iznos.className = "iznos";
  iznos.textContent = r.pokriveno ? euro(r.ukupno) : "—";
  if (r.nedostaje.length && r.pokriveno) {
    const oznaka = document.createElement("small");
    oznaka.textContent = "djelomično, nije cijeli popis";
    iznos.appendChild(oznaka);
  }
  iznos.setAttribute("aria-label", r.nedostaje.length ? `Djelomični iznos ${euro(r.ukupno)}, nije cijeli popis`
    : `Procjena ${euro(r.ukupno)} iz različitih poslovnica lanca, nije iznos jednog dućana`);
  b.append(lijevo, iznos);
  li.appendChild(b);
  return li;
}

function prikaziJednuTrgovinu() {
  const ul = $("trgovine-usporedba");
  const ulN = $("trgovine-nepotpune");
  ul.innerHTML = "";
  ulN.innerHTML = "";
  $("jedna-trgovina").hidden = !podaci || !stanje.popis.length;
  if (!podaci || !stanje.popis.length) return null;
  const rez = sveUJednomDucanu();
  $("kombinacija").textContent = rez.kombinacija !== null
    ? `Najpovoljnija kombinacija više trgovina: ${euro(rez.kombinacija)} (svaka stavka u poslovnici s najnižom cijenom; više dućana).`
    : `Kombinacija više trgovina nije potpuna: za ${rez.kombinacijaNedostaje} od ${rez.stavki} stavki nema usporedive ponude.`;
  $("usporedne-kolicine").textContent = rez.jedinice.length ? `Iste količine u svakom lancu: ${rez.jedinice.join(" · ")}.` : "";
  $("nema-potpune").hidden = rez.potpune.length > 0;
  for (const r of rez.potpune) ul.appendChild(redTrgovine(r));
  $("nepotpune-naslov").hidden = !rez.nepotpune.length;
  for (const r of rez.nepotpune) ulN.appendChild(redTrgovine(r));
  rez.poslovnice = prikaziPoslovnice();
  return rez;
}

function promijeni(grupa, smjer) {
  const n = ponudeZaGrupu(grupa).length;
  stanje.odabir[grupa] = ((stanje.odabir[grupa] || 0) + smjer + n) % n;
  if (!stanje.jedna) stanje.odabirSvi[grupa] = stanje.odabir[grupa];
  spremi();
  prikaziRezultate();
}

// ---------- Marka ----------
// "Bilo koja marka" ili "Samo <stvarna marka iz cjenika>"; sprema se uz stavku. Nepoznata marka ne može biti filtar.
function kontroleMarke(stavka, p) {
  const div = document.createElement("div");
  div.className = "marka-odabir";
  const marka = stavka.marka || (p ? markaProizvoda(p.i) : null);
  const bilo = gumb("Bilo koja marka", "marka-gumb" + (stavka.marka ? "" : " aktivna"), () => postaviMarku(stavka, null),
    `Bilo koja marka za ${stavka.naziv}`);
  bilo.setAttribute("aria-pressed", String(!stavka.marka));
  div.appendChild(bilo);
  if (marka) {
    const samo = gumb(`Samo ${marka}`, "marka-gumb" + (stavka.marka ? " aktivna" : ""), () => postaviMarku(stavka, marka),
      `Samo marka ${marka} za ${stavka.naziv}`);
    samo.setAttribute("aria-pressed", String(!!stavka.marka));
    div.appendChild(samo);
  } else {
    const n = document.createElement("span");
    n.className = "marka-nepoznata";
    n.textContent = "Marka nije navedena u cjeniku";
    div.appendChild(n);
  }
  return div;
}

function postaviMarku(stavka, marka) {
  if (stavka.marka === marka) return;
  stavka.marka = marka;
  pogociCache.clear();
  ponudeCache.clear();
  delete stanje.odabir[stavka.naziv];
  delete stanje.odabirSvi[stavka.naziv];
  spremi();
  prikazi();
}

// ---------- Lokacija i karta ----------
// Točka se bira samo na izričit zahtjev (gumb, prijedlog, pretraga ili pomak oznake); nema praćenja u pozadini.
// Točka ostaje u ovom pregledniku; vanjskoj usluzi šalje se samo upisani tekst kad korisnik pritisne "Traži adresu".
let mjesta = null;
let karta = null;
let kartaSloj = null;
let kartaKljuc = "";
let leafletObecanje = null;
const VRSTE_MJESTA = ["grad", "grad", "selo", "dio naselja", "kvart", "zaselak"];

function postaviLokaciju(l, poruka = "") {
  stanje.lokacija = valjanaLokacija(l);
  spremi();
  $("lokacija-poruka").textContent = poruka;
  prikazi();
}

function prikaziStatusKruga() {
  const opis = $("lokacija-opis");
  if (!opis) return;
  const l = stanje.lokacija;
  $("zaboravi-lokaciju").hidden = !l;
  for (const b of document.querySelectorAll ? document.querySelectorAll("#radijus button") : []) {
    b.setAttribute("aria-pressed", String(Number(b.dataset.km) === stanje.radijus));
  }
  if (!l) {
    opis.textContent = "Bez odabrane lokacije uspoređujemo cijene cijele Hrvatske. Odaberi lokaciju za stvarne dućane u blizini.";
    return;
  }
  const n = krug.poslovnice.length;
  opis.textContent = `${l.naziv || "Odabrana točka"}${l.priblizno ? " (približno središte mjesta)" : ""} · krug ${stanje.radijus} km (zračna udaljenost): `
    + (krug.stanje === "bez-koordinata" ? "lokacije poslovnica nisu dostupne"
      : krug.stanje === "ucitava" ? `${n} poslovnica, učitavam cjenike ${krug.ucitano || 0}/${n}…`
      : krug.stanje === "prazno" ? "nema poslovnica s provjerenom lokacijom"
      : krug.stanje === "greska" ? `${n} poslovnica, cjenici nisu dostupni`
      : `${n} poslovnica s provjerenom lokacijom` + (krug.neucitane ? `, ${krug.neucitane} bez dostupnog cjenika` : ""))
    + (krug.bezKoordinata ? ` · ${krug.bezKoordinata} poslovnica odabranih lanaca nema provjerenu lokaciju i nije uključeno.` : ".");
  if (krug.stanje === "ucitava" && $("poslovnice-status")) {
    $("poslovnice-status").textContent = `Učitavam cjenike poslovnica u krugu (${krug.ucitano || 0}/${n})…`;
  }
}

function prikaziLokaciju() {
  prikaziStatusKruga();
  const div = $("karta");
  if (!div || typeof document.querySelector !== "function") return;
  div.hidden = !stanje.lokacija;
  if (stanje.lokacija) nacrtajKartu();
}

function ucitajLeaflet() {
  if (window.L) return Promise.resolve();
  if (!leafletObecanje) {
    leafletObecanje = new Promise((ok, ne) => {
      const css = document.createElement("link");
      css.rel = "stylesheet";
      css.href = "leaflet/leaflet.css";
      document.head.appendChild(css);
      const js = document.createElement("script");
      js.src = "leaflet/leaflet.js";
      js.onload = ok;
      js.onerror = () => { leafletObecanje = null; ne(new Error("Karta nije učitana")); };
      document.head.appendChild(js);
    });
  }
  return leafletObecanje;
}

async function nacrtajKartu() {
  try { await ucitajLeaflet(); }
  catch (e) { $("lokacija-poruka").textContent = "Karta se nije učitala (nema veze?). Usporedba po krugu radi i bez karte."; return; }
  const l = stanje.lokacija;
  if (!l) return;
  if (!karta) {
    karta = L.map("karta", { zoomControl: true, attributionControl: true });
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> suradnici',
    }).addTo(karta);
    kartaSloj = L.layerGroup().addTo(karta);
    // Dodir na kartu premješta točku (potvrda mjesta).
    karta.on("click", (e) => postaviLokaciju({ lat: +e.latlng.lat.toFixed(5), lon: +e.latlng.lng.toFixed(5), naziv: "Točka na karti", priblizno: false },
      "Točka je premještena. Krug i cijene su preračunati."));
  }
  const kljuc = [l.lat, l.lon, stanje.radijus, krug.kljuc, krug.stanje].join("|");
  if (kljuc === kartaKljuc) return;
  const prvi = !kartaKljuc;
  kartaKljuc = kljuc;
  kartaSloj.clearLayers();
  const krugSloj = L.circle([l.lat, l.lon], { radius: stanje.radijus * 1000, color: "#2f6fb3", weight: 2, fillOpacity: 0.07 }).addTo(kartaSloj);
  const oznaka = L.marker([l.lat, l.lon], { draggable: true, keyboard: true, title: "Tvoja točka (povuci za pomak)", alt: "Tvoja točka" }).addTo(kartaSloj);
  oznaka.on("dragend", () => {
    const t = oznaka.getLatLng();
    postaviLokaciju({ lat: +t.lat.toFixed(5), lon: +t.lng.toFixed(5), naziv: "Točka na karti", priblizno: false },
      "Točka je premještena. Krug i cijene su preračunati.");
  });
  for (const x of krug.poslovnice) {
    const p = podaci.poslovnice[x.idx];
    L.circleMarker([x.lat, x.lon], { radius: 6, color: "#b8551f", weight: 2, fillColor: "#f2a65a", fillOpacity: 0.9 })
      .bindPopup(`${nazivLanca(podaci.lanci[p[0]])}<br>${opisPoslovnice(x.idx).replace(/[<>&]/g, "")}<br>${opisKm(x.km)} zračne udaljenosti`)
      .addTo(kartaSloj);
  }
  if (prvi || !karta.getBounds().contains(krugSloj.getBounds())) karta.fitBounds(krugSloj.getBounds(), { padding: [12, 12] });
  setTimeout(() => karta.invalidateSize(), 0);
}

function koristiMojuLokaciju() {
  const poruka = $("lokacija-poruka");
  if (!navigator.geolocation || !window.isSecureContext) {
    poruka.textContent = "Ovaj preglednik ne daje lokaciju. Upiši mjesto ili adresu.";
    $("adresa").focus();
    return;
  }
  poruka.textContent = "Tražim tvoju lokaciju…";
  navigator.geolocation.getCurrentPosition(
    (pol) => postaviLokaciju({ lat: +pol.coords.latitude.toFixed(5), lon: +pol.coords.longitude.toFixed(5), naziv: "Moja lokacija",
      priblizno: pol.coords.accuracy > 500 }, `Lokacija pronađena (točnost oko ${Math.round(pol.coords.accuracy)} m). Po potrebi povuci oznaku na karti.`),
    (e) => {
      poruka.textContent = e.code === 1 ? "Pristup lokaciji je odbijen. Upiši mjesto ili adresu ispod."
        : e.code === 3 ? "Lokacija nije pronađena na vrijeme. Pokušaj ponovno ili upiši mjesto ili adresu."
        : "Lokacija trenutačno nije dostupna. Upiši mjesto ili adresu.";
      $("adresa").focus();
    },
    { enableHighAccuracy: false, timeout: 15000, maximumAge: 60000 });
}

async function ucitajMjesta() {
  if (mjesta) return mjesta;
  try {
    const o = await fetch("data/mjesta.json", { cache: "no-cache" });
    if (!o.ok) throw new Error(o.status);
    const d = await o.json();
    mjesta = (Array.isArray(d.mjesta) ? d.mjesta : []).map((m) => ({ naziv: m[0], lat: m[1], lon: m[2], vrsta: m[3], kraj: m[4] || "",
      n: normaliziraj(String(m[0])) }));
  } catch (e) { mjesta = null; }
  return mjesta;
}

// Prijedlozi iz lokalnog popisa naselja (bez slanja upisa ikamo): početak naziva, pa početak riječi, pa dio naziva.
function prijedloziMjesta(upit) {
  const q = normaliziraj(upit);
  if (!mjesta || q.length < 2) return [];
  const rang = (m) => (m.n.startsWith(q) ? 0 : m.n.split(" ").some((w) => w.startsWith(q)) ? 1 : m.n.includes(q) ? 2 : 9);
  return mjesta.map((m) => [rang(m), m]).filter(([r]) => r < 9)
    .sort((a, b) => a[0] - b[0] || a[1].vrsta - b[1].vrsta || a[1].n.length - b[1].n.length || a[1].n.localeCompare(b[1].n))
    .slice(0, 8).map(([, m]) => ({ naziv: m.naziv, opis: [VRSTE_MJESTA[m.vrsta] || "mjesto", m.kraj ? `kraj: ${m.kraj}` : ""].filter(Boolean).join(" · "),
      lat: m.lat, lon: m.lon, priblizno: true }));
}

let prijedlozi = [];
let aktivniPrijedlog = -1;
function prikaziPrijedloge(lista, prazno = "") {
  prijedlozi = lista;
  aktivniPrijedlog = -1;
  const ul = $("prijedlozi");
  ul.innerHTML = "";
  lista.forEach((x, k) => {
    const li = document.createElement("li");
    li.id = `prijedlog-${k}`;
    li.setAttribute("role", "option");
    li.textContent = x.naziv;
    if (x.opis) {
      const s = document.createElement("small");
      s.textContent = ` · ${x.opis}`;
      li.appendChild(s);
    }
    li.onmousedown = (e) => { e.preventDefault(); odaberiPrijedlog(k); };
    ul.appendChild(li);
  });
  if (!lista.length && prazno) {
    const li = document.createElement("li");
    li.className = "prijedlog-prazno";
    li.textContent = prazno;
    ul.appendChild(li);
  }
  ul.hidden = !lista.length && !prazno;
  $("adresa").setAttribute("aria-expanded", String(!ul.hidden));
}

function odaberiPrijedlog(k) {
  const x = prijedlozi[k];
  if (!x) return;
  $("adresa").value = x.naziv;
  prikaziPrijedloge([]);
  postaviLokaciju({ lat: x.lat, lon: x.lon, naziv: x.naziv, priblizno: x.priblizno },
    x.priblizno ? `${x.naziv}: približno središte. Provjeri točku na karti i povuci oznaku na točnu adresu.`
      : `${x.naziv}. Provjeri točku na karti; oznaku možeš povući.`);
}

// Pretraga adrese (ulica i broj) samo na izričit pritisak: jedan upit javnom Nominatimu (OpenStreetMap), najviše
// jedan u sekundi, bez automatskog dovršavanja dok se tipka (pravila korištenja to ne dopuštaju).
let zadnjaPretraga = 0;
async function traziAdresu() {
  const upit = $("adresa").value.trim();
  const poruka = $("lokacija-poruka");
  if (upit.length < 3) { poruka.textContent = "Upiši barem 3 slova mjesta ili adrese."; return; }
  if (Date.now() - zadnjaPretraga < 1100) return;
  zadnjaPretraga = Date.now();
  const gumbT = $("trazi-adresu");
  gumbT.disabled = true;
  poruka.textContent = "Tražim adresu (OpenStreetMap Nominatim)…";
  try {
    const url = "https://nominatim.openstreetmap.org/search?format=jsonv2&countrycodes=hr&limit=6&accept-language=hr&q=" + encodeURIComponent(upit);
    const o = await fetch(url, { headers: { Accept: "application/json" }, referrerPolicy: "strict-origin-when-cross-origin" });
    if (!o.ok) throw new Error(o.status);
    const rez = (await o.json()).filter((x) => Number.isFinite(+x.lat) && Number.isFinite(+x.lon)).map((x) => ({
      naziv: String(x.display_name || upit).split(",").slice(0, 3).join(","), opis: x.addresstype || x.type || "",
      lat: +(+x.lat).toFixed(5), lon: +(+x.lon).toFixed(5),
      priblizno: !["house", "building", "shop", "amenity"].includes(x.addresstype || x.category) && !(x.address && x.address.house_number) }));
    poruka.textContent = rez.length ? "Odaberi pronađenu adresu, zatim provjeri točku na karti." : "";
    prikaziPrijedloge(rez, "Adresa nije pronađena. Upiši mjesto pa povuci oznaku na karti.");
  } catch (e) {
    poruka.textContent = "Pretraga adrese trenutačno nije dostupna. Odaberi mjesto s popisa prijedloga ili koristi svoju lokaciju.";
  } finally {
    gumbT.disabled = false;
  }
}

// ---------- Postavke ----------
// Izričit korisnički prioritet za hrvatsko tržište; nije rang po broju poslovnica.
const REDOSLIJED_LANACA = ["Konzum", "Lidl", "Plodine", "Kaufland", "NTL", "Eurospin", "Spar"];
// Posljednji dostupni objavljeni brojevi; izvori i ograničenja u docs/redoslijed-lanaca.md.
// null/odsutan broj nije nula: takav lanac ostaje dostupan na kraju.
const BROJ_POSLOVNICA = {
  "Studenac": 1165, "Trgovina Krk": 417, "Tommy": 244, "Boso": 230,
  "dm": 180, "Ribola": 98, "Trgocentar": 90, "Stridon": 43,
  "Djelo Vodice": 33, "KTC": 30, "Roto": 26, "Jadranka": 20,
  "Žabac": 8, "Vrutak": 8, "Dukat": 6, "Bure": 3, "Branka": 2,
};
function nazivLanca(ime) { return ime === "Spar" ? "SPAR / INTERSPAR" : ime; }
function redoslijedLanaca(lanci) {
  const prioritet = (ime) => {
    const i = REDOSLIJED_LANACA.indexOf(ime);
    return i < 0 ? REDOSLIJED_LANACA.length : i;
  };
  // Sortira se kopija: izvorni indeksi cijena ostaju nepromijenjeni.
  return [...lanci].sort((a, b) => {
    const red = prioritet(a) - prioritet(b);
    if (red || prioritet(a) < REDOSLIJED_LANACA.length) return red;
    const brojA = BROJ_POSLOVNICA[a], brojB = BROJ_POSLOVNICA[b];
    if (brojA === undefined || brojB === undefined) return Number(brojA === undefined) - Number(brojB === undefined);
    return brojB - brojA;
  });
}
function prikaziPostavke() {
  for (const r of document.querySelectorAll('input[name="nacin"]')) r.checked = r.value === stanje.nacin;
  const div = $("lanci");
  div.innerHTML = "";
  if (!podaci) return;
  const iskljuceni = new Set(stanje.iskljuceni);
  redoslijedLanaca(podaci.lanci).forEach((ime) => {
    const label = document.createElement("label");
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = !iskljuceni.has(ime);
    cb.onchange = () => {
      stanje.iskljuceni = cb.checked
        ? stanje.iskljuceni.filter((x) => x !== ime)
        : [...stanje.iskljuceni, ime];
      if (!cb.checked && stanje.jedna === ime) stanje.jedna = null;
      promijeniPostavke();
    };
    label.append(cb, " " + nazivLanca(ime));
    div.appendChild(label);
  });
}

for (const r of document.querySelectorAll('input[name="nacin"]')) {
  r.onchange = () => { stanje.nacin = r.value; promijeniPostavke(); };
}
$("lanci-sve").onclick = () => { stanje.iskljuceni = []; prikaziPostavke(); promijeniPostavke(); };
$("lanci-nista").onclick = () => {
  stanje.iskljuceni = podaci ? [...podaci.lanci] : [];
  stanje.jedna = null;
  prikaziPostavke();
  promijeniPostavke();
};


// ---------- Gumbi ----------
$("ponovi").onclick = ucitajPodatke;
$("mikrofon").onclick = pokreniSlusanje;
$("rucni-unos").onsubmit = (e) => {
  e.preventDefault();
  const tekst = $("unos").value.trim();
  if (tekst) dodajIzTeksta(razdvojiGlasovniPopis(tekst).join(", "));
  $("unos").value = "";
};
$("samo-trgovina-makni").onclick = () => {
  stanje.jedna = null;
  promijeniPostavke(true);
};

$("moja-lokacija").onclick = koristiMojuLokaciju;
$("zaboravi-lokaciju").onclick = () => postaviLokaciju(null, "Uspoređujemo cijene cijele Hrvatske.");
for (const b of document.querySelectorAll("#radijus button")) {
  b.onclick = () => {
    stanje.radijus = Number(b.dataset.km);
    spremi();
    prikazi();
  };
}
$("adresa").addEventListener("focus", ucitajMjesta, { once: true });
$("adresa").addEventListener("input", async () => {
  const upit = $("adresa").value;
  await ucitajMjesta();
  if ($("adresa").value === upit) prikaziPrijedloge(prijedloziMjesta(upit), normaliziraj(upit).length >= 2 && mjesta
    ? "Nema takvog naselja na popisu. Pritisni „Traži adresu” za ulicu i broj." : "");
});
$("adresa").addEventListener("keydown", (e) => {
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    if (!prijedlozi.length) return;
    e.preventDefault();
    aktivniPrijedlog = (aktivniPrijedlog + (e.key === "ArrowDown" ? 1 : -1) + prijedlozi.length) % prijedlozi.length;
    [...$("prijedlozi").children].forEach((li, k) => li.setAttribute("aria-selected", String(k === aktivniPrijedlog)));
    $("adresa").setAttribute("aria-activedescendant", `prijedlog-${aktivniPrijedlog}`);
  } else if (e.key === "Escape") prikaziPrijedloge([]);
});
$("adresa").addEventListener("blur", () => setTimeout(() => prikaziPrijedloge([]), 150));
$("adresa-forma").onsubmit = (e) => {
  e.preventDefault();
  if (aktivniPrijedlog >= 0) odaberiPrijedlog(aktivniPrijedlog);
  else traziAdresu();
};

prikaziPostavke();
prikazi();
ucitajPodatke();

if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});



