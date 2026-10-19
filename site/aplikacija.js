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
    const [g, m, d] = podaci.datum.split("-");
    $("status").textContent =
      `Cijene od ${d}.${m}.${g}. · ${podaci.proizvodi.length.toLocaleString("hr-HR")} proizvoda · ${podaci.lanci.length} lanaca`;
    $("status").parentElement.classList.add("spremno");
  } catch (e) {
    podaci = null;
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
  return { i, lanac, cijena, jedinica, poJedinici: iznos ? cijena / iznos : null };
}

// Uspoređuj samo poznate količine i iste osnovne jedinice.
function usporedivePonude(ponude) {
  const valjane = ponude.filter((p) => Number.isFinite(p.poJedinici) && p.poJedinici > 0
    && ["kg", "l", "kom"].includes(p.jedinica));
  if (new Set(valjane.map((p) => p.jedinica)).size > 1) return [];
  return valjane;
}

function usporedba() {
  return (a, b) => a.poJedinici - b.poJedinici || a.cijena - b.cijena;
}

// Sve ponude za jednu grupu, od najisplativije prema skupljoj.
// Svaki proizvod se pojavljuje samo jednom, u najjeftinijem dopuštenom lancu.
function ponudeZaGrupu(grupa) {
  if (ponudeCache.has(grupa)) return ponudeCache.get(grupa);
  const lanci = dozvoljeniLanci();
  const ponude = [];
  for (const i of pogoci(grupa)) {
    const cijene = podaci.proizvodi[i][5];
    for (let k = 0; k < cijene.length; k += 2) {
      if (lanci.has(cijene[k])) { ponude.push(ponuda(i, cijene[k], cijene[k + 1])); break; }
    }
  }
  const usporedive = usporedivePonude(ponude).sort(usporedba());
  ponudeCache.set(grupa, usporedive);
  return usporedive;
}

