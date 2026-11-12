"use strict";
// Sučelje lokalne jezgre: bez vanjskih biblioteka, radi bez interneta.
const $ = (id) => document.getElementById(id);
const fmt = (v, dec = 0, suf = "") =>
  v === null || v === undefined || Number.isNaN(v) ? "–" :
  Number(v).toLocaleString("hr-HR", { minimumFractionDigits: dec, maximumFractionDigits: dec }) + suf;
const kw = (w) => (w === null || w === undefined ? "–" : Math.abs(w) >= 1000 ? fmt(w / 1000, 1, " kW") : fmt(w, 0, " W"));

let token = null;
try { token = localStorage.getItem("energija-token"); } catch (_) { /* privatni prozor */ }

async function api(put, opcije = {}) {
  const h = Object.assign({ "Content-Type": "application/json" }, opcije.headers || {});
  if (token) h.Authorization = "Bearer " + token;
  const r = await fetch(put, Object.assign({}, opcije, { headers: h, credentials: "same-origin" }));
  if (r.status === 401) { prikaziUparivanje(); throw new Error("uparivanje"); }
  return r;
}

function prikaziUparivanje() { $("app").hidden = true; $("uparivanje").hidden = false; $("kod").focus(); }

$("obrazac-uparivanja").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("greska-uparivanja").textContent = "";
  const r = await fetch("/api/upari", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ kod: $("kod").value.trim(), ime: navigator.userAgent.slice(0, 40) }) });
  if (!r.ok) { $("greska-uparivanja").textContent = "Kod nije ispravan ili je istekao."; return; }
  token = (await r.json()).token;
  try { localStorage.setItem("energija-token", token); } catch (_) { /* kolačić je dovoljan */ }
  $("uparivanje").hidden = true;
  osvjezi();
});

const OPIS_DIONICE = { ispravna: "ispravna", slaba: "slaba", izolirana: "izolirana", prekid: "prekid",
  bez_napona: "bez napona", nema_mjerenja: "nema mjerenja", "?": "–" };
const NACIN = { NORMALNO: "Normalan rad", PRILIKA: "Višak sunca – teški poslovi", STEDNO: "Štedni način", KRITICNO: "Kritično – samo zaštita" };

function crtajTok(e, mrezaDostupna) {
  const pv = e.pv_snaga_w || 0, kuca = e.potrosnja_w || 0, bat = e.baterija_snaga_w || 0;
  const mreza = mrezaDostupna ? kuca - pv + bat : 0;
  $("t-pv").textContent = kw(pv);
  $("t-kuca").textContent = kw(kuca);
  $("t-bat").textContent = (bat > 20 ? "+" : bat < -20 ? "−" : "") + kw(Math.abs(bat));
  $("t-mreza").textContent = mrezaDostupna ? kw(mreza) : "nema";
  const postavi = (id, aktivno, klasa) => { $(id).setAttribute("class", "linija" + (aktivno ? " aktivna " + klasa : "")); };
  postavi("l-pv-kuca", pv > 20 && kuca > 20, "sunce");
  postavi("l-pv-bat", bat > 20 && pv > 20, "sunce");
  postavi("l-bat-kuca", bat < -20, "");
  postavi("l-mreza-kuca", mreza > 20, "mreza");
}

function crtajPlan(plan) {
  const svg = $("plan-svg");
  if (!plan || !plan.length) { svg.innerHTML = '<text x="10" y="80">Plan se izrađuje…</text>'; return; }
  const W = 640, H = 150, n = plan.length, sx = W / n;
  const maxPv = Math.max(500, ...plan.map((p) => p.pv_w || 0));
  const cijene = plan.map((p) => p.cijena);
  const cMin = Math.min(...cijene), cMax = Math.max(...cijene) + 1e-6;
  let pv = `M0 ${H}`, soc = "", cij = "";
  plan.forEach((p, i) => {
    const x = i * sx + sx / 2;
    pv += ` L${x.toFixed(1)} ${(H - (p.pv_w / maxPv) * (H - 20)).toFixed(1)}`;
    soc += `${i ? " L" : "M"}${x.toFixed(1)} ${(H - p.soc_cilj * (H - 20)).toFixed(1)}`;
    cij += `${i ? " L" : "M"}${x.toFixed(1)} ${(H - 10 - ((p.cijena - cMin) / (cMax - cMin)) * (H - 50)).toFixed(1)}`;
  });
  pv += ` L${W} ${H} Z`;
  let oznake = "";
  plan.forEach((p, i) => {
    const h = new Date(p.ts * 1000).getHours();
    if (h % 6 === 0) oznake += `<text x="${(i * sx + sx / 2).toFixed(1)}" y="166" text-anchor="middle">${String(h).padStart(2, "0")} h</text>`;
  });
  svg.innerHTML =
    `<path d="${pv}" fill="var(--sunce)" opacity=".18"/>` +
    `<path d="${cij}" fill="none" stroke="var(--mreza)" stroke-width="1.5" stroke-dasharray="3 3"/>` +
    `<path d="${soc}" fill="none" stroke="var(--naglasak)" stroke-width="2.5" stroke-linejoin="round"/>` +
    `<text x="4" y="12">${fmt(cMax * 100, 0)} c/kWh</text><text x="4" y="${H - 2}">${fmt(cMin * 100, 0)} c</text>` + oznake;
}

