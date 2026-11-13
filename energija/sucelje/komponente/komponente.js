// Energija Web Components – ugradivi u bilo koju stranicu:
//
//   <script type="module" src="https://<jezgra>/komponente/komponente.js"></script>
//   <e-usteda api="https://<jezgra>" token="…"></e-usteda>
//
// Atributi (svi neobavezni): api (adresa jezgre; prazno = ista), token, prikaz="jednostavno|napredno",
// raspon="1h|6h|24h|48h|7d|30d", tema="svijetla|tamna" (inače prema sustavu).
// Izgled se prilagođava CSS varijablama --e-* na stranici domaćinu (prolaze kroz shadow DOM), npr.
//   e-usteda { --e-naglasak: #0a7d5a; --e-radijus: 12px; --e-font: "Inter", system-ui; }
// Domaćin koji ima samo svijetlu (ili samo tamnu) temu neka postavi tema="svijetla|tamna"; tko mijenja
// --e-povrsina, neka promijeni i --e-tekst / --e-tekst-2 / --e-tekst-3, inače kontrast nije zajamčen.
// Događaji: "e-greska" (detail: {status, poruka}) – npr. 401 => domaćin prikaže uparivanje.

import { EnergijaKlijent } from "../sdk/energija-sdk.js";
import { broj, graf, snaga, STIL_GRAFA, vrijeme } from "./graf.js";

const TOKENI = `
:host { display: block; box-sizing: border-box; font-family: var(--e-font, system-ui, -apple-system, "Segoe UI", sans-serif);
  --_povrsina: var(--e-povrsina, #fcfcfb); --_pozadina: var(--e-pozadina, #f6f5f1); --_tekst: var(--e-tekst, #0b0b0b);
  --_tekst2: var(--e-tekst-2, #52514e); --_tekst3: var(--e-tekst-3, #78766f); --_rub: var(--e-rub, rgba(11,11,11,.09));
  --_mreza: var(--e-mreza, #e8e7e1); --_os: var(--e-os, #c3c2b7); --_naglasak: var(--e-naglasak, #1d6b52);
  --_s1: var(--e-serija-1, #2a78d6); --_s2: var(--e-serija-2, #eb6834); --_s3: var(--e-serija-3, #1baf7a); --_s4: var(--e-serija-4, #eda100);
  --_dobro: #0ca30c; --_upozorenje: #fab219; --_ozbiljno: #ec835a; --_kriticno: #d03b3b; --_dobro-tekst: #006300;
  --_radijus: var(--e-radijus, 18px); color: var(--_tekst); }
@media (prefers-color-scheme: dark) {
  :host(:not([tema="svijetla"])) { --_povrsina: var(--e-povrsina, #1a1a19); --_pozadina: var(--e-pozadina, #0f0f0e);
    --_tekst: var(--e-tekst, #f0efec); --_tekst2: var(--e-tekst-2, #c3c2b7); --_tekst3: var(--e-tekst-3, #8f8d86);
    --_rub: var(--e-rub, rgba(255,255,255,.09)); --_mreza: var(--e-mreza, #2a2a28); --_os: var(--e-os, #3a3a37);
    --_naglasak: var(--e-naglasak, #4cc79a); --_s1: var(--e-serija-1, #3987e5); --_s2: var(--e-serija-2, #d95926);
    --_s3: var(--e-serija-3, #199e70); --_s4: var(--e-serija-4, #c98500); --_dobro-tekst: #0ca30c; }
}
:host([tema="tamna"]) { --_povrsina: var(--e-povrsina, #1a1a19); --_pozadina: var(--e-pozadina, #0f0f0e);
  --_tekst: var(--e-tekst, #f0efec); --_tekst2: var(--e-tekst-2, #c3c2b7); --_tekst3: var(--e-tekst-3, #8f8d86);
  --_rub: var(--e-rub, rgba(255,255,255,.09)); --_mreza: var(--e-mreza, #2a2a28); --_os: var(--e-os, #3a3a37);
  --_naglasak: var(--e-naglasak, #4cc79a); --_s1: var(--e-serija-1, #3987e5); --_s2: var(--e-serija-2, #d95926);
  --_s3: var(--e-serija-3, #199e70); --_s4: var(--e-serija-4, #c98500); --_dobro-tekst: #0ca30c; }
* { box-sizing: border-box; }
.kartica { background: var(--_povrsina); border: 1px solid var(--_rub); border-radius: var(--_radijus); padding: 20px; height: 100%;
  transition: opacity .2s; }
.kartica.osvjezava { opacity: .6; }
.glava { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; margin-bottom: 14px; }
h2 { margin: 0; font-size: 13px; font-weight: 500; color: var(--_tekst2); letter-spacing: .01em; }
.pod { font-size: 12px; color: var(--_tekst3); }
.vrijednost { font-size: 28px; font-weight: 600; letter-spacing: -.02em; line-height: 1.1; }
.redak { display: flex; gap: 22px; flex-wrap: wrap; }
.stat span { display: block; font-size: 12px; color: var(--_tekst3); }
.stat b { font-size: 18px; font-weight: 600; }
.cip { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: 500;
  background: color-mix(in srgb, var(--boja) 14%, transparent); color: var(--_tekst); }
.cip::before { content: ""; width: 8px; height: 8px; border-radius: 50%; background: var(--boja); }
.ikona-auto { display: inline-flex; align-items: center; gap: 4px; font-size: 11px; color: var(--_tekst3); }
button.akcija { appearance: none; border: 1px solid var(--_rub); background: var(--_pozadina); color: var(--_tekst); font: inherit;
  font-size: 13px; font-weight: 500; padding: 8px 14px; border-radius: 10px; cursor: pointer; }
button.akcija:hover { border-color: var(--_tekst3); }
button.akcija.glavna { background: var(--_tekst); color: var(--_povrsina); border-color: transparent; }
button:focus-visible, select:focus-visible, input:focus-visible { outline: 2px solid var(--_naglasak); outline-offset: 2px; }
.prazno { color: var(--_tekst3); font-size: 13px; padding: 12px 0; }
.mali-graf { margin-top: 12px; }
table.lista { width: 100%; border-collapse: collapse; font-size: 13px; }
table.lista td, table.lista th { padding: 8px 6px; border-bottom: 1px solid var(--_rub); text-align: left; vertical-align: top; }
table.lista th { color: var(--_tekst3); font-weight: 500; font-size: 12px; }
@media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
` + STIL_GRAFA;