// Za "sve u jednoj trgovini": najbolja ponuda za grupu u svakom lancu.
function najboljePoLancu(grupa, lanci) {
  const sve = [];
  for (const i of pogoci(grupa)) {
    const cijene = podaci.proizvodi[i][5];
    for (let k = 0; k < cijene.length; k += 2) {
      if (lanci.has(cijene[k])) sve.push(ponuda(i, cijene[k], cijene[k + 1]));
    }
  }
  const usporedi = usporedba();
  const najbolje = new Map();
  for (const p of usporedivePonude(sve)) {
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

function pokreniSlusanje() {
  if (!Prepoznavanje) {
    alert("Ovaj preglednik ne podržava glasovni unos. Otvori aplikaciju u Google Chromeu ili upiši proizvode rukom.");
    return;
  }
  if (slusac) { slusac.stop(); return; }
  slusac = new Prepoznavanje();
  slusac.lang = "hr-HR";
  slusac.interimResults = false;
  slusac.maxAlternatives = 1;
  slusac.onresult = (e) => dodajIzTeksta(e.results[0][0].transcript);
  slusac.onerror = (e) => {
    if (e.error === "not-allowed") alert("Dopusti pristup mikrofonu u postavkama preglednika.");
  };
  slusac.onend = () => {
    slusac = null;
    $("mikrofon").classList.remove("slusa");
    $("mikrofon-tekst").textContent = "Reci što trebaš kupiti";
  };
  try { slusac.start(); } catch (e) {
    slusac = null;
    alert("Glasovni unos nije dostupan. Pokušaj ponovno ili upiši proizvode.");
    return;
  }
  $("mikrofon").classList.add("slusa");
  $("mikrofon-tekst").textContent = "Slušam… (dodirni za kraj)";
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
  $("uredivanje").hidden = stanje.zakljucano;
  $("rezultati").hidden = !stanje.zakljucano;
  $("korak-popis").classList.toggle("aktivan", !stanje.zakljucano);
  $("korak-cijene").classList.toggle("aktivan", !!stanje.zakljucano);
  $("korak-popis").toggleAttribute("aria-current", !stanje.zakljucano);
  $("korak-cijene").toggleAttribute("aria-current", !!stanje.zakljucano);
  (stanje.zakljucano ? $("korak-cijene") : $("korak-popis")).setAttribute("aria-current", "step");
  $("lanci-info").textContent = podaci ? `${sviLanci().size} od ${podaci.lanci.length} trgovina odabrano` : "Trgovine će se prikazati nakon učitavanja cijena.";
  stanje.zakljucano ? prikaziRezultate() : prikaziPopis();
}

function prikaziPopis() {
  const ul = $("popis");
  ul.innerHTML = "";
  stanje.popis.forEach((stavka, i) => {
    const li = document.createElement("li");
    const naziv = document.createElement("span");
    naziv.className = "naziv-stavke";
    naziv.textContent = stavka.naziv;
    const kontrole = document.createElement("span");
    kontrole.className = "kontrole";
    const manje = gumb("−", "kolicina-gumb", () => promijeniKolicinu(i, -1), `Manje ${stavka.naziv}`);
    manje.disabled = stavka.kom <= 1;
    const broj = document.createElement("span");
    broj.className = "broj";
    broj.textContent = `${stavka.kom}×`;
    kontrole.append(
      manje, broj,
      gumb("+", "kolicina-gumb", () => promijeniKolicinu(i, +1), `Više ${stavka.naziv}`),
      gumb("✕", "ukloni", () => ukloni(i), `Ukloni ${stavka.naziv}`),
    );
    li.append(naziv, kontrole);
    ul.appendChild(li);
  });
  $("prazno").hidden = stanje.popis.length > 0;
  const n = stanje.popis.length;
  $("broj-stavki").textContent = `${n} ${n % 10 === 1 && n % 100 !== 11 ? "stavka" : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14) ? "stavke" : "stavki"}`;
  $("zakljucaj").disabled = !n || !podaci || !sviLanci().size;
  $("pomoc-usporedbe").textContent = !n ? "Dodaj barem jedan proizvod za usporedbu."
    : !podaci ? "Usporedba će biti dostupna nakon učitavanja cijena."
    : !sviLanci().size ? "Odaberi barem jednu trgovinu u postavkama."
    : "Usporedi ponude iz odabranih trgovina.";
}

// "10 jaja" znači 10 komada, a ne 10 pakiranja po 10 jaja. Kad netko traži
// 5 ili više komada proizvoda koji dolazi u pakiranju od više komada,
// računamo koliko pakiranja treba.
function brojPakiranja(stavka, p) {
  const iznos = podaci.proizvodi[p.i][2];
  if (stavka.kom >= 5 && p.jedinica === "kom" && iznos > 1) return Math.ceil(stavka.kom / iznos);
  return stavka.kom;
}

function opisJedinicne(p) {
  if (!p.poJedinici) return "";
  const iznos = podaci.proizvodi[p.i][2];
  if (p.jedinica === "kom" && iznos <= 1) return "";
  return `${euro(p.poJedinici)}/${p.jedinica}`;
}

function prikaziRezultate() {
  const ul = $("kartice");
  ul.innerHTML = "";
  let ukupno = 0;
  let preostalo = 0;
  let kupljeno = 0;
  let nedostaje = 0;
  const poLancu = {};
  const lanciOk = sviLanci().size > 0;

  $("samo-trgovina").hidden = !(podaci && dozvoljeniLanci().size === 1 && stanje.jedna);
  $("samo-trgovina-naziv").textContent = stanje.jedna || "";

  for (const stavka of stanje.popis) {
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

    if (!ponude.length) {
      nedostaje++;
      li.classList.add("nema");
      const poruka = document.createElement("div");
      poruka.className = "naziv";
      poruka.textContent = !podaci ? "Cijene još nisu učitane."
        : !lanciOk ? "Nijedna trgovina nije odabrana (vidi Postavke)."
        : stanje.jedna ? `Nema u trgovini ${stanje.jedna}.`
        : "Nema ponuda s usporedivom količinom i jedinicom mjere. Preciziraj naziv proizvoda.";
      sadrzaj.appendChild(poruka);
      ul.appendChild(li);
      continue;
    }

    const rb = (stanje.odabir[grupa] || 0) % ponude.length;
    const p = ponude[rb];
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
      opisJedinicne(p),
    ].filter(Boolean).join(" · ");
    const mjesto = sadrzaj.querySelector(".mjesto");
    if (rb > 0) {
      mjesto.appendChild(gumb(`◀ ${rb + 1}. od ${ponude.length}`, "natrag", (e) => {
        e.stopPropagation();
        promijeni(grupa, -1);
      }));
    } else {
      mjesto.textContent = `${stanje.nacin === "jedinica" ? "najisplativije" : "najjeftinije"} od ${ponude.length}`;
    }
    if (ponude.length > 1) {
      sadrzaj.appendChild(gumb("Sljedeći proizvod →", "sljedeci", (e) => {
        e.stopPropagation();
        promijeni(grupa, +1);
      }, `Sljedeći proizvod za ${grupa}`));
    }
    kvacica.setAttribute("aria-pressed", String(!!stavka.kupljeno));
    li.onclick = () => promijeni(grupa, +1);
    ul.appendChild(li);
  }

  $("napredak").textContent = stanje.popis.length ? `U košarici: ${kupljeno} od ${stanje.popis.length}` : "";
  $("ukupno").textContent = euro(ukupno);
  $("ukupno-oznaka").textContent = nedostaje ? "Iznos pronađenih proizvoda" : "Ukupno za popis";
  $("nedostaje").hidden = nedostaje === 0;
  $("nedostaje").textContent = `Za ${nedostaje} od ${stanje.popis.length} stavki nema cijene. Prikazani iznos ne obuhvaća cijeli popis.`;
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

  const lanci = sviLanci();
  const zbroj = new Map([...lanci].map((l) => [l, { ukupno: 0, nema: [] }]));
  let najboljeMijesano = 0;
  let sveMijesanoIma = true;
  for (const stavka of stanje.popis) {
    const { najbolje, usporedi } = najboljePoLancu(stavka.naziv, lanci);
    const prva = [...najbolje.values()].sort(usporedi)[0];
    if (prva) najboljeMijesano += prva.cijena * brojPakiranja(stavka, prva); else sveMijesanoIma = false;
    for (const [l, z] of zbroj) {
      const p = najbolje.get(l);
      if (p) z.ukupno += p.cijena * brojPakiranja(stavka, p); else z.nema.push(stavka.naziv);
    }
  }

  const redovi = [...zbroj].filter(([, z]) => z.nema.length < stanje.popis.length)
    .sort(([, a], [, b]) => a.nema.length - b.nema.length || a.ukupno - b.ukupno)
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
      ? `nema: ${z.nema.join(", ")}`
      : sveMijesanoIma && z.ukupno - najboljeMijesano >= 0.005
        ? `ima sve · ${euro(z.ukupno - najboljeMijesano)} više nego po svim trgovinama`
        : "ima sve";
    lijevo.append(naziv, opis);
    const iznos = document.createElement("span");
    iznos.className = "iznos";
    iznos.textContent = (z.nema.length ? "od " : "") + euro(z.ukupno);
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
$("rucni-unos").onsubmit = (e) => {
  e.preventDefault();
  const tekst = $("unos").value.trim();
  if (tekst) dodajIzTeksta(tekst);
  $("unos").value = "";
};
$("zakljucaj").onclick = () => {
  if (!podaci || !stanje.popis.length || !sviLanci().size) return;
  stanje.zakljucano = true;
  stanje.odabir = {};
  stanje.popis.forEach((s) => { s.kupljeno = false; });
  spremi();
  prikazi();
  window.scrollTo(0, 0);
};
$("otkljucaj").onclick = () => {
  stanje.zakljucano = false;
  spremi();
  prikazi();
};
$("samo-trgovina-makni").onclick = () => {
  stanje.jedna = null;
  promijeniPostavke();
};

prikaziPostavke();
prikazi();
ucitajPodatke();

if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});

