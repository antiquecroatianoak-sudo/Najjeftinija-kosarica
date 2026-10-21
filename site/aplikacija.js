"use strict";

// ---------- Stanje aplikacije (sprema se u mobitel) ----------
const SPREMISTE = "kosarica-v1";
let stanje = {
  popis: [],          // [{ naziv, kom, kupljeno }]
  zakljucano: false,
  odabir: {},         // grupa -> redni broj ponude
  odabirSvi: {},      // odabir iz pregleda svih trgovina; referentna količina za usporedbu
  nacin: "jedinica",  // Poredak uvijek određuje jedinična cijena.
  iskljuceni: [],     // nazivi lanaca koji korisniku ne odgovaraju
  jedna: null,        // naziv lanca ako se kupuje sve u jednoj trgovini
  grad: "",           // grad za odabir stvarnih poslovnica
  poslovnice: [],     // odabrane stvarne poslovnice: "Lanac|store_id"
};
try { Object.assign(stanje, JSON.parse(localStorage.getItem(SPREMISTE)) || {}); } catch (e) {}
// Starija verzija je spremala popis kao obične tekstove.
stanje.popis = (Array.isArray(stanje.popis) ? stanje.popis : [])
  .map((s) => typeof s === "string" ? { naziv: s, kom: 1, kupljeno: false } : s)
  .filter((s) => s && typeof s.naziv === "string" && s.naziv.trim())
  .map((s) => ({ naziv: s.naziv, kom: Math.min(99, Math.max(1, Math.floor(Number(s.kom) || 1))), kupljeno: !!s.kupljeno }));