const LIST_STILA = new CSSStyleSheet();
LIST_STILA.replaceSync(TOKENI);

/** Status (rezervirane boje) uvijek s oznakom; boja nikad sama ne nosi značenje. */
export const STATUS = { ok: ["var(--_dobro)", "U redu"], info: ["var(--_tekst3)", "Info"],
  upozorenje: ["var(--_upozorenje)", "Pažnja"], kvar: ["var(--_kriticno)", "Kvar"] };

class EBaza extends HTMLElement {
  static observedAttributes = ["api", "token", "prikaz", "raspon", "tema"];
  osvjezavanjeMs = 30000;

  constructor() {
    super();
    this.root = this.attachShadow({ mode: "open" });
    this.root.adoptedStyleSheets = [LIST_STILA];
    this.kartica = document.createElement("section");
    this.kartica.className = "kartica";
    this.root.appendChild(this.kartica);
  }

  get klijent() { return this._klijent || EnergijaKlijent.za({ api: this.getAttribute("api") || "", token: this.getAttribute("token") }); }
  set klijent(k) { this._klijent = k; }
  get prikaz() { return this.getAttribute("prikaz") || "napredno"; }
  get raspon() { return this.getAttribute("raspon") || "24h"; }

  connectedCallback() {
    this._spojen = true;
    this.osvjezi();
    this._timer = setInterval(() => this.osvjezi(), this.osvjezavanjeMs);
    if (this.uzivo) this._odjava = this.klijent.uzivo((d) => this.uzivo(d));
  }

  disconnectedCallback() {
    this._spojen = false;
    clearInterval(this._timer);
    if (this._odjava) this._odjava();
  }

  attributeChangedCallback(ime, staro, novo) {
    if (staro !== novo && this._spojen && ime !== "tema") this.osvjezi();
  }

  async osvjezi() {
    if (this._ucitava) { this._ponovi = true; return; }  // promjena usred učitavanja se ne gubi
    this._ucitava = true;
    this.kartica.classList.add("osvjezava");  // zadrži prethodni prikaz, bez treptanja
    try {
      await this.ucitaj();
    } catch (e) {
      this.dispatchEvent(new CustomEvent("e-greska", { bubbles: true, composed: true, detail: { status: e.status, poruka: e.message } }));
      if (!this._iscrtano) this.kartica.replaceChildren(Object.assign(document.createElement("p"), { className: "prazno", textContent: "Podaci trenutačno nisu dostupni." }));
    } finally {
      this.kartica.classList.remove("osvjezava");
      this._ucitava = false;
      if (this._ponovi) { this._ponovi = false; this.osvjezi(); }
    }
  }

  glava(naslov, pod) {
    const g = document.createElement("header");
    g.className = "glava";
    const h = document.createElement("h2");
    h.textContent = naslov;
    g.appendChild(h);
    const p = document.createElement("span");
    p.className = "pod";
    if (pod) p.textContent = pod;
    g.appendChild(p);
    return g;
  }

  /** Napravi ili osvježi grafikon na zadanom mjestu (zadržava instancu i stanje tablice). */
  grafikon(kljuc, kontejner, cfg) {
    this._grafovi = this._grafovi || {};
    if (this._grafovi[kljuc] && this._grafovi[kljuc].kontejner === kontejner) this._grafovi[kljuc].g.azuriraj(cfg);
    else this._grafovi[kljuc] = { kontejner, g: graf(kontejner, cfg) };
  }

  stat(naziv, vrijednost) {
    const d = document.createElement("div");
    d.className = "stat";
    const s = document.createElement("span"); s.textContent = naziv;
    const b = document.createElement("b"); b.textContent = vrijednost;
    d.append(s, b);
    return d;
  }

  cip(stanje, tekst) {
    const [boja, oznaka] = STATUS[stanje] || STATUS.info;
    const c = document.createElement("span");
    c.className = "cip";
    c.style.setProperty("--boja", boja);
    c.textContent = tekst || oznaka;
    c.setAttribute("aria-label", `${oznaka}: ${tekst || ""}`);
    return c;
  }

  /** Jednokratna izrada okvira (mjesta za grafikone se ne zamjenjuju pri osvježavanju). */
  okvir(gradi) {
    if (!this._okvir) { this.kartica.replaceChildren(); this._okvir = gradi(); this._iscrtano = true; }
    return this._okvir;
  }
}

const div = (klasa, tekst) => Object.assign(document.createElement("div"), { className: klasa || "", textContent: tekst ?? "" });
const eur = (v) => (v === null || v === undefined ? "–" : `${broj(v, 2)} €`);

