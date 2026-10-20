"use strict";

// ---------- Stanje aplikacije (sprema se u mobitel) ----------
const SPREMISTE = "kosarica-v1";
let stanje = {
  popis: [],          // [{ naziv, kom, kupljeno }]
  zakljucano: false,
  odabir: {},         // grupa -> redni broj ponude
  nacin: "jedinica",  // Poredak uvijek određuje jedinična cijena.
  iskljuceni: [],     // nazivi lanaca koji korisniku ne odgovaraju
  jedna: null,        // naziv lanca ako se kupuje sve u jednoj trgovini
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
function spremi() {
  try { localStorage.setItem(SPREMISTE, JSON.stringify(stanje)); } catch (e) {}
}

// ---------- Podaci o cijenama ----------
// { datum, lanci: [...], proizvodi: [[naziv, količina, iznos, jedinica, riječi marke, [lanac, cijena, ...]], ...] }
let podaci = null;
let klasifikacija = null;
let rijeci = [];       // za svaki proizvod: normalizirane riječi naziva
const pogociCache = new Map();
const ponudeCache = new Map();

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
    // Zaštita i za stare/offline cjenike: ne prikazuj ponude od jednog centa.
    podaci.proizvodi = podaci.proizvodi.map((p) => {
      const cijene = [];
      for (let k = 0; k < p[5].length; k += 2) {
        const c = p[5][k + 1];
        if (typeof c === "number" && Number.isFinite(c) && Math.round(c * 100) > 1) {
          cijene.push(p[5][k], c);
        }
      }
      return [...p.slice(0, 5), cijene];
    }).filter((p) => p[5].length);
    if (!podaci.proizvodi.length) throw new Error("Nema valjanih cijena");
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
      `Cijene od ${d}.${m}.${g}. · ${podaci.proizvodi.length.toLocaleString("hr-HR")} proizvoda · ${podaci.lanci.length} lanaca`;
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

function ponuda(i, lanac, cijena) {
  const [, , iznos, jedinica] = podaci.proizvodi[i];
  return { i, lanac, cijena, jedinica, poJedinici: iznos ? cijena / iznos : null,
    vrstaNejasna: !!klasifikacija && !klasifikacija.vrstaProizvoda(i) };
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
function ponudeZaGrupu(grupa) {
  if (ponudeCache.has(grupa)) return ponudeCache.get(grupa);
  const lanci = dozvoljeniLanci();
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
  ponudeCache.set(grupa, ponude);
  return ponude;
}

// Za "sve u jednoj trgovini": najbolja ponuda za grupu u svakom lancu.
function najboljePoLancu(grupa, lanci, trazenaJedinica = null) {
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
  for (const p of sve.filter((p) => imaJedinicnu(p) && p.jedinica === jedinica)) {
    const dosad = najbolje.get(p.lanac);
    if (!dosad || usporedi(p, dosad) < 0) najbolje.set(p.lanac, p);
  }
  return { najbolje, usporedi };
}

function promijeniPostavke() {
  ponudeCache.clear();
  stanje.odabir = {};
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
let glasovniUnos = null;

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

// Natpis prati potvrđene događaje, a svaki pokušaj ima vremensko ograničenje.
let glasovnaPoruka = "";
function prikaziGlasovniUnos() {
  const sesija = glasovniUnos;
  const aktivan = !!sesija;
  $("mikrofon").classList.toggle("slusa", !!sesija?.snima);
  $("mikrofon").setAttribute("aria-pressed", String(aktivan));
  $("mikrofon-tekst").textContent = !aktivan ? "Reci što trebaš kupiti"
    : !sesija.aktivan ? "Dovršavam popis…"
    : sesija.snima ? "Nabrajaj… dodirni za kraj" : "Pokrećem mikrofon… dodirni za odustajanje";
  const nacrt = $("glasovni-nacrt");
  nacrt.hidden = !aktivan && !glasovnaPoruka;
  nacrt.textContent = aktivan
    ? [sesija.tekst, sesija.trenutni].filter(Boolean).join(" ")
      || (sesija.snima ? "Mikrofon je uključen. Nabroji proizvode."
        : "Čekam pokretanje mikrofona. Ako se pojavi zahtjev, dopusti pristup.")
    : glasovnaPoruka;
}

function pocistiGlasovneTimere(sesija) {
  for (const kljuc of ["timer", "pokretanje", "bezRezultata", "zavrsetak"]) {
    clearTimeout(sesija[kljuc]);
    sesija[kljuc] = null;
  }
}

function dovrsiGlasovniUnos(sesija) {
  if (glasovniUnos !== sesija) return;
  pocistiGlasovneTimere(sesija);
  const tekst = [sesija.tekst, sesija.trenutni].filter(Boolean).join(" ").trim();
  const prethodni = slusac;
  glasovniUnos = null;
  slusac = null;
  // Kasni događaji više ne mogu promijeniti popis niti pokrenuti novi mikrofon.
  try { prethodni?.abort(); } catch (e) {}
  if (!tekst && !glasovnaPoruka) glasovnaPoruka = "Nije prepoznat govor. Pokušaj ponovno ili koristi unos ispod.";
  prikaziGlasovniUnos();
  if (tekst) dodajIzTeksta(razdvojiGlasovniPopis(tekst).join(", "));
}

function glasovniNeuspjeh(sesija, poruka) {
  if (glasovniUnos !== sesija) return;
  sesija.aktivan = false;
  glasovnaPoruka = poruka + " Prepoznate stavke ostaju na popisu. Možeš pokušati ponovno ili upotrijebiti unos ispod.";
  dovrsiGlasovniUnos(sesija);
}

function alternativniUnos() {
  // Standardno tekstno polje radi i bez Web Speech API-ja. Diktiranje tipkovnice
  // pripada uređaju; web stranica ga ne može uključiti niti jamčiti dostupnost.
  $("unos").focus();
}

function noviSlusac(sesija) {
  if (glasovniUnos !== sesija || !sesija.aktivan) return;
  sesija.snima = false;
  prikaziGlasovniUnos();
  let novi;
  try { novi = new Prepoznavanje(); }
  catch (e) { glasovniNeuspjeh(sesija, "Preglednik nije uspio otvoriti prepoznavanje govora."); return; }
  slusac = novi;
  novi.lang = "hr-HR";
  // Zadrži prethodni način prepoznavanja koji je korisniku radio.
  // Aplikacija povezuje više kratkih prepoznavanja u jednu sesiju nabrajanja.
  novi.continuous = false;
  novi.interimResults = false;
  novi.maxAlternatives = 1;
  const vrijedi = () => glasovniUnos === sesija && slusac === novi;
  const prije = sesija.tekst;
  sesija.pokretanje = setTimeout(() => {
    if (vrijedi()) glasovniNeuspjeh(sesija, "Mikrofon se nije pokrenuo. Provjeri dozvolu mikrofona za ovu stranicu i preglednik.");
  }, 15000);
  const pratiRezultate = () => {
    clearTimeout(sesija.bezRezultata);
    sesija.bezRezultata = setTimeout(() => {
      if (vrijedi()) glasovniNeuspjeh(sesija, "Prepoznavanje nije vratilo tekst. Provjeri internetsku vezu i mikrofon.");
    }, 20000);
  };
  novi.onstart = () => {
    if (!vrijedi()) return;
    clearTimeout(sesija.pokretanje);
    pratiRezultate();
  };
  novi.onaudiostart = () => {
    if (!vrijedi()) return;
    clearTimeout(sesija.pokretanje);
    sesija.snima = true;
    pratiRezultate();
    prikaziGlasovniUnos();
  };
  novi.onresult = (e) => {
    if (!vrijedi()) return;
    clearTimeout(sesija.pokretanje);
    sesija.prazniPokusaji = 0;
    pratiRezultate();
    const zavrseni = [], privremeni = [];
    for (let i = 0; i < e.results.length; i++) {
      const r = e.results[i];
      (r.isFinal ? zavrseni : privremeni).push(r[0].transcript);
    }
    sesija.tekst = [prije, ...zavrseni].filter(Boolean).join(" ");
    sesija.trenutni = privremeni.join(" ");
    prikaziGlasovniUnos();
  };
  novi.onerror = (e) => {
    if (!vrijedi()) return;
    if (e.error === "no-speech") return; // onend ograničava broj praznih pokušaja.
    const poruke = {
      "not-allowed": "Pristup mikrofonu nije dopušten. Provjeri dozvolu u pregledniku i postavkama uređaja.",
      "service-not-allowed": "Preglednik ne dopušta uslugu prepoznavanja govora.",
      "audio-capture": "Zvuk mikrofona nije dostupan. Provjeri mikrofon i koristi li ga druga aplikacija.",
      "network": "Usluga prepoznavanja govora nije dostupna preko mreže.",
      "language-not-supported": "Usluga ovog preglednika ne podržava hrvatski govor.",
      "no-speech": "Nije prepoznat govor.",
      "aborted": "Prepoznavanje govora je prekinuto.",
    };
    glasovniNeuspjeh(sesija, poruke[e.error] || "Prepoznavanje govora nije uspjelo.");
  };
  novi.onend = () => {
    if (!vrijedi()) return;
    clearTimeout(sesija.pokretanje);
    clearTimeout(sesija.bezRezultata);
    slusac = null;
    sesija.snima = false;
    if (!sesija.aktivan) { dovrsiGlasovniUnos(sesija); return; }
    if (sesija.trenutni) {
      sesija.tekst = [sesija.tekst, sesija.trenutni].filter(Boolean).join(" ");
      sesija.trenutni = "";
    }
    // Prekini petlju ako servis stalno završava bez ijednog novog rezultata.
    sesija.prazniPokusaji = sesija.tekst === prije ? sesija.prazniPokusaji + 1 : 0;
    if (sesija.prazniPokusaji >= 2) {
      glasovniNeuspjeh(sesija, "Preglednik završava slušanje bez prepoznatog govora.");
      return;
    }
    prikaziGlasovniUnos();
    sesija.timer = setTimeout(() => noviSlusac(sesija), 300);
  };
  try { novi.start(); }
  catch (e) { glasovniNeuspjeh(sesija, "Preglednik nije uspio pokrenuti glasovni unos."); }
}

function pokreniSlusanje() {
  if (glasovniUnos) {
    const sesija = glasovniUnos;
    sesija.aktivan = false;
    pocistiGlasovneTimere(sesija);
    prikaziGlasovniUnos();
    // Neki preglednici ne šalju onend nakon stop(). Ne ostavljaj zaključan gumb.
    sesija.zavrsetak = setTimeout(() => dovrsiGlasovniUnos(sesija), 2000);
    if (slusac) {
      try { slusac.stop(); } catch (e) { dovrsiGlasovniUnos(sesija); }
    } else dovrsiGlasovniUnos(sesija);
    return;
  }
  glasovnaPoruka = "";
  if (!Prepoznavanje) {
    glasovnaPoruka = "Ovaj preglednik nema ugrađeno prepoznavanje govora. U polju ispod možeš upisati popis ili koristiti mikrofon tipkovnice ako je dostupan na uređaju, pa pritisnuti Dodaj.";
    prikaziGlasovniUnos();
    alternativniUnos();
    return;
  }
  glasovniUnos = { aktivan: true, snima: false, tekst: "", trenutni: "", prazniPokusaji: 0 };
  prikaziGlasovniUnos();
  noviSlusac(glasovniUnos);
}

// Ne pokreći dodatno slušanje kad aplikacija nije vidljiva.
document.addEventListener("visibilitychange", () => {
  if (document.hidden && glasovniUnos?.aktivan) pokreniSlusanje();
});

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
function brojPakiranja(stavka, p) {
  return stavka.kom;
}

// Sve trgovine uspoređuju istu fizičku količinu trenutno odabranih artikala.
// Količina = broj odabranih pakiranja × sadržaj pakiranja; ne zaokružuje se za usporedbu.
function usporedbaKosarice() {
  const lanci = sviLanci();
  const zbroj = new Map([...lanci].map((l) => [l, { usporedno: 0, ukupno: 0, nema: [] }]));
  let najboljeMijesano = 0;
  let sveMijesanoIma = true;
  const jedinice = [];
  for (const stavka of stanje.popis) {
    const prikazane = ponudeZaGrupu(stavka.naziv);
    const odabrana = prikazane[(stanje.odabir[stavka.naziv] || 0) % prikazane.length];
    const kolicina = odabrana && imaJedinicnu(odabrana)
      ? podaci.proizvodi[odabrana.i][2] * brojPakiranja(stavka, odabrana) : 0;
    const { najbolje, usporedi } = kolicina > 0
      ? najboljePoLancu(stavka.naziv, lanci, odabrana.jedinica)
      : { najbolje: new Map(), usporedi: () => 0 };
    const prva = [...najbolje.values()].sort(usporedi)[0];
    if (prva) {
      najboljeMijesano += prva.poJedinici * kolicina;
      jedinice.push(`${stavka.naziv}: ${Number(kolicina.toFixed(6)).toLocaleString("hr-HR")} ${prva.jedinica}`);
    } else sveMijesanoIma = false;
    for (const [l, z] of zbroj) {
      const p = najbolje.get(l);
      if (p) {
        z.usporedno += p.poJedinici * kolicina;
        // Za blagajnu su potrebna cijela pakiranja, barem tražena količina.
        const pakiranja = Math.ceil(kolicina / podaci.proizvodi[p.i][2] - 1e-9);
        z.ukupno += p.cijena * pakiranja;
      } else z.nema.push(stavka.naziv);
    }
  }
  return { zbroj, najboljeMijesano, sveMijesanoIma, jedinice };
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
      <div class="detalji"><span class="kolicina"></span><span class="mjesto"></span></div>`);
    sadrzaj.querySelector(".naziv").textContent = naziv;
    sadrzaj.querySelector(".trgovina").textContent = lanac;
    sadrzaj.querySelector(".cijena").textContent = euro(cijena);
    sadrzaj.querySelector(".kolicina").textContent = [
      pakiranja > 1 ? `${pakiranja} × ${euro(p.cijena)}` : "",
      kolicina,
      p.vrstaNejasna ? "Moguće podudaranje · vrsta za provjeru"
        : imaJedinicnu(p) ? opisJedinicne(p) : "Količina nije poznata · bez poretka po jediničnoj cijeni",
    ].filter(Boolean).join(" · ");
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

// Koliko bi koštalo da se sve kupi u istoj trgovini.
function prikaziJednuTrgovinu() {
  const ul = $("trgovine-usporedba");
  ul.innerHTML = "";
  $("jedna-trgovina").hidden = !podaci || !stanje.popis.length;
  if (!podaci || !stanje.popis.length) return;

  const { zbroj, najboljeMijesano, sveMijesanoIma, jedinice } = usporedbaKosarice();
  const napomena = document.createElement("li");
  napomena.className = "savjet";
  napomena.textContent = `Usporedne količine: ${jedinice.join(" · ") || "nema usporedivih ponuda"}. `
    + (sveMijesanoIma ? `Najpovoljnije po svim trgovinama za odabrane količine: ${euro(najboljeMijesano)} za te količine.`
      : "Nije moguće usporediti cijeli popis.");
  ul.appendChild(napomena);

  const redovi = [...zbroj].filter(([, z]) => z.nema.length < stanje.popis.length)
    .sort(([, a], [, b]) => a.nema.length - b.nema.length || a.usporedno - b.usporedno)
    .slice(0, 8);
  if (!redovi.length) { $("jedna-trgovina").hidden = true; return; }

  for (const [l, z] of redovi) {
    const ime = podaci.lanci[l];
    const li = document.createElement("li");
    const b = gumb("", "trgovina-red" + (stanje.jedna === ime ? " odabrana" : ""), () => {
      stanje.jedna = stanje.jedna === ime ? null : ime;
      promijeniPostavke();
      window.scrollTo(0, 0);
    });
    const lijevo = document.createElement("span");
    lijevo.className = "lijevo";
    const naziv = document.createElement("strong");
    naziv.textContent = ime;
    const opis = document.createElement("small");
    opis.textContent = z.nema.length
      ? `Nedostaje: ${z.nema.join(", ")}. Djelomična usporedba; nije cijeli popis.`
      : sveMijesanoIma && z.usporedno - najboljeMijesano >= 0.005
        ? `Ima sve · ${euro(z.usporedno - najboljeMijesano)} više za usporedne količine`
        : "Ima sve · najpovoljnije po jedinici";
    const placanje = document.createElement("small");
    placanje.textContent = `${z.nema.length ? "Za pronađena pakiranja" : "Cijela pakiranja za barem istu količinu"}: ${euro(z.ukupno)}`;
    lijevo.append(naziv, opis, placanje);
    const iznos = document.createElement("span");
    iznos.className = "iznos";
    iznos.textContent = z.nema.length ? "Nepotpuno" : `${euro(z.usporedno)}`;
    iznos.setAttribute("aria-label", z.nema.length ? "Nema usporednog iznosa za cijeli popis" : `${euro(z.usporedno)} za iste jedinične količine kao najpovoljnija kombinacija`);
    b.append(lijevo, iznos);
    li.appendChild(b);
    ul.appendChild(li);
  }
}

function promijeni(grupa, smjer) {
  const n = ponudeZaGrupu(grupa).length;
  stanje.odabir[grupa] = ((stanje.odabir[grupa] || 0) + smjer + n) % n;
  spremi();
  prikaziRezultate();
}

// ---------- Postavke ----------
function prikaziPostavke() {
  for (const r of document.querySelectorAll('input[name="nacin"]')) r.checked = r.value === stanje.nacin;
  const div = $("lanci");
  div.innerHTML = "";
  if (!podaci) return;
  const iskljuceni = new Set(stanje.iskljuceni);
  [...podaci.lanci].sort((a, b) => a.localeCompare(b, "hr")).forEach((ime) => {
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
    label.append(cb, " " + ime);
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
$("tipkovnica-unos").onclick = alternativniUnos;
$("rucni-unos").onsubmit = (e) => {
  e.preventDefault();
  const tekst = $("unos").value.trim();
  if (tekst) dodajIzTeksta(razdvojiGlasovniPopis(tekst).join(", "));
  $("unos").value = "";
};
$("samo-trgovina-makni").onclick = () => {
  stanje.jedna = null;
  promijeniPostavke();
};

prikaziPostavke();
prikazi();
ucitajPodatke();

if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});