stanje.iskljuceni = Array.isArray(stanje.iskljuceni) ? stanje.iskljuceni : [];
stanje.odabir = stanje.odabir && typeof stanje.odabir === "object" ? stanje.odabir : {};
stanje.nacin = "jedinica";
// Svako otvaranje započinje usporedbom svih lanaca.
stanje.iskljuceni = [];
stanje.jedna = null;
stanje.odabir = {};
stanje.odabirSvi = {};
stanje.grad = typeof stanje.grad === "string" ? stanje.grad : "";
stanje.poslovnice = Array.isArray(stanje.poslovnice) ? stanje.poslovnice.filter((x) => typeof x === "string") : [];
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
const cjeniciPoslovnica = new Map();  // poslovnica -> Map(proizvod -> cijena u centima), ili null dok se učitava

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
      return [...p.slice(0, 5), cijene, ponude];
    });
    if (!podaci.proizvodi.some((p) => p[5].length)) throw new Error("Nema valjanih cijena");
    podaci.poslovnice = Array.isArray(podaci.poslovnice) ? podaci.poslovnice : [];
    cjeniciPoslovnica.clear();
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
    ucitajOdabranePoslovnice();
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
// Indeksi proizvoda koji odgovaraju grupi (npr. "mlijeko").
function pogoci(grupa) {
  if (pogociCache.has(grupa)) return pogociCache.get(grupa);
  if (klasifikacija) {
    const prepoznati = klasifikacija.pogoci(grupa);
    if (prepoznati !== null) {
      const rezultat = [...prepoznati, ...klasifikacija.moguciPogoci(grupa)];
      pogociCache.set(grupa, rezultat);
      return rezultat;
    }
  }
  const korijeni = normaliziraj(grupa).split(" ").filter(Boolean).map(korijen);
  let rezultat = [];
  if (korijeni.length) {
    rezultat = trazi(korijeni, (w, k) => w.startsWith(k) && NASTAVCI.has(w.slice(k.length)));
    if (!rezultat.length) rezultat = trazi(korijeni, (w, k) => w.startsWith(k));
  }
  pogociCache.set(grupa, rezultat);
  return rezultat;
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

// Ponuda nosi stvarnu poslovnicu čija je to cijena (ili zadanu poslovnicu kad se zbraja jedna poslovnica).
function ponuda(i, lanac, cijena, poslovnica = null) {
  const [, , iznos, jedinica, , cijene, ponude] = podaci.proizvodi[i];
  let meta = null;
  if (poslovnica === null && ponude) {
    for (let k = 0; k < cijene.length; k += 2) if (cijene[k] === lanac) { meta = ponude[k / 2]; break; }
  }
  return { i, lanac, cijena, jedinica, poJedinici: iznos ? cijena / iznos : null,
    poslovnica: poslovnica !== null ? poslovnica : meta ? meta[0] : null,
    brojPoslovnica: meta ? meta[1] : null, najvisa: meta ? meta[2] : null, akcija: !!(meta && meta[3]),
    redak: meta && Number.isInteger(meta[4]) ? meta[4] : null, nazivAkcije: meta && meta[5] ? meta[5] : "",
    vrstaNejasna: !!klasifikacija && !klasifikacija.vrstaProizvoda(i) };
}

// [URL službene datoteke, datum] iz koje su cijene poslovnice, ili null (arhiva cijene.dev).
function izvorPoslovnice(idx) {
  const p = podaci && (podaci.poslovnice || [])[idx];
  const i = p && Number.isInteger(p[4]) ? p[4] : -1;
  return i >= 0 && Array.isArray(podaci.izvori) ? podaci.izvori[i] || null : null;
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

function imaJedinicnu(p) {
  return !p.vrstaNejasna && Number.isFinite(p.poJedinici) && p.poJedinici > 0 && ["kg", "l", "kom"].includes(p.jedinica);
}

// Različite jedinice ne smiju sakriti cijelu skupinu niti se uspoređivati brojčano.
// Najzastupljenija jedinica ide prva; sve druge i nepoznate količine ostaju dostupne.
function jediniceGrupe(grupa) {
  const broj = new Map();
  for (const i of pogoci(grupa)) {
    const p = ponuda(i, 0, 1);
    if (imaJedinicnu(p)) broj.set(p.jedinica, (broj.get(p.jedinica) || 0) + 1);
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
  const kljuc = grupa + "|" + [...lanci].join(",");
  if (ponudeCache.has(kljuc)) return ponudeCache.get(kljuc);
  const ponude = [];
  for (const i of pogoci(grupa)) {
    const cijene = podaci.proizvodi[i][5];
    let najjeftinija = null;
    for (let k = 0; k < cijene.length; k += 2) {
      if (lanci.has(cijene[k]) && (!najjeftinija || cijene[k + 1] < najjeftinija.cijena)) {
        najjeftinija = ponuda(i, cijene[k], cijene[k + 1]);
      }
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
    const cijene = podaci.proizvodi[i][5];
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
      if (kartica) {
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
        : stanje.jedna ? `Nema u trgovini ${stanje.jedna}.`
        : "Nema pronađenih ponuda u odabranim trgovinama.";
      sadrzaj.appendChild(poruka);
      ul.appendChild(li);
      continue;
    }

    const rb = (stanje.odabir[grupa] || 0) % ponude.length;
    const p = ponude[rb];
    if (p.vrstaNejasna) zaProvjeru++;
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
        : "Ponuda je dostupna; povoljnost se ne može usporediti bez količine.";
    }
    sadrzaj.appendChild(poredak);
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
  $("ukupno").textContent = euro(ukupno);
  $("ukupno-oznaka").textContent = nedostaje ? "Iznos pronađenih proizvoda" : zaProvjeru ? "Iznos prikazanih ponuda" : "Za plaćanje · odabrana pakiranja";
  $("nedostaje").hidden = nedostaje === 0 && zaProvjeru === 0;
  $("nedostaje").textContent = [
    nedostaje ? `Za ${nedostaje} od ${stanje.popis.length} stavki nema cijene. Iznos ne obuhvaća cijeli popis.` : "",
    zaProvjeru ? `Za ${zaProvjeru} stavki provjeri vrstu prikazanog proizvoda prije kupnje.` : "",
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

// ---------- Stvarne poslovnice ----------
// Cijeli popis zbraja se samo unutar jedne stvarne poslovnice, njezinim cijenama. Potpuna je samo poslovnica koja
// za svaku stavku ima usporedivu ponudu; bez zajedničke poslovnice cijeli popis nije košarica u jednom dućanu.
function kljucPoslovnice(idx) {
  const p = podaci.poslovnice[idx];
  return `${podaci.lanci[p[0]]}|${p[1]}`;
}

function odabranePoslovnice() {
  if (!podaci) return [];
  const trazene = new Set(stanje.poslovnice);
  const lanci = sviLanci();
  return (podaci.poslovnice || []).map((_, idx) => idx)
    .filter((idx) => trazene.has(kljucPoslovnice(idx)) && lanci.has(podaci.poslovnice[idx][0]));
}

async function ucitajPoslovnicu(idx) {
  if (cjeniciPoslovnica.has(idx)) return;
  cjeniciPoslovnica.set(idx, null);
  const datum = podaci.datum;
  try {
    const odgovor = await fetch(`data/poslovnice/${idx}.json`, { cache: "no-cache" });
    if (!odgovor.ok) throw new Error(odgovor.status);
    const d = await odgovor.json();
    // Datoteka mora pripadati istom cjeniku (isti datum i isti popis proizvoda).
    if (!podaci || podaci.datum !== datum || d.datum !== datum || d.proizvoda !== podaci.proizvodi.length) throw new Error("Zastarjelo");
    const cjenik = new Map();
    let i = 0;
    for (let k = 0; k < d.c.length; k += 2) { i += d.c[k]; cjenik.set(i, d.c[k + 1]); }
    cjeniciPoslovnica.set(idx, cjenik);
  } catch (e) {
    cjeniciPoslovnica.set(idx, false);
  }
}

function ucitajOdabranePoslovnice() {
  const cekaju = odabranePoslovnice().filter((idx) => !cjeniciPoslovnica.has(idx));
  if (!cekaju.length) return Promise.resolve();
  return Promise.all(cekaju.map(ucitajPoslovnicu)).then(() => prikaziJednuTrgovinu());
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

function usporedbaPoslovnica() {
  const redovi = [];
  const stavki = stanje.popis.length;
  for (const idx of odabranePoslovnice()) {
    const cjenik = cjeniciPoslovnica.get(idx);
    const red = { poslovnica: idx, ime: podaci.lanci[podaci.poslovnice[idx][0]], adresa: opisPoslovnice(idx),
      ukupno: 0, pokriveno: 0, stavki, nedostaje: [], ucitano: cjenik instanceof Map, greska: cjenik === false };
    if (red.ucitano) {
      for (const stavka of stanje.popis) {
        const ref = referentnaPonuda(stavka.naziv);
        const p = ref && imaJedinicnu(ref) ? najboljaUPoslovnici(stavka, idx, cjenik, ref.jedinica) : null;
        if (p) { red.ukupno += p.cijena * brojPakiranja(stavka, p, true); red.pokriveno++; }
        else red.nedostaje.push(stavka.naziv);
      }
    }
    redovi.push(red);
  }
  const potpune = redovi.filter((r) => r.ucitano && !r.nedostaje.length)
    .sort((a, b) => centi(a.ukupno) - centi(b.ukupno) || a.ime.localeCompare(b.ime, "hr"));
  const najmanje = potpune.length ? centi(potpune[0].ukupno) : null;
  for (const r of potpune) r.najpovoljnija = centi(r.ukupno) === najmanje;
  const ostale = redovi.filter((r) => !potpune.includes(r))
    .sort((a, b) => b.pokriveno - a.pokriveno || a.ukupno - b.ukupno || a.ime.localeCompare(b.ime, "hr"));
  return { potpune, ostale, odabrano: redovi.length };
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
  naziv.textContent = `${nazivLanca(r.ime)} · ${r.adresa}`;
  const opis = document.createElement("small");
  opis.textContent = r.greska ? "Cijene ove poslovnice nisu dostupne za današnji cjenik."
    : !r.ucitano ? "Učitavam cijene poslovnice…"
    : r.nedostaje.length ? `Pokriva ${r.pokriveno}/${r.stavki} · nedostaje: ${r.nedostaje.join(", ")}`
    : `Ima sve (${r.stavki}/${r.stavki}) · cijene te poslovnice, cijela pakiranja`;
  lijevo.append(naziv, opis);
  const iznos = document.createElement("span");
  iznos.className = "iznos";
  iznos.textContent = r.ucitano && r.pokriveno ? euro(r.ukupno) : "—";
  if (r.ucitano && r.nedostaje.length && r.pokriveno) {
    const oznaka = document.createElement("small");
    oznaka.textContent = "djelomično, nije cijeli popis";
    iznos.appendChild(oznaka);
  }
  li.append(lijevo, iznos);
  return li;
}

// Popis se gradi ponovno samo kad se promijeni cjenik, grad ili dopušteni lanci (fokus i odabir ostaju).
let potpisOdabira = "";
function prikaziOdabirPoslovnica() {
  const sel = $("grad");
  const div = $("poslovnice-popis");
  if (!sel || !podaci) return;
  const lanci = sviLanci();
  const potpis = [podaci.datum, stanje.grad, ...lanci].join("|");
  if (potpis === potpisOdabira) return;
  potpisOdabira = potpis;
  const gradovi = [...new Set((podaci.poslovnice || []).filter((p) => lanci.has(p[0]) && p[3]).map((p) => p[3]))]
    .sort((a, b) => a.localeCompare(b, "hr"));
  sel.innerHTML = "";
  const prazno = document.createElement("option");
  prazno.value = "";
  prazno.textContent = "Odaberi grad";
  sel.appendChild(prazno);
  for (const g of gradovi) {
    const o = document.createElement("option");
    o.value = g;
    o.textContent = g;
    sel.appendChild(o);
  }
  sel.value = gradovi.includes(stanje.grad) ? stanje.grad : "";
  div.innerHTML = "";
  const odabrane = new Set(stanje.poslovnice);
  (podaci.poslovnice || []).forEach((p, idx) => {
    if (!sel.value || p[3] !== sel.value || !lanci.has(p[0])) return;
    const kljuc = kljucPoslovnice(idx);
    const label = document.createElement("label");
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = odabrane.has(kljuc);
    cb.onchange = () => {
      stanje.poslovnice = cb.checked ? [...new Set([...stanje.poslovnice, kljuc])] : stanje.poslovnice.filter((x) => x !== kljuc);
      spremi();
      ucitajOdabranePoslovnice();
      prikaziJednuTrgovinu();
    };
    label.append(cb, ` ${nazivLanca(podaci.lanci[p[0]])} · ${p[2] || p[1]}`);
    div.appendChild(label);
  });
}

function prikaziPoslovnice() {
  const ul = $("poslovnice-usporedba");
  if (!ul) return null;
  ul.innerHTML = "";
  const rez = usporedbaPoslovnica();
  for (const r of [...rez.potpune, ...rez.ostale]) ul.appendChild(redPoslovnice(r));
  const ucitane = rez.ostale.every((r) => r.ucitano || r.greska);
  $("nema-potpune-poslovnice").hidden = !rez.odabrano || rez.potpune.length > 0 || !ucitane;
  $("poslovnice-status").textContent = rez.odabrano
    ? `Odabrano poslovnica: ${rez.odabrano}. Iznos je zbroj cijena te jedne poslovnice za cijeli popis.`
    : "Odaberi grad i poslovnice za stvarni iznos cijelog popisa u jednoj poslovnici.";
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
  prikaziOdabirPoslovnica();
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

if ($("grad")) $("grad").onchange = () => { stanje.grad = $("grad").value; spremi(); prikaziOdabirPoslovnica(); };

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

prikaziPostavke();
prikazi();
ucitajPodatke();

if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});