// ------------------------------------------------------------------ ušteda
class EUsteda extends EBaza {
  osvjezavanjeMs = 60000;
  async ucitaj() {
    const u = await this.klijent.usteda(30);
    const r = u.razdoblja || {};
    const o = this.okvir(() => {
      const glava = this.glava("Ušteda ovaj mjesec", "procjena u odnosu na iste uređaje bez upravljanja");
      const hero = div("hero");
      hero.style.cssText = "font-size:clamp(40px,7vw,64px);font-weight:600;letter-spacing:-.03em;line-height:1;margin:6px 0 14px";
      const redak = div("redak");
      const g = div("mali-graf");
      this.kartica.append(glava, hero, redak, g);
      return { hero, redak, g };
    });
    o.hero.textContent = eur(r.mjesec?.usteda_eur);
    o.redak.replaceChildren(this.stat("Danas", eur(r.danas?.usteda_eur)), this.stat("Ukupno", eur(r.ukupno?.usteda_eur)),
      this.stat("Samoopskrba", r.mjesec?.samoopskrba == null ? "–" : `${broj(r.mjesec.samoopskrba * 100)} %`));
    if (this.prikaz === "jednostavno") { o.g.hidden = true; return; }
    const dani = u.po_danima || [];
    this.grafikon("dani", o.g, {
      kategorije: dani.map((d) => d.dan.slice(8, 10) + "." + d.dan.slice(5, 7) + "."),
      serije: [{ oznaka: "Ušteda po danu", vrijednosti: dani.map((d) => d.usteda_eur), boja: "var(--_s1)", tip: "stupci" }],
      format: (v) => eur(v), visina: 150, opis: "Ušteda po danu, zadnjih 30 dana",
    });
  }
}

// ------------------------------------------------------------------ tok energije uživo
class ETok extends EBaza {
  async ucitaj() { this.crtaj(await this.klijent.tok()); }
  uzivo(d) { if (d.tok) this.crtaj(d.tok); }
  crtaj(t) {
    const o = this.okvir(() => {
      this.kartica.append(this.glava("Tok energije", "uživo"));
      const svgNS = "http://www.w3.org/2000/svg";
      const svg = document.createElementNS(svgNS, "svg");
      svg.setAttribute("viewBox", "0 0 360 210");
      svg.setAttribute("role", "img");
      svg.style.cssText = "width:100%;height:auto;display:block";
      const stil = document.createElement("style");
      stil.textContent = `.v{stroke:var(--_mreza);stroke-width:2;fill:none;stroke-linecap:round}
        .v.on{stroke:var(--_tekst2);stroke-dasharray:3 7;animation:t 1s linear infinite}
        @keyframes t{to{stroke-dashoffset:-10}} .c{fill:var(--_pozadina);stroke:var(--_rub);stroke-width:1.5}
        .n{font-size:10px;fill:var(--_tekst3);text-anchor:middle} .w{font-size:12px;font-weight:600;fill:var(--_tekst);text-anchor:middle}`;
      this.root.appendChild(stil);
      const cvorovi = { sunce: [180, 36, "Sunce"], baterija: [60, 160, "Baterija"], kuca: [180, 160, "Kuća"], mreza: [300, 160, "Mreža"], bojler: [300, 52, "Bojler"] };
      const veze = { "sunce-kuca": "M180 64V132", "sunce-baterija": "M160 56L82 140", "baterija-kuca": "M88 160H152", "mreza-kuca": "M272 160H208", "kuca-bojler": "M200 140L282 72" };
      const v = {}; const w = {};
      for (const [k, d] of Object.entries(veze)) { const p = document.createElementNS(svgNS, "path"); p.setAttribute("d", d); p.setAttribute("class", "v"); svg.appendChild(p); v[k] = p; }
      for (const [k, [x, y, ime]] of Object.entries(cvorovi)) {
        const g = document.createElementNS(svgNS, "g"); g.setAttribute("transform", `translate(${x} ${y})`);
        const c = document.createElementNS(svgNS, "circle"); c.setAttribute("r", "28"); c.setAttribute("class", "c");
        const n = document.createElementNS(svgNS, "text"); n.setAttribute("y", "-4"); n.setAttribute("class", "n"); n.textContent = ime;
        const t2 = document.createElementNS(svgNS, "text"); t2.setAttribute("y", "12"); t2.setAttribute("class", "w");
        g.append(c, n, t2); svg.appendChild(g); w[k] = t2;
      }
      this.kartica.appendChild(svg);
      return { v, w, svg };
    });
    const bat = t.baterija_w || 0;
    o.w.sunce.textContent = snaga(t.pv_w);
    o.w.kuca.textContent = snaga(t.potrosnja_w);
    o.w.baterija.textContent = `${t.baterija_soc == null ? "" : broj(t.baterija_soc * 100) + " % "}`;
    o.w.mreza.textContent = t.mreza_dostupna ? snaga(t.mreza_w) : "nema";
    o.w.bojler.textContent = snaga(t.bojler_w);
    const on = (k, a) => o.v[k].classList.toggle("on", !!a);
    on("sunce-kuca", t.pv_w > 20 && t.potrosnja_w > 20); on("sunce-baterija", t.pv_w > 20 && bat > 20);
    on("baterija-kuca", bat < -20); on("mreza-kuca", t.mreza_w > 20); on("kuca-bojler", t.bojler_w > 20);
    o.svg.setAttribute("aria-label", `Sunce ${snaga(t.pv_w)}, kuća ${snaga(t.potrosnja_w)}, baterija ${snaga(bat)}, mreža ${snaga(t.mreza_w)}, bojler ${snaga(t.bojler_w)}`);
  }
}

