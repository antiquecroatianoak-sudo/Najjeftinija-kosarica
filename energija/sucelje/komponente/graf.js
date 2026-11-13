// Motor grafikona (SVG, bez ovisnosti). Pravila: jedna os Y (nikad dvije), linije 2 px, površina 10 %,
// stupci ≤ 24 px sa zaobljenim krajem od 4 px, tanka puna mreža, izravne oznake na kraju, pratilica + oblačić
// sa svim serijama, tipkovnica, i tablični prikaz kao jednakovrijedan pristup podacima.

const NS = "http://www.w3.org/2000/svg";
const el = (ime, atr = {}, roditelj) => {
  const e = document.createElementNS(NS, ime);
  for (const [k, v] of Object.entries(atr)) e.setAttribute(k, v);
  if (roditelj) roditelj.appendChild(e);
  return e;
};
const html = (ime, klasa, roditelj, tekst) => {
  const e = document.createElement(ime);
  if (klasa) e.className = klasa;
  if (tekst !== undefined) e.textContent = tekst;
  if (roditelj) roditelj.appendChild(e);
  return e;
};

export const broj = (v, dec = 0) => v === null || v === undefined || Number.isNaN(v) ? "–"
  : Number(v).toLocaleString("hr-HR", { minimumFractionDigits: dec, maximumFractionDigits: dec });
export const snaga = (w) => w === null || w === undefined ? "–" : Math.abs(w) >= 1000 ? `${broj(w / 1000, 1)} kW` : `${broj(w)} W`;
export const vrijeme = (ts, dugo) => new Date(ts * 1000).toLocaleString("hr-HR", dugo
  ? { day: "numeric", month: "numeric", hour: "2-digit", minute: "2-digit" } : { hour: "2-digit", minute: "2-digit" });

function lijepiKoraci(min, max, n = 4) {
  if (min === max) { max = min + 1; }
  const sirovo = (max - min) / n;
  const mag = 10 ** Math.floor(Math.log10(sirovo));
  const korak = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((k) => k >= sirovo) || 10 * mag;
  const od = Math.floor(min / korak) * korak;
  const out = [];
  for (let v = od; v <= max + korak * 0.5; v += korak) out.push(Math.round(v / korak) * korak);
  return out;
}

/**
 * graf(kontejner, cfg) -> { azuriraj(cfg) }
 * cfg: { t: [unix s] | kategorije: [tekst], serije: [{ oznaka, vrijednosti, boja, tip: "linija"|"povrsina"|"stupci",
 *        crtkano }], format: (v) => tekst, referentne: [{ vrijednost, oznaka }], visina, odNule, opis }
 */
