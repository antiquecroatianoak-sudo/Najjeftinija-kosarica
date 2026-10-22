// Krug oko odabrane točke (#13): samo stvarne poslovnice s provjerenom lokacijom unutar polumjera i njihove cijene,
// granica udaljenosti, susjedno naselje po geometriji, odbijena lokacija i ručni unos, pomak točke, promjena polumjera
// dok se učitava, poslovnica bez koordinata, prazan krug, nedostupne cijene, točan optimum kombinacije, filtar marke
// i njegovo spremanje. Sintetički podaci (nisu stvarne cijene): node tests/krug.cjs
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const Skupine = require("../site/skupine.js");

// Točka u središtu Zagreba; 1° geografske širine = 111,195 km (polumjer Zemlje 6371,0088 km).
const T = { lat: 45.8, lon: 15.97 };
const sjever = (km) => +(T.lat + km / 111.19508).toFixed(6);

function app({ poslovnice, lokacije, cjenici, proizvodi, popis, spremljeno = null, kasni = {} }) {
  let izvor = fs.readFileSync(path.join(__dirname, "../site/aplikacija.js"), "utf8");
  izvor = izvor.slice(0, izvor.lastIndexOf("\nfor (const r of document.querySelectorAll"));
  const cekanja = [];
  const ctx = vm.createContext({
    Skupine, console, setTimeout, Promise,
    window: { scrollTo() {}, isSecureContext: true },
    navigator: {},
    localStorage: { getItem: () => spremljeno, setItem(k, v) { ctx.__spremljeno = v; } },
    document: { addEventListener() {} },
    fetch: (url) => {
      const m = /poslovnice\/(\d+)\.json$/.exec(url);
      const idx = m ? +m[1] : -1;
      const odgovor = () => (cjenici[idx] === undefined
        ? { ok: false, status: 404, json: async () => ({}) }
        : { ok: true, json: async () => cjenici[idx] });
      if (kasni[idx]) return new Promise((ok) => cekanja.push(() => ok(odgovor())));
      return Promise.resolve(odgovor());
    },
  });
  ctx.__cekanja = cekanja;
  vm.runInContext(izvor + require("./sluzbeno-pomoc.cjs") + `
    const cvor = () => ({ children: [], hidden: false, textContent: "", className: "", value: "", dataset: {},
      classList: { add() {}, remove() {} }, set innerHTML(v) { this.children = []; },
      appendChild(c) { this.children.push(c); }, append(...c) { this.children.push(...c); }, setAttribute() {},
      insertAdjacentHTML() {}, querySelector() { return cvor(); }, focus() {} });
    globalThis.__cvorovi = {};
    document.getElementById = (id) => __cvorovi[id] || (__cvorovi[id] = cvor());
    document.createElement = () => cvor();
    podaci = { datum: "2026-10-21", lanci: ["Konzum", "Lidl"], proizvodi: ${JSON.stringify(proizvodi)} };
    uSluzbeno(podaci);
    podaci.poslovnice = ${JSON.stringify(poslovnice)};
    podaci.marke = ["Dukat", "Z bregov"];
    rijeci = podaci.proizvodi.map((x) => normaliziraj(x[0]).split(" "));
    klasifikacija = Skupine.pripremi(podaci.proizvodi, null, rijeci);
    lokacije = new Map(${JSON.stringify(lokacije)});
    if (!stanje.popis.length) stanje.popis = ${JSON.stringify(popis)};
  `, ctx);
  return ctx;
}
// Rezultati iz konteksta kao obični JSON (deepEqual ne uspoređuje nizove različitih realma).
const run = (ctx, kod) => {
  const v = vm.runInContext(kod, ctx);
  return v && typeof v === "object" ? JSON.parse(JSON.stringify(v, (k, x) => (x === Infinity ? "Infinity" : x))) : v;
};
const tick = () => new Promise((r) => setImmediate(r));
async function cekaj(ctx) { for (let k = 0; k < 20; k++) await tick(); }
const cjenik = (parovi) => {
  const c = [];
  let prije = 0;
  for (const [i, centi] of parovi) { c.push(i - prije, centi); prije = i; }
  return { datum: "2026-10-21", proizvoda: 3, c, r: parovi.map((_, k) => k + 2) };
};
const P = (naziv, iznos, jedinica, marka) => [naziv, `${iznos} ${jedinica}`, iznos, jedinica, 0, [0, 9.99, 1, 9.99], null, marka];