// ------------------------------------------------------------------ energija kroz vrijeme
class EEnergija extends EBaza {
  osvjezavanjeMs = 60000;
  async ucitaj() {
    const p = await this.klijent.povijest(["potrosnja_w", "pv_w", "mreza_w"], this.raspon);
    const o = this.okvir(() => { const g = div(); this.kartica.append(this.glava("Potrošnja, sunce i mreža", ""), g); return { g, pod: this.kartica.querySelector(".pod") }; });
    o.pod.textContent = `zadnjih ${this.raspon}`;
    this.grafikon("e", o.g, {
      t: p.t, format: snaga, minRaspon: 100, opis: "Potrošnja, proizvodnja sunca i mreža kroz vrijeme",
      serije: [
        { oznaka: "Potrošnja", vrijednosti: p.serije.potrosnja_w, boja: "var(--_s1)", tip: "linija" },
        { oznaka: "Sunce", vrijednosti: p.serije.pv_w, boja: "var(--_s2)", tip: "povrsina" },
        { oznaka: "Mreža (+uvoz / −izvoz)", vrijednosti: p.serije.mreza_w, boja: "var(--_s3)", tip: "linija" },
      ],
    });
  }
}

// ------------------------------------------------------------------ baterija
class EBaterija extends EBaza {
  async ucitaj() {
    const [b, p] = await Promise.all([this.klijent.baterija(),
      this.prikaz === "jednostavno" ? null : this.klijent.povijest(["baterija_soc"], this.raspon)]);
    const o = this.okvir(() => { const v = div("vrijednost"); const r = div("redak"); r.style.marginTop = "10px"; const g = div("mali-graf");
      this.kartica.append(this.glava("Baterija", ""), v, r, g); return { v, r, g, pod: this.kartica.querySelector(".pod") }; });
    o.v.textContent = b.soc == null ? "–" : `${broj(b.soc * 100)} %`;
    o.pod.textContent = b.odluka ? b.odluka.odluka : "";
    o.r.replaceChildren(this.stat(b.snaga_w > 20 ? "Puni se" : b.snaga_w < -20 ? "Daje" : "Snaga", snaga(Math.abs(b.snaga_w || 0))),
      this.stat("Temperatura", b.temp_c == null ? "–" : `${broj(b.temp_c)} °C`),
      this.stat("Noćna rezerva", b.rezerva_soc == null ? "–" : `${broj(b.rezerva_soc * 100)} %`));
    if (this.prikaz === "napredno" && b.unutarnji_otpor_mohm != null) o.r.appendChild(this.stat("Unutarnji otpor", `${broj(b.unutarnji_otpor_mohm, 1)} mΩ`));
    if (!p) { o.g.hidden = true; return; }
    this.grafikon("soc", o.g, { t: p.t, format: (v) => `${broj(v)} %`, visina: 140, opis: "Napunjenost baterije",
      serije: [{ oznaka: "Napunjenost", vrijednosti: p.serije.baterija_soc, boja: "var(--_s1)", tip: "povrsina" }],
      referentne: b.rezerva_soc ? [{ vrijednost: b.rezerva_soc * 100, oznaka: "noćna rezerva" }] : [] });
  }
}

// ------------------------------------------------------------------ bojler
class EBojler extends EBaza {
  async ucitaj() {
    const [b, p] = await Promise.all([this.klijent.bojler(),
      this.prikaz === "jednostavno" ? null : this.klijent.povijest(["bojler_temp_c", "bojler_w"], this.raspon === "30d" ? "7d" : this.raspon)]);
    this._b = b;
    const o = this.okvir(() => {
      const v = div("vrijednost"); const status = div(); status.style.margin = "8px 0 12px";
      const red = div("redak"); const gumb = document.createElement("button");
      gumb.className = "akcija glavna"; gumb.type = "button"; gumb.textContent = "Zagrij vodu odmah";
      gumb.addEventListener("click", async () => {
        gumb.disabled = true;
        try { await this.klijent.naredba({ akcija: "topla_voda_sada" }); gumb.textContent = "Grije se (60 min)"; this.osvjezi(); }
        catch (e) { gumb.textContent = "Nije uspjelo"; } finally { setTimeout(() => { gumb.disabled = false; gumb.textContent = "Zagrij vodu odmah"; }, 4000); }
      });
      const gT = div("mali-graf"); const gW = div("mali-graf");
      this.kartica.append(this.glava("Topla voda", ""), v, status, red, gT, gW);
      const akcije = div(); akcije.style.marginTop = "14px"; akcije.appendChild(gumb); this.kartica.appendChild(akcije);
      return { v, status, red, gT, gW, pod: this.kartica.querySelector(".pod") };
    });
    o.v.textContent = b.temp_c == null ? "–" : `${broj(b.temp_c)} °C`;
    o.status.replaceChildren(b.spremna_topla_voda ? this.cip("ok", "Topla voda spremna") : this.cip("info", b.grije ? "Grije se" : "Hladi se – grijanje planirano"));
    o.pod.textContent = b.odluka ? `${b.odluka.odluka} · ${b.odluka.razlog}` : "";
    o.red.replaceChildren(this.stat("Grijač", b.grije ? snaga(b.snaga_w) : "isključen"),
      this.stat("Danas", `${broj(b.energija_danas_kwh, 1)} kWh`),
      this.stat("Sljedeće grijanje", b.sljedece_planirano_grijanje ? vrijeme(b.sljedece_planirano_grijanje) : "–"));
    if (!p) { o.gT.hidden = o.gW.hidden = true; return; }
    // dvije veličine (°C i W) -> dva mala grafikona s istom vremenskom osi, nikad dvije osi Y na jednom
    this.grafikon("t", o.gT, { t: p.t, format: (v) => `${broj(v)} °C`, visina: 120, odNule: false, opis: "Temperatura vode",
      serije: [{ oznaka: "Temperatura vode", vrijednosti: p.serije.bojler_temp_c, boja: "var(--_s1)", tip: "linija" }],
      referentne: [{ vrijednost: 42, oznaka: "udobnost 42 °C" }] });
    this.grafikon("w", o.gW, { t: p.t, format: snaga, minRaspon: 100, visina: 90, opis: "Snaga grijača bojlera",
      serije: [{ oznaka: "Grijač", vrijednosti: p.serije.bojler_w, boja: "var(--_s2)", tip: "povrsina" }] });
  }
  uzivo(d) {
    if (d.bojler_temp_c == null || !this._okvir) return;
    this._okvir.v.textContent = `${broj(d.bojler_temp_c)} °C`;
  }
}