export function graf(kontejner, cfg) {
  const korijen = html("figure", "graf", kontejner);
  const legenda = html("div", "legenda", korijen);
  const plot = html("div", "plot", korijen);
  const svg = el("svg", { role: "img", tabindex: "0" }, plot);
  const oblacic = html("div", "oblacic", plot);
  oblacic.hidden = true;
  const alati = html("div", "alati", korijen);
  const gumb = html("button", "tablica-gumb", alati, "Prikaži tablicu");
  gumb.type = "button";
  const tablica = html("div", "tablica", korijen);
  tablica.hidden = true;
  gumb.addEventListener("click", () => {
    tablica.hidden = !tablica.hidden;
    gumb.textContent = tablica.hidden ? "Prikaži tablicu" : "Sakrij tablicu";
    gumb.setAttribute("aria-expanded", String(!tablica.hidden));
    if (!tablica.hidden) crtajTablicu();
  });
  let c = cfg, sirina = 0, idx = null, geo = null;

  function format(v) { return c.format ? c.format(v) : broj(v); }
  function xOznaka(i, zaOs = false) {
    if (c.kategorije) return c.kategorije[i];
    const raspon = c.t[c.t.length - 1] - c.t[0];
    const d = new Date(c.t[i] * 1000);
    if (zaOs && raspon > 2 * 86400) return `${d.getDate()}. ${d.getMonth() + 1}.`;
    if (zaOs && raspon > 20 * 3600 && (i === 0 || i === c.t.length - 1)) return `${d.getDate()}. ${d.getMonth() + 1}. ${vrijeme(c.t[i])}`;
    return vrijeme(c.t[i], raspon > 86400);
  }

  function crtajLegendu() {
    legenda.replaceChildren();
    if (c.serije.length < 2) { legenda.hidden = true; return; }
    legenda.hidden = false;
    for (const s of c.serije) {
      const st = html("span", "stavka", legenda);
      const k = html("i", `kljuc ${s.tip === "linija" || !s.tip ? "linija" : "pravokutnik"}${s.crtkano ? " crtkano" : ""}`, st);
      k.style.setProperty("--boja", s.boja);
      html("span", "", st, s.oznaka);
    }
  }

  function crtaj() {
    sirina = Math.max(240, kontejner.clientWidth || 600);
    const V = c.visina || 200, L = 48, R = c.serije.length <= 4 && !c.kategorije ? 70 : 12, T = 12, B = 26;
    const n = c.kategorije ? c.kategorije.length : c.t.length;
    svg.setAttribute("viewBox", `0 0 ${sirina} ${V}`);
    svg.setAttribute("height", V);
    svg.setAttribute("aria-label", c.opis || "Grafikon");
    svg.replaceChildren();
    const sve = c.serije.flatMap((s) => s.vrijednosti.filter((v) => v !== null && v !== undefined));
    (c.referentne || []).forEach((r) => sve.push(r.vrijednost));
    let mn = sve.length ? Math.min(...sve) : 0, mx = sve.length ? Math.max(...sve) : 1;
    if (c.odNule !== false) { mn = Math.min(0, mn); mx = Math.max(0, mx); }
    if (c.minRaspon && mx - mn < c.minRaspon) mx = mn + c.minRaspon;  // bez ponovljenih oznaka kad je sve ≈ 0
    const koraci = lijepiKoraci(mn, mx);
    mn = Math.min(mn, koraci[0]); mx = Math.max(mx, koraci[koraci.length - 1]);
    const y = (v) => T + (V - T - B) * (1 - (v - mn) / (mx - mn || 1));
    const pojas = (sirina - L - R) / Math.max(1, c.kategorije || c.serije.some((s) => s.tip === "stupci") ? n : n - 1);
    const x = (i) => c.kategorije || c.serije.some((s) => s.tip === "stupci") ? L + pojas * (i + 0.5) : L + pojas * i;
    geo = { x, y, n, L, R, T, B, V, pojas };

    const mreza = el("g", { class: "mreza" }, svg);
    for (const k of koraci) {
      el("line", { x1: L, x2: sirina - R, y1: y(k), y2: y(k), class: k === 0 ? "nula" : "" }, mreza);
      el("text", { x: L - 8, y: y(k) + 4, "text-anchor": "end", class: "os" }, mreza).textContent = format(k);
    }
    const dugo = !c.kategorije && c.t[c.t.length - 1] - c.t[0] > 86400;
    const brojX = Math.min(n, Math.max(2, Math.floor((sirina - L - R) / (dugo ? 110 : 80))));
    for (let j = 0; j < brojX; j++) {
      const i = Math.round((j * (n - 1)) / Math.max(1, brojX - 1));
      el("text", { x: x(i), y: V - 6, "text-anchor": j === 0 && !c.kategorije ? "start" : j === brojX - 1 && !c.kategorije ? "end" : "middle", class: "os" }, mreza)
        .textContent = xOznaka(i, true);
    }
    for (const r of c.referentne || []) {
      el("line", { x1: L, x2: sirina - R, y1: y(r.vrijednost), y2: y(r.vrijednost), class: "referentna" }, svg);
      el("text", { x: L + 4, y: y(r.vrijednost) - 4, class: "os" }, svg).textContent = r.oznaka;
    }

    const krajevi = [];
    const stupaca = c.serije.filter((s) => s.tip === "stupci").length;
    c.serije.forEach((s, si) => {
      if (s.tip === "stupci") {
        const w = Math.min(24, pojas * 0.7 / stupaca) - 2;  // 2 px razmak između susjednih stupaca
        const pomak = (si - (stupaca - 1) / 2) * (w + 2);
        s.vrijednosti.forEach((v, i) => {
          if (v === null || v === undefined || v === 0) return;
          const x0 = x(i) - w / 2 + pomak, y0 = y(0), y1 = y(v), r = Math.min(4, Math.abs(y0 - y1), w / 2);
          const d = v > 0
            ? `M${x0},${y0}V${y1 + r}Q${x0},${y1} ${x0 + r},${y1}H${x0 + w - r}Q${x0 + w},${y1} ${x0 + w},${y1 + r}V${y0}Z`
            : `M${x0},${y0}V${y1 - r}Q${x0},${y1} ${x0 + r},${y1}H${x0 + w - r}Q${x0 + w},${y1} ${x0 + w},${y1 - r}V${y0}Z`;
          el("path", { d, fill: s.boja, class: "stupac" }, svg);
        });
        return;
      }
      let d = "", dP = "", otvoren = false, zadnji = null, pocetakP = null;
      s.vrijednosti.forEach((v, i) => {
        if (v === null || v === undefined) {
          if (otvoren && s.tip === "povrsina" && pocetakP !== null) dP += `L${x(zadnji)},${y(Math.max(mn, 0))}L${x(pocetakP)},${y(Math.max(mn, 0))}Z`;
          otvoren = false; return;
        }
        d += `${otvoren ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`;
        if (s.tip === "povrsina") { dP += `${otvoren ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`; if (!otvoren) pocetakP = i; }
        otvoren = true; zadnji = i;
      });
      if (s.tip === "povrsina" && otvoren && pocetakP !== null) dP += `L${x(zadnji)},${y(Math.max(mn, 0))}L${x(pocetakP)},${y(Math.max(mn, 0))}Z`;
      if (dP) el("path", { d: dP, fill: s.boja, class: "povrsina" }, svg);
      if (d) el("path", { d, stroke: s.boja, class: `linija${s.crtkano ? " crtkano" : ""}` }, svg);
      if (zadnji !== null && R > 20) krajevi.push({ s, i: zadnji, v: s.vrijednosti[zadnji] });
    });
    // izravne oznake na kraju (razmaknute da se ne preklapaju)
    krajevi.sort((a, b) => y(a.v) - y(b.v));
    let prosli = -Infinity;
    for (const k of krajevi) {
      const yy = Math.max(y(k.v), prosli + 13);
      prosli = yy;
      el("circle", { cx: x(k.i), cy: y(k.v), r: 4, fill: k.s.boja, class: "tocka" }, svg);
      const t = el("text", { x: x(k.i) + 8, y: yy + 4, class: "kraj" }, svg);
      t.textContent = format(k.v);
    }
    // sloj za pratilicu (veći od oznaka)
    const pratilica = el("line", { y1: T, y2: V - B, class: "pratilica", visibility: "hidden" }, svg);
    const tockeP = el("g", {}, svg);
    const pogodak = el("rect", { x: L, y: T, width: sirina - L - R, height: V - T - B, fill: "transparent" }, svg);
    const pokazi = (i) => {
      idx = Math.max(0, Math.min(n - 1, i));
      pratilica.setAttribute("x1", x(idx)); pratilica.setAttribute("x2", x(idx));
      pratilica.setAttribute("visibility", "visible");
      tockeP.replaceChildren();
      oblacic.replaceChildren();
      html("div", "naslov", oblacic, xOznaka(idx));
      for (const s of c.serije) {
        const v = s.vrijednosti[idx];
        if (s.tip !== "stupci" && v !== null && v !== undefined) el("circle", { cx: x(idx), cy: y(v), r: 4, fill: s.boja, class: "tocka" }, tockeP);
        const red = html("div", "red", oblacic);
        const k = html("i", `kljuc linija${s.crtkano ? " crtkano" : ""}`, red);
        k.style.setProperty("--boja", s.boja);
        html("strong", "", red, format(v));
        html("span", "", red, s.oznaka);
      }
      oblacic.hidden = false;
      const lijevo = (x(idx) / sirina) * plot.clientWidth;
      oblacic.style.left = `${Math.min(Math.max(8, lijevo + 12), plot.clientWidth - oblacic.offsetWidth - 8)}px`;
      oblacic.style.top = "8px";
    };
    const sakrij = () => { pratilica.setAttribute("visibility", "hidden"); tockeP.replaceChildren(); oblacic.hidden = true; idx = null; };
    pogodak.addEventListener("pointermove", (e) => {
      const r = svg.getBoundingClientRect();
      const px = ((e.clientX - r.left) / r.width) * sirina;
      const i = c.kategorije || c.serije.some((s) => s.tip === "stupci") ? Math.floor((px - L) / pojas) : Math.round((px - L) / pojas);
      pokazi(i);
    });
    pogodak.addEventListener("pointerleave", sakrij);
    svg.onkeydown = (e) => {
      if (e.key === "ArrowRight" || e.key === "ArrowLeft") { e.preventDefault(); pokazi((idx ?? n - 1) + (e.key === "ArrowRight" ? 1 : -1)); }
      if (e.key === "Escape") sakrij();
    };
    svg.onblur = sakrij;
  }

  function crtajTablicu() {
    tablica.replaceChildren();
    const t = html("table", "", tablica);
    const zag = html("tr", "", html("thead", "", t));
    html("th", "", zag, c.kategorije ? "Dan" : "Vrijeme");
    c.serije.forEach((s) => html("th", "", zag, s.oznaka));
    const tb = html("tbody", "", t);
    const n = c.kategorije ? c.kategorije.length : c.t.length;
    for (let i = n - 1; i >= 0; i--) {
      if (c.serije.every((s) => s.vrijednosti[i] === null || s.vrijednosti[i] === undefined)) continue;
      const r = html("tr", "", tb);
      html("td", "", r, xOznaka(i));
      c.serije.forEach((s) => html("td", "broj", r, format(s.vrijednosti[i])));
    }
  }

  crtajLegendu();
  crtaj();
  const ro = new ResizeObserver(() => { if (Math.abs((kontejner.clientWidth || 0) - sirina) > 4) crtaj(); });
  ro.observe(kontejner);
  return {
    azuriraj(novi) { c = novi; crtajLegendu(); crtaj(); if (!tablica.hidden) crtajTablicu(); },
    unisti() { ro.disconnect(); korijen.remove(); },
  };
}

