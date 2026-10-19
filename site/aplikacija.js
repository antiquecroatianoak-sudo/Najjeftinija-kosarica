"use strict";

// ---------- Stanje aplikacije (sprema se u mobitel) ----------
const SPREMISTE = "kosarica-v1";
let stanje = { popis: [], zakljucano: false, odabir: {} }; // odabir: grupa -> redni broj ponude
try { Object.assign(stanje, JSON.parse(localStorage.getItem(SPREMISTE)) || {}); } catch (e) {}
function spremi() {
  try { localStorage.setItem(SPREMISTE, JSON.stringify(stanje)); } catch (e) {}
}

// ---------- Podaci o cijenama ----------
let podaci = null;     // { datum, lanci: [...], proizvodi: [[naziv, količina, lanac, cijena], ...] }
let rijeci = [];       // za svaki proizvod: normalizirane riječi naziva
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

async function ucitajPodatke() {
  try {
    const odgovor = await fetch("data/proizvodi.json", { cache: "no-cache" });
    if (!odgovor.ok) throw new Error(odgovor.status);
    podaci = await odgovor.json();
    rijeci = podaci.proizvodi.map((p) => normaliziraj(p[0]).split(" "));
    const [g, m, d] = podaci.datum.split("-");
    $("status").textContent =
      `Cijene od ${d}.${m}.${g}. · ${podaci.proizvodi.length.toLocaleString("hr-HR")} proizvoda · ${podaci.lanci.length} lanaca`;
  } catch (e) {
    $("status").textContent = "Cijene još nisu preuzete. Pokušaj ponovno kasnije.";
  }
  prikazi();
}

// Sve ponude za jednu grupu (npr. "mlijeko"), od najjeftinije prema skupljoj.
// Proizvodi su u datoteci već poredani po cijeni.
function ponudeZaGrupu(grupa) {
  if (ponudeCache.has(grupa)) return ponudeCache.get(grupa);
  const korijeni = normaliziraj(grupa).split(" ").filter(Boolean).map(korijen);
  const naPocetku = [];  // naziv počinje traženom riječi (npr. "Mlijeko svježe…")
  const bilogdje = [];   // tražena riječ je negdje u nazivu
  if (korijeni.length) {
    for (let i = 0; i < rijeci.length; i++) {
      const r = rijeci[i];
      if (!korijeni.every((k) => r.some((w) => w.startsWith(k)))) continue;
      (r[0].startsWith(korijeni[0]) ? naPocetku : bilogdje).push(i);
    }
  }
  const rezultat = naPocetku.length ? naPocetku : bilogdje;
  ponudeCache.set(grupa, rezultat);
  return rezultat;
}

// ---------- Dodavanje stavki (glasom ili rukom) ----------
function dodajIzTeksta(tekst) {
  const dijelovi = tekst
    .split(/,|;|\.|\s+i\s+|\s+pa\s+|\s+te\s+|\s+onda\s+/i)
    .map((s) => s.trim().replace(/^(i|još|jos|pa)\s+/i, ""))
    .filter(Boolean);
  for (const d of dijelovi) {
    const naziv = d.charAt(0).toUpperCase() + d.slice(1).toLowerCase();
    if (!stanje.popis.some((p) => normaliziraj(p) === normaliziraj(naziv))) stanje.popis.push(naziv);
  }
  spremi();
  prikazi();
}

function ukloni(i) {
  stanje.popis.splice(i, 1);
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
  slusac.start();
  $("mikrofon").classList.add("slusa");
  $("mikrofon-tekst").textContent = "Slušam… (dodirni za kraj)";
}

// ---------- Prikaz ----------
function prikazi() {
  $("uredivanje").hidden = stanje.zakljucano;
  $("rezultati").hidden = !stanje.zakljucano;
  stanje.zakljucano ? prikaziRezultate() : prikaziPopis();
}