// ------------------------------------------------------------------ sunčani paneli
class ESolar extends EBaza {
  async ucitaj() {
    const [s, p] = await Promise.all([this.klijent.solar(),
      this.prikaz === "jednostavno" ? null : this.klijent.povijest(["pv_w", "pv_prognoza_w"], this.raspon === "30d" || this.raspon === "7d" ? "48h" : this.raspon)]);
    const o = this.okvir(() => { const v = div("vrijednost"); const r = div("redak"); r.style.marginTop = "10px"; const g = div("mali-graf");
      this.kartica.append(this.glava("Sunčani paneli", ""), v, r, g); return { v, r, g, pod: this.kartica.querySelector(".pod") }; });
    o.v.textContent = snaga(s.snaga_w);
    o.pod.textContent = `${broj(s.instalirano_kwp, 1)} kWp · prognoza: ${s.izvor_prognoze || "–"}`;
    o.r.replaceChildren(this.stat("Danas", `${broj(s.danas_kwh, 1)} kWh`), this.stat("Prognoza danas", `${broj(s.prognoza_danas_kwh, 1)} kWh`),
      this.stat("Učinak prema očekivanom", s.ucinak_prema_ocekivanom == null ? "–" : `${broj(s.ucinak_prema_ocekivanom * 100)} %`));
    if (!p) { o.g.hidden = true; return; }
    this.grafikon("pv", o.g, { t: p.t, format: snaga, minRaspon: 100, visina: 150, opis: "Proizvodnja panela i prognoza",
      serije: [{ oznaka: "Proizvodnja", vrijednosti: p.serije.pv_w, boja: "var(--_s2)", tip: "povrsina" },
               { oznaka: "Prognoza", vrijednosti: p.serije.pv_prognoza_w, boja: "var(--_s2)", tip: "linija", crtkano: true }] });
  }
}

// ------------------------------------------------------------------ električni pastir
const OPIS_DIONICE = { ispravna: ["ok", "ispravna"], slaba: ["upozorenje", "slaba"], izolirana: ["kvar", "izolirana"],
  prekid: ["upozorenje", "prekid – napaja se s druge strane"], bez_napona: ["kvar", "bez napona"], nema_mjerenja: ["info", "nema mjerenja"] };

class EPastir extends EBaza {
  async ucitaj() {
    const p = await this.klijent.pastir();
    const n = p.dionice.length;
    const h = this.prikaz === "jednostavno" ? null
      : await this.klijent.povijest(p.dionice.map((d) => `pastir_v${d.dionica}_kv`), this.raspon === "30d" ? "48h" : this.raspon);
    const o = this.okvir(() => { const status = div(); const mapa = div(); mapa.style.cssText = "display:grid;gap:8px;margin:14px 0";
      const r = div("redak"); const g = div("mali-graf");
      this.kartica.append(this.glava("Električni pastir", ""), status, mapa, r, g); return { status, mapa, r, g, pod: this.kartica.querySelector(".pod") }; });
    const ok = p.nacin === "normalno";
    o.status.replaceChildren(this.cip(ok ? "ok" : p.nacin === "prekid" ? "upozorenje" : "kvar",
      ok ? "Ograda pod naponom" : (p.dogadjaji.at(-1)?.poruka || p.nacin)));
    o.pod.textContent = `${n} dionice · prag ${broj(p.prag_kv)} kV`;
    o.mapa.style.gridTemplateColumns = `repeat(${n}, minmax(0,1fr))`;
    o.mapa.replaceChildren(...p.dionice.map((d) => {
      const [st, opis] = OPIS_DIONICE[d.stanje] || ["info", d.stanje];
      const k = div(); k.style.cssText = "text-align:center;font-size:12px;color:var(--_tekst2)";
      const crta = div(); crta.style.cssText = `height:6px;border-radius:3px;margin-bottom:6px;background:${STATUS[st][0]};${st === "kvar" ? "opacity:.55" : ""}`;
      const kv = div("", d.kv == null ? "–" : `${broj(d.kv, 1)} kV`); kv.style.cssText = "font-weight:600;color:var(--_tekst)";
      k.append(crta, kv, div("", `${d.dionica} · ${opis}`));
      k.setAttribute("aria-label", `Dionica ${d.dionica}: ${opis}, ${d.kv ?? "nema"} kV`);
      return k;
    }));
    o.r.replaceChildren(this.stat("Impuls", p.snaga_impulsa < 1 ? "štedni" : "puni"),
      this.stat("Baterija aparata", p.baterija_aparata == null ? "–" : `${broj(p.baterija_aparata * 100)} %`),
      this.stat("Dostupnost", p.dostupnost == null ? "–" : `${broj(p.dostupnost * 100, 1)} %`));
    if (!h) { o.g.hidden = true; return; }
    const boje = ["var(--_s1)", "var(--_s2)", "var(--_s3)", "var(--_s4)"];
    this.grafikon("kv", o.g, { t: h.t, format: (v) => `${broj(v, 1)} kV`, visina: 160, opis: "Napon ograde po dionicama",
      serije: p.dionice.slice(0, 4).map((d, i) => ({ oznaka: `Dionica ${d.dionica}`, vrijednosti: h.serije[`pastir_v${d.dionica}_kv`], boja: boje[i], tip: "linija" })),
      referentne: [{ vrijednost: p.prag_kv, oznaka: `prag ${broj(p.prag_kv)} kV` }] });
  }
  uzivo(d) { if (this._okvir && d.pastir && d.pastir !== this._zadnji) { this._zadnji = d.pastir; this.osvjezi(); } }
}