function prikazi(s) {
  $("app").hidden = false;
  const u = s.usteda || {};
  const mj = u.mjesec, dan = u.danas, uk = u.ukupno;
  $("usteda-mjesec").textContent = mj ? fmt(mj.usteda_eur, 2, " €") : "–";
  $("usteda-danas").textContent = dan ? fmt(dan.usteda_eur, 2, " €") : "–";
  $("usteda-ukupno").textContent = uk ? fmt(uk.usteda_eur, 2, " €") : "–";
  $("samoopskrba").textContent = mj && mj.samoopskrba !== null ? fmt(mj.samoopskrba * 100, 0, " %") : "–";
  const d = new Date(s.vrijeme * 1000);
  $("podnaslov").textContent = d.toLocaleString("hr-HR", { weekday: "long", hour: "2-digit", minute: "2-digit" }) +
    " · " + (s.cijena ? `${fmt(s.cijena.kupnja * 100, 1)} c/kWh (${s.cijena.izvor})` : "");

  const kriticne = (s.anomalije || []).filter((a) => a.ozbiljnost === "kriticno");
  const st = $("status-sustava");
  const kvarPastira = ["izolirano", "prekid", "trazenje", "kvar_aparata"].includes(s.pastir.nacin);
  st.className = "status" + (kriticne.length || s.sigurno_stanje ? " kvar" : kvarPastira || (s.anomalije || []).length ? " upozorenje" : "");
  $("status-tekst").textContent = s.sigurno_stanje ? "Sigurno stanje" : kriticne.length ? "Zaštita aktivna" :
    kvarPastira ? "Kvar ograde izoliran" : NACIN[s.nacin] || s.nacin;

  crtajTok(s.energija, s.mreza_dostupna);

  const soc = s.energija.baterija_soc;
  $("soc").textContent = soc !== null && soc !== undefined ? fmt(soc * 100, 0, " %") : "–";
  $("prsten-soc").setAttribute("stroke-dasharray", `${((soc || 0) * 100).toFixed(1)} 100`);
  const rez = (s.parametri && s.parametri.rezerva_soc) || 0.15;
  const kut = rez * 2 * Math.PI;
  const r = $("prsten-rezerva");
  r.setAttribute("x1", 60 + 44 * Math.cos(kut)); r.setAttribute("y1", 60 + 44 * Math.sin(kut));
  r.setAttribute("x2", 60 + 56 * Math.cos(kut)); r.setAttribute("y2", 60 + 56 * Math.sin(kut));
  $("bat-temp").textContent = fmt(s.energija.baterija_temp_c, 0, " °C");
  const b = s.energija.baterija_snaga_w || 0;
  $("bat-opis").textContent = (b > 20 ? `Puni se ${kw(b)}` : b < -20 ? `Daje ${kw(-b)}` : "Miruje") +
    ` · noćna rezerva ${fmt(rez * 100, 0, " %")} (naučeno)`;

  const p = s.pastir;
  $("pastir-dionice").innerHTML = (p.dionice || []).map((x, i) => {
    const v = p.naponi ? p.naponi[i + 1] : null;
    return `<div class="dionica ${x}"><div class="crta"></div><span class="kv">${fmt(v, 1, " kV")}</span>${i + 1} · ${OPIS_DIONICE[x] || x}</div>`;
  }).join("");
  const zadnji = (p.dogadjaji || []).slice(-1)[0];
  $("pastir-opis").textContent = (p.nacin === "normalno" ? (p.snaga < 1 ? "Ispravno · štedni impuls" : "Ispravno · puna snaga") :
    zadnji ? zadnji.poruka : p.nacin) + (p.baterija !== null && p.baterija !== undefined ? ` · baterija aparata ${fmt(p.baterija * 100, 0, " %")}` : "");

  const zone = s.navodnjavanje.zone || {};
  $("zone").innerHTML = Object.entries(zone).map(([id, z]) => `
    <div class="zona"><div class="zona-red"><span>Zona ${id.replace("z", "")}${s.navodnjavanje.aktivna === id ? " · zalijeva se" : ""}</span><b>${fmt(z.vlaga, 0, " %")}</b></div>
    <div class="traka"><span style="width:${Math.min(100, (z.vlaga || 0) / 50 * 100)}%"></span><i style="left:${z.prag / 50 * 100}%"></i></div></div>`).join("") || '<p class="blago">Nema senzora tla.</p>';
  $("navodnjavanje-opis").textContent = (s.navodnjavanje.odluka && s.navodnjavanje.odluka.razlog) || "–";

  crtajPlan(s.plan);

  const stavke = [];
  for (const a of s.anomalije || []) stavke.push(`<li class="${a.ozbiljnost}">${a.poruka}</li>`);
  for (const z of s.odrzavanje || []) stavke.push(`<li class="${z.hitno ? "upozorenje" : ""}">${z.poruka} · za ~${fmt(z.dana_do_praga, 0)} dana</li>`);
  for (const [t, doTs] of Object.entries(s.zastita || {})) stavke.push(`<li class="upozorenje">Zaštita: ${t} isključen do ${new Date(doTs * 1000).toLocaleTimeString("hr-HR", { hour: "2-digit", minute: "2-digit" })}</li>`);
  $("upozorenja").innerHTML = stavke.join("") || '<li class="blago">Sve je u redu.</li>';

  const oblak = s.oblak.ukljuceno ? (s.oblak.greska ? "nedostupan (radi lokalno)" : "sinkronizirano") : "isključen";
  const sustav = [
    ["Način", NACIN[s.nacin] || s.nacin],
    ["Uređaji", `${(s.uredaji || []).filter((x) => x.dostupan).length}/${(s.uredaji || []).length} dostupno`],
    ["Brojilo", `${fmt(s.brojilo.konstanta, 0)} imp/kWh (${s.brojilo.izvor})`],
    ["Prognoza", s.prognoza.izvor],
    ["Oblak", oblak],
    ["Kopije", (s.kopije || []).map((k) => (k.ok ? "✓ " : "✗ ") + k.odrediste.split("/").pop()).join(", ") || "nema odredišta"],
    ["Oporavak", s.oporavak ? `snimka: ${s.oporavak.snimka}, ponovljeno ${s.oporavak.ponovljeno_zapisa}` : "–"],
  ];
  $("sustav").innerHTML = sustav.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("");
}

