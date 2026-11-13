// Ljuska aplikacije: uparivanje, prikaz za stanara / kontrolni centar, tema, jedan red filtera.
import { EnergijaKlijent } from "./sdk/energija-sdk.js";
import "./komponente/komponente.js";

const $ = (id) => document.getElementById(id);
const pohrana = {
  get: (k) => { try { return localStorage.getItem(k); } catch (_) { return null; } },
  set: (k, v) => { try { localStorage.setItem(k, v); } catch (_) { /* privatni prozor */ } },
};

let token = pohrana.get("energija-token");
let klijent = EnergijaKlijent.za({ token });
let uloga = null;
let prikaz = pohrana.get("energija-prikaz") || "stanar";
let raspon = pohrana.get("energija-raspon") || "24h";
let tema = pohrana.get("energija-tema") || "auto";

const RASPORED = {
  stanar: [["e-status"], ["e-usteda", "s7"], ["e-tok", "s5"], ["e-bojler", "s4 par"], ["e-baterija", "s4 par"], ["e-solar", "s4 par"],
    ["e-pastir", "s6"], ["e-navodnjavanje", "s6"]],
  admin: [["e-status"], ["e-usteda", "s7"], ["e-tok", "s5"], ["e-energija"], ["e-baterija", "s6"], ["e-bojler", "s6"], ["e-solar", "s6"],
    ["e-navodnjavanje", "s6"], ["e-pastir"], ["e-odluke"], ["e-upravljanje"], ["e-dijagnostika"]],
};

function primijeniTemu() {
  if (tema === "auto") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.setAttribute("data-theme", tema === "tamna" ? "dark" : "light");
  document.querySelectorAll("#sadrzaj > *").forEach((e) => (tema === "auto" ? e.removeAttribute("tema") : e.setAttribute("tema", tema)));
  $("tema").setAttribute("aria-label", `Tema: ${{ auto: "prema sustavu", svijetla: "svijetla", tamna: "tamna" }[tema]}`);
}

function oznaciSegment(skup, atribut, vrijednost) {
  skup.querySelectorAll("button").forEach((b) => b.setAttribute("aria-checked", String(b.dataset[atribut] === vrijednost)));
}

function iscrtaj() {
  if (uloga !== "administrator") prikaz = "stanar";
  $("izbor-prikaza").hidden = uloga !== "administrator";
  oznaciSegment($("izbor-prikaza"), "prikaz", prikaz);
  oznaciSegment($("izbor-raspona"), "raspon", raspon);
  $("filteri").hidden = prikaz !== "admin";
  const sadrzaj = $("sadrzaj");
  sadrzaj.replaceChildren(...RASPORED[prikaz].map(([ime, klasa]) => {
    const e = document.createElement(ime);
    if (klasa) e.className = klasa;
    e.klijent = klijent;
    e.setAttribute("prikaz", prikaz === "admin" ? "napredno" : "jednostavno");
    e.setAttribute("raspon", raspon);
    return e;
  }));
  primijeniTemu();
}

async function pokreni() {
  try {
    const s = await klijent.sustav();
    uloga = s.uloga;
    $("naziv").textContent = s.lokacija || "Energija";
    $("podnaslov").textContent = uloga === "administrator" ? "administrator" : "stanar";
    $("uparivanje").hidden = true;
    $("aplikacija").hidden = false;
    iscrtaj();
  } catch (e) {
    if (e.status === 401) prikaziUparivanje();
    else { $("aplikacija").hidden = false; $("sadrzaj").textContent = "Jezgra trenutačno nije dostupna – pokušavam ponovno…"; setTimeout(pokreni, 5000); }
  }
}

function prikaziUparivanje() { $("aplikacija").hidden = true; $("uparivanje").hidden = false; $("kod").focus(); }

$("obrazac-uparivanja").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("greska-uparivanja").textContent = "";
  try {
    const r = await klijent.upari($("kod").value.trim(), navigator.userAgent.slice(0, 40));
    token = r.token;
    pohrana.set("energija-token", token);
    klijent = EnergijaKlijent.za({ token });
    pokreni();
  } catch (_) { $("greska-uparivanja").textContent = "Kod nije ispravan ili je istekao."; }
});

$("izbor-prikaza").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-prikaz]");
  if (!b) return;
  prikaz = b.dataset.prikaz;
  pohrana.set("energija-prikaz", prikaz);
  iscrtaj();
});
$("izbor-raspona").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-raspon]");
  if (!b) return;
  raspon = b.dataset.raspon;
  pohrana.set("energija-raspon", raspon);
  oznaciSegment($("izbor-raspona"), "raspon", raspon);
  document.querySelectorAll("#sadrzaj > *").forEach((el) => el.setAttribute("raspon", raspon));  // filter vrijedi za sve ispod
});
$("tema").addEventListener("click", () => {
  tema = { auto: "svijetla", svijetla: "tamna", tamna: "auto" }[tema];
  pohrana.set("energija-tema", tema);
  primijeniTemu();
});
document.addEventListener("e-greska", (e) => { if (e.detail.status === 401) prikaziUparivanje(); });

pokreni();