// ------------------------------------------------------------------ navodnjavanje
class ENavodnjavanje extends EBaza {
  async ucitaj() {
    const n = await this.klijent.navodnjavanje();
    const h = this.prikaz === "jednostavno" || !n.zone.length ? null
      : await this.klijent.povijest(n.zone.map((z) => `tlo_${z.zona}_vlaga`), this.raspon === "30d" ? "7d" : this.raspon);
    const o = this.okvir(() => { const status = div(); const zone = div(); zone.style.cssText = "display:grid;gap:12px;margin:14px 0";
      const r = div("redak"); const g = div("mali-graf");
      this.kartica.append(this.glava("Navodnjavanje", ""), status, zone, r, g); return { status, zone, r, g, pod: this.kartica.querySelector(".pod") }; });
    o.status.replaceChildren(n.aktivna_zona ? this.cip("info", `Zalijeva zonu ${n.aktivna_zona}`) : this.cip("ok", n.odluka?.razlog || "Vlaga u redu"));
    o.pod.textContent = n.kisa_12h_mm == null ? "kiša: nema prognoze" : `kiša sljedećih 12 h: ${broj(n.kisa_12h_mm, 1)} mm`;
    o.zone.replaceChildren(...n.zone.map((z) => {
      const red = div(); const zag = div(); zag.style.cssText = "display:flex;justify-content:space-between;font-size:13px;margin-bottom:6px";
      zag.append(div("", `Zona ${z.zona.replace("z", "")}`), Object.assign(document.createElement("b"), { textContent: z.vlaga == null ? "–" : `${broj(z.vlaga)} %` }));
      const traka = div(); traka.style.cssText = "position:relative;height:8px;border-radius:4px;background:var(--_mreza)";
      const pun = div(); pun.style.cssText = `position:absolute;inset:0 auto 0 0;border-radius:4px;background:var(--_s1);width:${Math.min(100, (z.vlaga || 0) / 50 * 100)}%`;
      const prag = div(); prag.style.cssText = `position:absolute;top:-3px;bottom:-3px;width:2px;background:var(--_tekst2);left:${z.prag / 50 * 100}%`;
      prag.title = `prag ${z.prag} %`;
      traka.append(pun, prag); red.append(zag, traka); return red;
    }));
    o.r.replaceChildren(this.stat("Pumpa", n.pumpa ? "radi" : "miruje"), this.stat("Ušteđeno vode (kiša)", `${broj(n.usteda_vode_min)} min`));
    if (!h) { o.g.hidden = true; return; }
    const boje = ["var(--_s1)", "var(--_s2)", "var(--_s3)", "var(--_s4)"];
    this.grafikon("tlo", o.g, { t: h.t, format: (v) => `${broj(v)} %`, visina: 150, odNule: false, opis: "Vlaga tla po zonama",
      serije: n.zone.slice(0, 4).map((z, i) => ({ oznaka: `Zona ${z.zona.replace("z", "")}`, vrijednosti: h.serije[`tlo_${z.zona}_vlaga`], boja: boje[i], tip: "linija" })),
      referentne: n.zone.length ? [{ vrijednost: n.zone[0].prag, oznaka: `prag ${broj(n.zone[0].prag)} %` }] : [] });
  }
}

// ------------------------------------------------------------------ pokazatelji automatike
const IZVOR = { plan: "optimizator", pravilo: "pravilo", zastita: "zaštita", rucno: "ručno", ai: "rubni AI", profil: "profil navika",
  kalibracija: "kalibracija", mreza: "zahtjev mreže" };
const PODSUSTAV = { baterija: "Baterija", bojler: "Bojler", pumpa: "Navodnjavanje", pastir: "Pastir", prognoza: "Prognoza potrošnje" };

class EStatus extends EBaza {
  osvjezavanjeMs = 15000;
  async ucitaj() { const p = await this.klijent.pregled(); this.crtaj(p.status); }
  uzivo(d) { if (d.status) this.crtaj(d.status); }
  crtaj(status) {
    this.kartica.style.cssText = "padding:14px 16px";
    const red = div(); red.style.cssText = "display:flex;flex-wrap:wrap;gap:8px";
    red.append(...status.map((s) => { const c = this.cip(s.stanje, s.tekst); if (s.automatski) c.title = "Automatika je reagirala sama"; return c; }));
    this.kartica.replaceChildren(red);
    this._iscrtano = true;
  }
}