const PODSUSTAV = { baterija: "Baterija", bojler: "Bojler", pumpa: "Navodnjavanje", pastir: "Pastir", prognoza: "Prognoza potrošnje" };
const IZVOR = { plan: "optimizator", pravilo: "pravilo", zastita: "zaštita", rucno: "ručno", ai: "rubni AI", profil: "profil navika", kalibracija: "kalibracija" };
let naprednoUcitano = false;

function prikaziOdluke(s) {
  const o = s.odluke || {};
  $("odluke").innerHTML = Object.entries(o).map(([k, d]) => `<li><span class="pod">${PODSUSTAV[k] || k}</span>
    <b>${esc(d.odluka)}</b><span class="blago">${esc(d.razlog)}</span><br><span class="izvor ${d.izvor}">${IZVOR[d.izvor] || d.izvor}</span></li>`).join("")
    || '<li class="blago">Odluke se pojavljuju nakon prvog ciklusa.</li>';
  const ai = s.ai || {}, k = ai.kvaliteta || {}, p = ai.provjera || {};
  $("ai-stanje").textContent = ai.aktivan ? (k.koristi_se ? "Aktivan i koristi se – točniji od profila navika." :
    "Aktivan, uči i provjerava se; dok nije točniji, koristi se profil navika.") :
    (s.napredno && !s.napredno.ai ? "Isključen ručno." : "Nije primijenjen: " + (p.razlozi || []).join("; "));
  const r = p.resursi || {};
  $("ai-detalji").innerHTML = [
    ["Slobodna memorija", fmt(p.slobodno_mb, 0, " MB")], ["Memorija jezgre (RSS)", fmt(r.rss_mb, 1, " MB")],
    ["Opterećenje CPU", r.load1 === null || r.load1 === undefined ? "–" : `${fmt(r.load1, 2)} / ${r.jezgri} jezgre`],
    ["Težine modela", fmt(k.tezine_bajtova, 0, " B (int8)")], ["Zaključivanje", fmt(k.zakljucivanje_ms, 2, " ms")],
    ["Točnost AI / profil", k.mae_ai_w === null ? "–" : `${fmt(k.mae_ai_w, 0)} W / ${fmt(k.mae_profil_w, 0)} W (${k.sati_provjere} h)`],
  ].map(([a, b]) => `<dt>${a}</dt><dd>${b}</dd>`).join("");
  if (!naprednoUcitano && s.napredno) {
    $("ai-ukljucen").checked = !!s.napredno.ai;
    const r2 = document.querySelector(`input[name=bn][value="${s.napredno.baterija_nacin}"]`);
    if (r2) r2.checked = true;
    $("rucno-polja").hidden = s.napredno.baterija_nacin !== "rucno";
    naprednoUcitano = true;
  }
  $("rucna-trosila").innerHTML = ["bojler", "uticnice", "hladnjak"].filter((t) => t in (s.releji || {})).map((t) =>
    `<button type="button" class="gumb sporedno" data-trosilo="${t}" data-ukljuci="${s.releji[t] ? 0 : 1}">${{ bojler: "Bojler", uticnice: "Utičnice", hladnjak: "Hladnjak" }[t]}: ${s.releji[t] ? "isključi" : "uključi"}</button>`).join("");
}