export const STIL_GRAFA = `
.graf { margin: 0; }
.legenda { display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: 12px; color: var(--_tekst2); margin: 0 0 8px; }
.legenda .stavka { display: inline-flex; align-items: center; gap: 6px; }
.kljuc { display: inline-block; flex: none; }
.kljuc.linija { width: 14px; height: 0; border-top: 2px solid var(--boja); }
.kljuc.linija.crtkano { border-top-style: dashed; }
.kljuc.pravokutnik { width: 10px; height: 10px; border-radius: 2px; background: var(--boja); }
.plot { position: relative; }
.plot svg { display: block; width: 100%; overflow: visible; }
.plot svg:focus-visible { outline: 2px solid var(--_naglasak); outline-offset: 4px; border-radius: 6px; }
.mreza line { stroke: var(--_mreza); stroke-width: 1; }
.mreza line.nula { stroke: var(--_os); }
.os { font-size: 11px; fill: var(--_tekst3); font-variant-numeric: tabular-nums; }
.kraj { font-size: 11px; fill: var(--_tekst2); font-variant-numeric: tabular-nums; }
.linija { fill: none; stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
.linija.crtkano { stroke-dasharray: 5 4; }
.povrsina { opacity: 0.1; }
.tocka { stroke: var(--_povrsina); stroke-width: 2; }
.referentna { stroke: var(--_tekst3); stroke-width: 1; }
.pratilica { stroke: var(--_tekst3); stroke-width: 1; }
.stupac:hover { opacity: 0.85; }
.oblacic { position: absolute; z-index: 2; min-width: 150px; pointer-events: none; padding: 10px 12px; border-radius: 10px;
  background: var(--_povrsina); border: 1px solid var(--_rub); box-shadow: 0 6px 24px rgba(0,0,0,.12); font-size: 12px; }
.oblacic .naslov { color: var(--_tekst3); margin-bottom: 6px; }
.oblacic .red { display: flex; align-items: center; gap: 8px; line-height: 1.7; }
.oblacic strong { color: var(--_tekst); font-weight: 600; font-variant-numeric: tabular-nums; min-width: 56px; }
.oblacic span { color: var(--_tekst2); }
.alati { display: flex; justify-content: flex-end; margin-top: 4px; }
.tablica-gumb { appearance: none; border: 0; background: none; color: var(--_tekst3); font: inherit; font-size: 12px; cursor: pointer;
  padding: 4px 0; text-decoration: underline; text-underline-offset: 3px; }
.tablica { max-height: 240px; overflow: auto; margin-top: 6px; border-top: 1px solid var(--_rub); }
.tablica table { width: 100%; border-collapse: collapse; font-size: 12px; }
.tablica th, .tablica td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--_rub); }
.tablica th { color: var(--_tekst3); font-weight: 500; position: sticky; top: 0; background: var(--_povrsina); }
.tablica td.broj { text-align: right; font-variant-numeric: tabular-nums; }
`;