class EOdluke extends EBaza {
  osvjezavanjeMs = 15000;
  async ucitaj() {
    const r = await this.klijent.odluke();
    const o = this.okvir(() => { const l = div(); l.style.cssText = "display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px";
      this.kartica.append(this.glava("Što automatika radi i zašto", "uživo"), l); return { l }; });
    o.l.replaceChildren(...Object.entries(r.odluke).map(([k, d]) => {
      const c = div(); c.style.cssText = "border:1px solid var(--_rub);border-radius:12px;padding:12px";
      const izvor = div("ikona-auto", `● ${IZVOR[d.izvor] || d.izvor}`);
      c.append(div("pod", PODSUSTAV[k] || k), Object.assign(document.createElement("b"), { textContent: d.odluka }),
        Object.assign(div("", d.razlog), { style: "font-size:13px;color:var(--_tekst2);margin:4px 0 8px" }), izvor);
      return c;
    }));
  }
}

// ------------------------------------------------------------------ kontrolni centar: dijagnostika
class EDijagnostika extends EBaza {
  osvjezavanjeMs = 20000;
  async ucitaj() {
    const [d, dog] = await Promise.all([this.klijent.dijagnostika(), this.klijent.dogadjaji(24).catch(() => ({ dogadjaji: [] }))]);
    this.kartica.replaceChildren(this.glava("Dijagnostika", `jezgra ${d.id} · ${d.nacin_rada}`));
    const mreza = div(); mreza.style.cssText = "display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:20px";
    const blok = (naslov, redovi) => {
      const b = div(); const h = document.createElement("h2"); h.textContent = naslov; h.style.marginBottom = "8px";
      const t = document.createElement("table"); t.className = "lista";
      for (const [k, v, st] of redovi) {
        const tr = t.insertRow(); tr.insertCell().textContent = k; const td = tr.insertCell();
        if (st) td.appendChild(this.cip(st, v)); else td.textContent = v;
      }
      b.append(h, t); return b;
    };
    const r = d.resursi || {};
    const ai = d.ai || {}; const kv = ai.kvaliteta || {};
    mreza.append(
      blok("Uređaji", d.uredaji.map((u) => [`${u.id}`, `${u.protokol}${u.greska ? " – " + u.greska : ""}`, u.dostupan ? "ok" : "kvar"])),
      blok("Zadaci i oporavak", [
        ["Sigurno stanje", d.sigurno_stanje ? "aktivno" : "ne", d.sigurno_stanje ? "kvar" : "ok"],
        ...Object.entries(d.zadaci?.zadaci || {}).map(([k, z]) => [k, `${z.padova} padova${z.greska ? " · " + z.greska : ""}`, z.greska ? "upozorenje" : "ok"]),
        ["Dnevnik", `${d.dnevnik.segmenata} segmenata · ${broj(d.dnevnik.bajtova / 1048576, 1)} MB`],
        ["Oporavak", `snimka: ${d.dnevnik.oporavak.snimka}, ponovljeno ${d.dnevnik.oporavak.ponovljeno_zapisa}`]]),
      blok("Resursi uređaja", [
        ["Opterećenje CPU", r.load1 == null ? "–" : `${broj(r.load1, 2)} / ${r.jezgri} jezgre`, r.load1 > 0.8 * r.jezgri ? "upozorenje" : null],
        ["Memorija jezgre", r.rss_mb == null ? "–" : `${broj(r.rss_mb)} MB`], ["Slobodna memorija", r.mem_slobodno_mb == null ? "–" : `${broj(r.mem_slobodno_mb)} MB`],
        ["Temperatura CPU", r.cpu_temp_c == null ? "–" : `${broj(r.cpu_temp_c)} °C`]]),
      blok("Rubni AI", [["Profil", ai.aktivan ? "aktivan" : "nije primijenjen", ai.aktivan ? "ok" : "info"],
        ["Koristi se", kv.koristi_se ? "da" : "ne – profil navika točniji"], ["Točnost AI / profil", kv.mae_ai_w == null ? "–" : `${broj(kv.mae_ai_w)} / ${broj(kv.mae_profil_w)} W`],
        ["Težine", `${kv.tezine_bajtova ?? "–"} B int8`]]),
      blok("Veze", [["Oblak", d.oblak.ukljuceno ? (d.oblak.greska ? "nedostupan" : "sinkronizirano") : "isključen", d.oblak.greska ? "upozorenje" : null],
        ["Prognoza", d.prognoza.greska ? `zamjenski model (${d.prognoza.greska.slice(0, 40)})` : `${d.prognoza.sati} h`, d.prognoza.greska ? "upozorenje" : "ok"],
        ["Tarifa", d.tarife.dinamicka ? "dinamička" : "VT/NT", null], ["Brojilo", `${broj(d.brojilo.konstanta)} imp/kWh (${d.brojilo.izvor})`],
        ...d.kopije.map((k) => [`Kopija ${k.odrediste.split("/").pop()}`, k.ok ? "uspjela" : k.greska, k.ok ? "ok" : "kvar"])]),
      blok("Upozorenja i održavanje", [...d.anomalije.map((a) => [a.kanal, a.poruka, a.ozbiljnost === "kriticno" ? "kvar" : "upozorenje"]),
        ...d.odrzavanje.map((z) => [z.pokazatelj, `${z.poruka} (za ~${broj(z.dana_do_praga)} dana)`, z.hitno ? "upozorenje" : "info"]),
        ...Object.entries(d.zastita).map(([k, v]) => [`Zaštita: ${k}`, `do ${vrijeme(v)}`, "upozorenje"])].concat(
        d.anomalije.length || d.odrzavanje.length ? [] : [["Stanje", "bez upozorenja", "ok"]])),
    );
    const dg = document.createElement("details"); dg.style.marginTop = "18px";
    const sm = document.createElement("summary"); sm.textContent = `Događaji (24 h): ${dog.dogadjaji.length}`; sm.style.cursor = "pointer";
    const t = document.createElement("table"); t.className = "lista";
    for (const e of dog.dogadjaji.slice(-60).reverse()) { const tr = t.insertRow(); tr.insertCell().textContent = vrijeme(e.ts, true); tr.insertCell().textContent = e.vrsta; tr.insertCell().textContent = e.poruka; }
    dg.append(sm, t);
    this.kartica.append(mreza, dg);
    this._iscrtano = true;
  }
}