function prikaziPopis() {
  const ul = $("popis");
  ul.innerHTML = "";
  stanje.popis.forEach((stavka, i) => {
    const li = document.createElement("li");
    li.textContent = stavka;
    const gumb = document.createElement("button");
    gumb.type = "button";
    gumb.textContent = "✕";
    gumb.setAttribute("aria-label", `Ukloni ${stavka}`);
    gumb.onclick = () => ukloni(i);
    li.appendChild(gumb);
    ul.appendChild(li);
  });
  $("prazno").hidden = stanje.popis.length > 0;
  $("zakljucaj").disabled = stanje.popis.length === 0;
}

function prikaziRezultate() {
  const ul = $("kartice");
  ul.innerHTML = "";
  let ukupno = 0;
  const poLancu = {};

  for (const grupa of stanje.popis) {
    const li = document.createElement("li");
    li.className = "kartica";
    const ponude = podaci ? ponudeZaGrupu(grupa) : [];

    if (!ponude.length) {
      li.classList.add("nema");
      li.innerHTML = `<div class="grupa"></div><div class="naziv">${podaci ? "Nije pronađeno. Probaj drugi naziv." : "Cijene još nisu učitane."}</div>`;
      li.querySelector(".grupa").textContent = grupa;
      ul.appendChild(li);
      continue;
    }

    const rb = (stanje.odabir[grupa] || 0) % ponude.length;
    const [naziv, kolicina, lanacIdx, cijena] = podaci.proizvodi[ponude[rb]];
    const lanac = podaci.lanci[lanacIdx];
    ukupno += cijena;
    poLancu[lanac] = (poLancu[lanac] || 0) + 1;

    li.innerHTML = `
      <div class="grupa"></div>
      <div class="naziv"></div>
      <div class="redak"><span class="trgovina"></span><span class="cijena"></span></div>
      <div class="detalji"><span class="kolicina"></span><span class="mjesto"></span></div>`;
    li.querySelector(".grupa").textContent = grupa;
    li.querySelector(".naziv").textContent = naziv;
    li.querySelector(".trgovina").textContent = lanac;
    li.querySelector(".cijena").textContent = euro(cijena);
    li.querySelector(".kolicina").textContent = kolicina ? `Količina: ${kolicina}` : "";
    const mjesto = li.querySelector(".mjesto");
    if (rb > 0) {
      const natrag = document.createElement("button");
      natrag.className = "natrag";
      natrag.type = "button";
      natrag.textContent = `◀ ${rb + 1}. od ${ponude.length}`;
      natrag.onclick = (e) => { e.stopPropagation(); promijeni(grupa, -1); };
      mjesto.appendChild(natrag);
    } else {
      mjesto.textContent = `najjeftinije od ${ponude.length}`;
    }
    li.onclick = () => promijeni(grupa, +1);
    ul.appendChild(li);
  }

  $("ukupno").textContent = euro(ukupno);
  $("po-trgovinama").textContent = Object.entries(poLancu)
    .sort((a, b) => b[1] - a[1])
    .map(([l, n]) => `${l}: ${n}`)
    .join(" · ");
}

function promijeni(grupa, smjer) {
  const n = ponudeZaGrupu(grupa).length;
  stanje.odabir[grupa] = ((stanje.odabir[grupa] || 0) + smjer + n) % n;
  spremi();
  prikaziRezultate();
}

// ---------- Gumbi ----------
$("mikrofon").onclick = pokreniSlusanje;
$("rucni-unos").onsubmit = (e) => {
  e.preventDefault();
  const tekst = $("unos").value.trim();
  if (tekst) dodajIzTeksta(tekst);
  $("unos").value = "";
};
$("zakljucaj").onclick = () => {
  stanje.zakljucano = true;
  stanje.odabir = {};
  spremi();
  prikazi();
  window.scrollTo(0, 0);
};
$("otkljucaj").onclick = () => {
  stanje.zakljucano = false;
  spremi();
  prikazi();
};

prikazi();
ucitajPodatke();

if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