(async () => {
  const proizvodi = [P("Mlijeko Dukat 1 l", 1, "l", 0), P("Mlijeko Z bregov 1 l", 1, "l", 1), P("Kruh 500 g", 0.5, "kg", -1)];
  // 0: Konzum 19,9 km sjeverno (unutar 20 km), 1: Konzum 20,1 km (izvan), jeftiniji; 2: Lidl u Sesvetama (susjedno
  // naselje, 9 km), 3: Konzum bez provjerene lokacije (ne smije u krug), 4: Lidl 3 km.
  const poslovnice = [[0, "K1", "Ulica 1", "Zagreb", 0], [0, "K2", "Ulica 2", "Zaprešić", 0], [1, "L1", "Ulica 3", "Sesvete", 1],
    [0, "K3", "Ulica 4", "Zagreb", 0], [1, "L2", "Ulica 5", "Zagreb", 1]];
  const lokacije = [["Konzum|K1", [sjever(19.9), T.lon, "n1", "adresa+mjesto"]], ["Konzum|K2", [sjever(20.1), T.lon, "n2", "adresa+mjesto"]],
    ["Lidl|L1", [sjever(9), T.lon, "n3", "adresa+postanski"]], ["Lidl|L2", [sjever(3), T.lon, "n4", "jedina u mjestu"]]];
  const cjenici = { 0: cjenik([[0, 120], [2, 100]]), 1: cjenik([[0, 50], [2, 40]]), 2: cjenik([[1, 110], [2, 130]]),
    3: cjenik([[0, 10], [2, 10]]), 4: cjenik([[0, 125], [1, 105]]) };
  const popis = [{ naziv: "Mlijeko", kom: 1, kupljeno: false, marka: null }, { naziv: "Kruh", kom: 1, kupljeno: false, marka: null }];

  // Bez lokacije: nacionalni prikaz (najniža cijena lanca bilo gdje), jasno kao takav.
  let a = app({ poslovnice, lokacije, cjenici, proizvodi, popis });
  run(a, "prikazi()");
  assert.equal(run(a, "krug.stanje"), "nacionalno");

  // Granica: 19,9 km je unutra, 20,1 km nije; poslovnica bez koordinata nikad; susjedno naselje (Sesvete) unutra po geometriji.
  run(a, `postaviLokaciju({ lat: ${T.lat}, lon: ${T.lon}, naziv: "Zagreb", priblizno: true })`);
  assert.equal(run(a, "krug.stanje"), "ucitava");
  assert.deepEqual(run(a, "krug.poslovnice.map((x) => x.idx)"), [4, 2, 0], "inside 20 km, nearest first; K2 at 20,1 km and K3 without coordinates are out");
  assert.equal(run(a, "krug.bezKoordinata"), 1);
  assert.ok(Math.abs(run(a, "krug.poslovnice[2].km") - 19.9) < 0.01, "straight-line distance");
  // Dok se učitava: nema ponuda (ni nacionalnih), iznos nije lažna nula.
  assert.equal(run(a, `ponudeZaGrupu("Kruh").length`), 0);
  run(a, "prikaziRezultate()");
  assert.equal(a.__cvorovi.ukupno.textContent, "—");
  await cekaj(a);
  assert.equal(run(a, "krug.stanje"), "spremno");
  // Isti lanac, dvije poslovnice: jeftiniji Konzum K2 (0,40 €) je izvan kruga i ne smije pobijediti.
  let kruh = run(a, `ponudeZaGrupu("Kruh").map((p) => [podaci.lanci[p.lanac], p.cijena, p.poslovnica])`);
  assert.deepEqual(kruh, [["Konzum", 1, 0]], "cheapest store inside the circle; K2 (0,40 €, outside) never wins");
  assert.deepEqual(run(a, "cijeneProizvoda(2)"), [[0, 1, 1, 1.3], [[0, 1, 1, 0, 3, ""], [2, 1, 1.3, 0, 3, ""]]],
    "per chain only in-circle stores and their own prices (store, count in circle, highest in circle, row)");
  assert.equal(run(a, `ponudeZaGrupu("Kruh")[0].sluzbena`), true);
  assert.equal(run(a, `opisIzvoraCijene(ponudeZaGrupu("Kruh")[0])`), "Poslovnica: Ulica 1, Zagreb · službeni cjenik, redak 3");

  // Sve u jednom dućanu i kombinacije samo iz poslovnica kruga.
  let r = run(a, "prikaziJednuTrgovinu()");
  assert.deepEqual(Array.from(r.poslovnice.potpune, (x) => [x.adresa, Math.round(x.ukupno * 100) / 100]),
    [["Ulica 1, Zagreb", 2.2], ["Ulica 3, Sesvete", 2.4]], "Konzum K1 1,20+1,00; Lidl L1 1,10+1,30");
  const komb = Object.fromEntries(r.poslovnice.kombinacije.map((k) => [String(k.K), k.rez && [k.rez.ukupno, k.rez.poslovnice.length]]));
  assert.deepEqual(komb, { 2: [2.05, 2], 3: [2.05, 2], Infinity: [2.05, 2] }, "milk 1,05 (Lidl L2) + bread 1,00 (Konzum K1)");

  // Pomak točke: novi krug, poništen odabir. Polumjer 5 km: samo Lidl L2 (3 km), kruha nema -> nedostaje, bez zamjene.
  run(a, "stanje.odabir = { Mlijeko: 1 }; stanje.radijus = 5; prikazi()");
  assert.deepEqual(run(a, "stanje.odabir"), {}, "radius change invalidates selections");
  await cekaj(a);
  assert.deepEqual(run(a, "krug.poslovnice.map((x) => x.idx)"), [4]);
  assert.equal(run(a, `ponudeZaGrupu("Kruh").length`), 0, "no national fallback outside the circle");
  r = run(a, "prikaziJednuTrgovinu()");
  assert.equal(r.poslovnice.potpune.length, 0);
  assert.ok(r.poslovnice.kombinacije.every((k) => k.rez === null), "incomplete basket: no combination, no savings");
  run(a, "stanje.radijus = 10");
  run(a, `postaviLokaciju({ lat: ${sjever(30)}, lon: ${T.lon}, naziv: "Točka na karti", priblizno: false })`);
  assert.equal(run(a, "krug.stanje"), "ucitava");
  await cekaj(a);
  assert.deepEqual(run(a, "krug.poslovnice.map((x) => [x.idx, Math.round(x.km * 10) / 10])"), [[1, 9.9]], "moved marker: K2 now 9,9 km away");

  // Prazan krug: jasno stanje, iznos "—", nema ponuda.
  run(a, `postaviLokaciju({ lat: 43.5, lon: 16.44, naziv: "Split", priblizno: true })`);
  assert.equal(run(a, "krug.stanje"), "prazno");
  run(a, "prikaziRezultate()");
  assert.equal(a.__cvorovi.ukupno.textContent, "—");
  assert.match(a.__cvorovi.kartice.children[0].children[1].children[2].textContent, /nema poslovnica s provjerenom lokacijom/);

  // Polumjer promijenjen dok se učitava: zakašnjeli odgovor starog kruga ne smije postaviti ponude.
  a = app({ poslovnice, lokacije, cjenici, proizvodi, popis, kasni: { 0: true } });
  run(a, `postaviLokaciju({ lat: ${T.lat}, lon: ${T.lon}, naziv: "Zagreb", priblizno: false })`);
  const stari = run(a, "generacijaKruga");
  run(a, "stanje.radijus = 10; prikazi()");
  assert.equal(run(a, "generacijaKruga"), stari + 1);
  await cekaj(a);
  assert.equal(run(a, "krug.stanje"), "spremno");
  assert.deepEqual(run(a, "krug.poslovnice.map((x) => x.idx)"), [4, 2]);
  a.__cekanja.forEach((f) => f()); // stari krug (20 km, s K1) tek sada dobiva odgovor
  await cekaj(a);
  assert.equal(run(a, "stanje.radijus"), 10);
  assert.deepEqual(run(a, `ponudeZaGrupu("Kruh").map((p) => p.poslovnica)`), [2], "late response of the old circle is ignored");

  // Nedostupne cijene: sve datoteke kruga ne postoje -> "greska", bez ponuda.
  a = app({ poslovnice, lokacije, cjenici: {}, proizvodi, popis });
  run(a, `postaviLokaciju({ lat: ${T.lat}, lon: ${T.lon}, naziv: "Zagreb", priblizno: false })`);
  await cekaj(a);
  assert.equal(run(a, "krug.stanje"), "greska");
  assert.equal(run(a, `ponudeZaGrupu("Mlijeko").length`), 0);

  // Odbijena lokacija: poruka i ručni unos; zatim odabir mjesta s popisa naselja (približno središte).
  a = app({ poslovnice, lokacije, cjenici, proizvodi, popis });
  run(a, `navigator.geolocation = { getCurrentPosition(ok, ne) { ne({ code: 1 }); } }; koristiMojuLokaciju()`);
  assert.match(a.__cvorovi["lokacija-poruka"].textContent, /odbijen/);
  assert.equal(run(a, "stanje.lokacija"), null, "denied: no location, national view stays");
  run(a, `mjesta = [{ naziv: "Sesvete", lat: 45.83, lon: 16.11, vrsta: 3, kraj: "Zagreb", n: "sesvete" },
    { naziv: "Sesvetski Kraljevec", lat: 45.83, lon: 16.18, vrsta: 2, kraj: "Zagreb", n: "sesvetski kraljevec" }];
    prikaziPrijedloge(prijedloziMjesta("sesv")); odaberiPrijedlog(0);`);
  assert.deepEqual(run(a, "[stanje.lokacija.naziv, stanje.lokacija.priblizno]"), ["Sesvete", true]);
  assert.match(a.__cvorovi["lokacija-poruka"].textContent, /približno središte/);
  run(a, `navigator.geolocation = { getCurrentPosition(ok) { ok({ coords: { latitude: 45.81, longitude: 15.98, accuracy: 30 } }); } }; koristiMojuLokaciju()`);
  assert.deepEqual(run(a, "[stanje.lokacija.lat, stanje.lokacija.lon, stanje.lokacija.priblizno]"), [45.81, 15.98, false]);

  // Filtar marke: "Samo Dukat" ostaje i nakon ponovnog otvaranja (spremljeni popis); nepoznata marka ga ne zadovoljava;
  // bez ponude te marke stavka nedostaje (nema tihe zamjene). Stari zapis bez marke = bilo koja marka.
  a = app({ poslovnice, lokacije, cjenici, proizvodi, popis });
  run(a, `postaviMarku(stanje.popis[0], "Dukat")`);
  const spremljeno = a.__spremljeno;
  assert.equal(JSON.parse(spremljeno).popis[0].marka, "Dukat");
  a = app({ poslovnice, lokacije, cjenici, proizvodi, popis: [], spremljeno });
  assert.equal(run(a, "stanje.popis[0].marka"), "Dukat", "brand filter persists across reload");
  assert.deepEqual(run(a, `ponudeZaGrupu("Mlijeko").map((p) => podaci.proizvodi[p.i][0])`), ["Mlijeko Dukat 1 l"]);
  run(a, `podaci.proizvodi[0][7] = -1; pogociCache.clear(); ponudeCache.clear();`);
  assert.equal(run(a, `ponudeZaGrupu("Mlijeko").length`), 0, "unknown brand never satisfies the strict filter");
  run(a, "prikaziRezultate()");
  assert.match(a.__cvorovi.kartice.children[0].children[1].children[2].textContent, /Nedostaje: nema ponude marke Dukat/);
  a = app({ poslovnice, lokacije, cjenici, proizvodi, popis: [],
    spremljeno: JSON.stringify({ popis: ["mlijeko", { naziv: "Kruh", kom: 2 }] }) });
  assert.deepEqual(run(a, "stanje.popis.map((s) => [s.naziv, s.kom, s.marka])"), [["mlijeko", 1, null], ["Kruh", 2, null]], "old saved list migrates");

  // Točan optimum: usporedba s potpunom pretragom na nasumičnim troškovima (do 7 poslovnica, 5 stavki, praznine).
  a = app({ poslovnice, lokacije, cjenici, proizvodi, popis });
  let sjeme = 7;
  const slucajno = () => (sjeme = (sjeme * 1103515245 + 12345) % 2147483648) / 2147483648;
  for (let pokus = 0; pokus < 300; pokus++) {
    const n = 1 + Math.floor(slucajno() * 5);
    const m = 1 + Math.floor(slucajno() * 7);
    const troskovi = Array.from({ length: m }, (_, idx) => ({ idx, ponude: Array(n).fill(null),
      v: Array.from({ length: n }, () => (slucajno() < 0.2 ? Infinity : 50 + Math.floor(slucajno() * 400))) }));
    run(a, `stanje.popis = Array.from({ length: ${n} }, (_, j) => ({ naziv: "S" + j, kom: 1, kupljeno: false, marka: null }))`);
    for (const K of [1, 2, 3, Infinity]) {
      let naj = Infinity;
      for (let maska = 1; maska < 1 << m; maska++) {
        const skup = troskovi.filter((_, k) => maska & (1 << k));
        if (skup.length > K) continue;
        let z = 0;
        for (let j = 0; j < n; j++) z += Math.min(...skup.map((t) => t.v[j]));
        naj = Math.min(naj, z);
      }
      a.__t = troskovi;
      const rez = run(a, `najboljaKombinacija(__t, ${K === Infinity ? "Infinity" : K})`);
      if (naj === Infinity) assert.equal(rez, null, "no complete combination");
      else {
        assert.equal(Math.round(rez.ukupno * 100), naj, `optimum K=${K}`);
        assert.ok(rez.poslovnice.length <= K);
        assert.equal(rez.dodjela.reduce((z, d, j) => z + troskovi[d.idx].v[j], 0), naj, "assignment adds up to the total");
      }
    }
  }
  // Mali primjer s dokazivim optimumom: A {1,00; 5,00; 5,00}, B {5,00; 1,00; 5,00}, C {5,00; 5,00; 1,00}, D {2,00; 2,00; 2,00}.
  // Jedan dućan: najbolji D = 6,00. Dva: A+D (ili B+D, C+D) = 1+2+2 = 5,00; A+B = 7,00. Tri: A+B+C = 3,00.
  const mali = [[100, 500, 500], [500, 100, 500], [500, 500, 100], [200, 200, 200]].map((v, idx) => ({ idx, v, ponude: [null, null, null] }));
  run(a, `stanje.popis = [0, 1, 2].map((j) => ({ naziv: "S" + j, kom: 1, kupljeno: false, marka: null }))`);
  a.__t = mali;
  assert.deepEqual([1, 2, 3].map((K) => run(a, `najboljaKombinacija(__t, ${K}).ukupno`)), [6, 5, 3]);
  console.log("KRUG PASS: boundary 19,9/20,1 km, no store without coordinates, neighbouring settlement by geometry, cheaper store "
    + "outside the circle never wins, loading/empty/error states without false zero or national offers, radius change "
    + "invalidates and ignores late responses, moved marker, denied geolocation + manual place, brand filter persists, "
    + "unknown brand excluded, old list migrates, exact optimum = brute force (300 random cases), 6,00/5,00/3,00 example");
})().catch((e) => { console.error(e); process.exit(1); });