// ------------------------------------------------------------------ kontrolni centar: upravljanje
class EUpravljanje extends EBaza {
  osvjezavanjeMs = 60000;
  async ucitaj() {
    const [p, f, z] = await Promise.all([this.klijent.postavke(), this.klijent.fleksibilnost(), this.klijent.zahtjeviMreze()]);
    this.kartica.replaceChildren(this.glava("Upravljanje", "sigurnosne granice i zaštita pastira uvijek imaju prednost"));
    const m = div(); m.style.cssText = "display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:22px";
    // baterija
    const b = div(); const hb = document.createElement("h2"); hb.textContent = "Baterija – ručno premošćivanje";
    const sel = document.createElement("select");
    sel.style.cssText = "width:100%;padding:8px;border-radius:10px;border:1px solid var(--_rub);background:var(--_pozadina);color:var(--_tekst);font:inherit;margin:8px 0";
    for (const [v, t] of [["auto", "Automatski (preporučeno)"], ["vlastita", "Samo vlastita potrošnja"], ["bez_punjenja_iz_mreze", "Ne puni iz mreže"]]) {
      sel.add(new Option(t, v, false, p.napredno.baterija_nacin === v));
    }
    const ai = document.createElement("label"); ai.style.cssText = "display:flex;gap:8px;align-items:center;font-size:13px;margin:8px 0";
    const aiC = Object.assign(document.createElement("input"), { type: "checkbox", checked: !!p.napredno.ai }); ai.append(aiC, "Rubni AI prognoza");
    const spremi = Object.assign(document.createElement("button"), { className: "akcija glavna", type: "button", textContent: "Primijeni" });
    const poruka = div("pod");
    spremi.addEventListener("click", async () => {
      try { await this.klijent.postavke({ baterija_nacin: sel.value, ai: aiC.checked }); poruka.textContent = "Primijenjeno."; }
      catch (e) { poruka.textContent = `Nije primijenjeno: ${e.message}`; }
    });
    b.append(hb, sel, ai, spremi, poruka);
    // fleksibilnost i mreža
    const fl = div(); const hf = document.createElement("h2"); hf.textContent = "Pametna mreža";
    const t = document.createElement("table"); t.className = "lista";
    for (const [k, v] of [["Može smanjiti uvoz", `${snaga(f.smanjenje_uvoza_w)} · ${broj(f.smanjenje_uvoza_h, 1)} h`],
      ["Može povećati potrošnju", `${snaga(f.povecanje_potrosnje_w)} · ${broj(f.povecanje_potrosnje_h, 1)} h`],
      ["Aktivni zahtjevi", String(z.zahtjevi.length)]]) { const tr = t.insertRow(); tr.insertCell().textContent = k; tr.insertCell().textContent = v; }
    for (const zh of z.zahtjevi) { const tr = t.insertRow(); tr.insertCell().textContent = `${zh.izvor}: ${zh.vrsta}`; tr.insertCell().textContent = `${snaga(zh.snaga_w)} do ${vrijeme(zh.do)}`; }
    fl.append(hf, t);
    // pozivnice
    const pz = div(); const hp = document.createElement("h2"); hp.textContent = "Pristup";
    const opis = div("pod", "Jednokratni kod (1 h) za mobitel stanara ili sustav koji se integrira.");
    const red = div(); red.style.cssText = "display:flex;gap:8px;margin:10px 0;flex-wrap:wrap";
    const kod = div("vrijednost"); kod.style.letterSpacing = ".12em";
    for (const [u, tx] of [["stanar", "Kod za stanara"], ["integracija", "Kod za integraciju"]]) {
      const g = Object.assign(document.createElement("button"), { className: "akcija", type: "button", textContent: tx });
      g.addEventListener("click", async () => { try { const r = await this.klijent.pozivnica(u); kod.textContent = r.kod; } catch (e) { kod.textContent = "–"; } });
      red.appendChild(g);
    }
    pz.append(hp, opis, red, kod);
    m.append(b, fl, pz);
    this.kartica.appendChild(m);
    this._iscrtano = true;
  }
}

const KOMPONENTE = { "e-usteda": EUsteda, "e-tok": ETok, "e-energija": EEnergija, "e-baterija": EBaterija, "e-bojler": EBojler,
  "e-solar": ESolar, "e-pastir": EPastir, "e-navodnjavanje": ENavodnjavanje, "e-status": EStatus, "e-odluke": EOdluke,
  "e-dijagnostika": EDijagnostika, "e-upravljanje": EUpravljanje };
for (const [ime, klasa] of Object.entries(KOMPONENTE)) if (!customElements.get(ime)) customElements.define(ime, klasa);

export { EnergijaKlijent, KOMPONENTE };