const esc = (t) => String(t ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

document.querySelectorAll("input[name=bn]").forEach((r) => r.addEventListener("change", () => {
  $("rucno-polja").hidden = r.value !== "rucno" || !r.checked;
}));
$("spremi-napredno").addEventListener("click", async () => {
  const nacin = (document.querySelector("input[name=bn]:checked") || {}).value || "auto";
  const tijelo = { ai: $("ai-ukljucen").checked, baterija_nacin: nacin,
    rucna_snaga_w: Number($("rucno-w").value), minuta: Number($("rucno-min").value) };
  const r = await api("/api/postavke", { method: "POST", body: JSON.stringify(tijelo) });
  $("napredno-poruka").textContent = r.ok ? "Primijenjeno." : "Nije primijenjeno: " + ((await r.json()).greska || r.status);
  osvjezi();
});
$("ai-provjera").addEventListener("click", async () => {
  await api("/api/ai/provjera", { method: "POST" });
  osvjezi();
});
$("rucna-trosila").addEventListener("click", async (e) => {
  const b = e.target.closest("[data-trosilo]");
  if (!b) return;
  await api("/api/naredba", { method: "POST", body: JSON.stringify({ trosilo: b.dataset.trosilo, ukljuci: b.dataset.ukljuci === "1", minuta: 30 }) });
  osvjezi();
});

async function osvjezi() {
  try {
    const r = await api("/api/stanje");
    const s = await r.json();
    prikazi(s);
    prikaziOdluke(s);
    $("podnozje").textContent = "Radi lokalno · bez interneta nastavlja autonomno";
  } catch (e) {
    if (e.message !== "uparivanje") $("podnozje").textContent = "Jezgra trenutačno nije dostupna – pokušavam ponovno…";
  }
}

document.querySelectorAll("[data-dana]").forEach((a) => a.addEventListener("click", async (e) => {
  e.preventDefault();
  const r = await api(`/api/izvjestaj?dana=${a.dataset.dana}&format=${a.dataset.format}`);
  const blob = await r.blob();
  const url = URL.createObjectURL(blob);
  if (a.dataset.format === "html") { window.open(url, "_blank", "noopener"); return; }
  const l = document.createElement("a");
  l.href = url; l.download = `izvjestaj-${a.dataset.dana}d.${a.dataset.format}`; l.click();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}));

osvjezi();
setInterval(osvjezi, 5000);
