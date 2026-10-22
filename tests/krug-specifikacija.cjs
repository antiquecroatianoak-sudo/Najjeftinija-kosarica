// Izvedbeni primjeri specifikacije (#4, 6350283572): lokalne cijene i ušteda, potpunost, pakiranja, marke,
// asinkronost i osvježenja, statusi. Sintetički testni podaci, nisu stvarne cijene: node tests/krug-specifikacija.cjs
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const Skupine = require("../site/skupine.js");

// Udaljenosti iz stvarnih (determinističkih) koordinata oko testnog središta, ne iz oznake km: točka d km sjeverno.
// Haversine za pomak po meridijanu daje točno R·Δφ, pa je d = 6371,0088 km · Δφ (radijani).
const S = { lat: 45.0, lon: 16.0 };
const sjever = (km) => S.lat + (km / 6371.0088) * (180 / Math.PI);

const LANCI = ["X", "Y", "Z"];
// Proizvodi: 0 mlijeko M 1 l, 1 mlijeko N 1 l, 2 kruh 1 kom, 3 mlijeko 1,5 l (M), 4 mlijeko bez marke 1 l,
// 5 čokolada M s mlijekom (druga vrsta iste marke).
const PROIZVODI = [
  ["Mlijeko M 1 l", "1 l", 1, "l", 0, [0, 9.99], null, 0],
  ["Mlijeko N 1 l", "1 l", 1, "l", 0, [0, 9.99], null, 1],
  ["Kruh 1 kom", "1 kom", 1, "kom", 0, [0, 9.99], null, -1],
  ["Mlijeko M 1,5 l", "1,5 l", 1.5, "l", 0, [0, 9.99], null, 0],
  ["Mlijeko 1 l", "1 l", 1, "l", 0, [0, 9.99], null, -1],
  ["Čokolada M s mlijekom 100 g", "100 g", 0.1, "kg", 0, [0, 9.99], null, 0],
];
const POSL = [[0, "A", "Ulica 1", "Mjesto A", 0], [0, "B", "Ulica 2", "Mjesto B", 0], [1, "C", "Ulica 3", "Mjesto C", 1],
  [2, "D", "Ulica 4", "Mjesto D", 2]];
const KM = { A: 2, B: 8, C: 25 }; // D nema koordinate
const LOK = Object.entries(KM).map(([id, km]) => [`${LANCI[POSL.find((p) => p[1] === id)[0]]}|${id}`, [sjever(km), S.lon, "n" + id, "adresa+mjesto"]]);

function cjenik(idx, parovi, izdanje = "v1") {
  const c = [];
  let prije = 0;
  for (const [i, centi] of [...parovi].sort((a, b) => a[0] - b[0])) { c.push(i - prije, centi); prije = i; }
  return { datum: "2026-10-21", izdanje, poslovnica: `${LANCI[POSL[idx][0]]}|${POSL[idx][1]}`, proizvoda: PROIZVODI.length, c,
    r: parovi.map((_, k) => k + 2) };
}
const MLIJEKO_2L = { naziv: "Mlijeko", kom: 2, kupljeno: false, marka: null, mjera: { jedinica: "l", iznos: 1 } };
const KRUH = { naziv: "Kruh", kom: 1, kupljeno: false, marka: null, mjera: null };

function app({ cjenici, popis = [MLIJEKO_2L, KRUH], spremljeno = null }) {
  let izvor = fs.readFileSync(path.join(__dirname, "../site/aplikacija.js"), "utf8");
  izvor = izvor.slice(0, izvor.lastIndexOf("\nfor (const r of document.querySelectorAll"));
  const mreza = { kasni: new Set(), kvar: new Set(), cekanja: [], pozivi: [], istodobno: 0, najvise: 0 };
  const ctx = vm.createContext({
    Skupine, console, setTimeout, Promise,
    window: { scrollTo() {}, isSecureContext: true }, navigator: {},
    localStorage: { getItem: () => spremljeno, setItem(k, v) { ctx.__spremljeno = v; } },
    document: { addEventListener() {} },
    fetch: (url) => {
      const idx = +/poslovnice\/(\d+)\.json$/.exec(url)[1];
      mreza.pozivi.push(idx);
      mreza.istodobno++;
      mreza.najvise = Math.max(mreza.najvise, mreza.istodobno);
      const odgovor = () => {
        mreza.istodobno--;
        return mreza.kvar.has(idx) || !cjenici[idx] ? { ok: false, status: 503, json: async () => ({}) } : { ok: true, json: async () => cjenici[idx] };
      };
      if (mreza.kasni.has(idx)) return new Promise((ok) => mreza.cekanja.push(() => ok(odgovor())));
      return new Promise((ok) => setImmediate(() => ok(odgovor())));
    },
  });
  ctx.__mreza = mreza;
  vm.runInContext(izvor + require("./sluzbeno-pomoc.cjs") + `
    const cvor = () => ({ children: [], hidden: false, open: false, textContent: "", className: "", value: "", dataset: {},
      classList: { add() {}, remove() {} }, set innerHTML(v) { this.children = []; },
      appendChild(c) { this.children.push(c); }, append(...c) { this.children.push(...c); }, setAttribute() {},
      insertAdjacentHTML() {}, querySelector() { return cvor(); }, focus() {} });
    globalThis.__cvorovi = {};
    document.getElementById = (id) => __cvorovi[id] || (__cvorovi[id] = cvor());
    document.createElement = () => cvor();
    podaci = { datum: "2026-10-21", izdanje: "v1", lanci: ${JSON.stringify(LANCI)}, proizvodi: ${JSON.stringify(PROIZVODI)} };
    uSluzbeno(podaci);
    podaci.poslovnice = ${JSON.stringify(POSL)};
    podaci.marke = ["M", "N"];
    rijeci = podaci.proizvodi.map((x) => normaliziraj(x[0]).split(" "));
    klasifikacija = Skupine.pripremi(podaci.proizvodi, null, rijeci);
    lokacije = new Map(${JSON.stringify(LOK)});
    if (!stanje.popis.length) stanje.popis = ${JSON.stringify(popis)};
  `, ctx);
  return ctx;
}
const run = (ctx, kod) => {
  const v = vm.runInContext(kod, ctx);
  return v && typeof v === "object" ? JSON.parse(JSON.stringify(v, (k, x) => (x === Infinity ? "Infinity" : x))) : v;
};
const cekaj = async () => { for (let k = 0; k < 30; k++) await new Promise((r) => setImmediate(r)); };
const lociraj = (a, R) => run(a, `stanje.radijus = ${R}; postaviLokaciju({ lat: ${S.lat}, lon: ${S.lon}, naziv: "Test", priblizno: false })`);
// Sažetak: pojedinačne potpune poslovnice, kombinacije (K -> [centi, broj dućana]) i ušteda prema jednom dućanu.
function sazetak(a) {
  const r = run(a, "prikaziJednuTrgovinu()").poslovnice;
  return {
    jedna: r.potpune.map((x) => [x.ime + "/" + x.adresa.split(",")[0], Math.round(x.ukupno * 100), !!x.najpovoljnija]),
    komb: Object.fromEntries(r.kombinacije.map((k) => [k.K, k.rez && [Math.round(k.rez.ukupno * 100), k.rez.poslovnice.length]])),
    ostale: r.ostale.map((x) => `${x.ime}/${x.adresa.split(",")[0]} ${x.pokriveno}/${x.stavki}`),
  };
}

(async () => {
  const A = (m = 120, k = 160) => cjenik(0, [[0, m], [2, k]]);
  const B = (m = 100, k = 200) => cjenik(1, [[1, m], [2, k]]);
  const C = cjenik(2, [[0, 50], [2, 50]]);
  const D = cjenik(3, [[0, 20], [2, 20]]);

  // 1. Lokalne cijene i ušteda.
  let a = app({ cjenici: { 0: A(), 1: B(), 2: C, 3: D } });
  lociraj(a, 20);
  await cekaj();
  assert.deepEqual(run(a, "krug.poslovnice.map((x) => [x.idx, Math.round(x.km * 1e6) / 1e6])"), [[0, 2], [1, 8]], "A 2 km, B 8 km from coordinates");
  assert.equal(run(a, "krug.bezKoordinata"), 1, "D without coordinates is never in the circle");
  let s = sazetak(a);
  assert.deepEqual(s.jedna, [["X/Ulica 1", 400, true], ["X/Ulica 2", 400, true]], "A and B tie at 400 cents");
  assert.deepEqual(s.komb[2], [360, 2], "B milk 2×100 + A bread 160 = 360, two stores");
  assert.deepEqual(s.komb.Infinity, [360, 2]);
  assert.ok(!s.jedna.some((x) => x[1] === 360), "chain X is never one store with 360");
  assert.deepEqual(run(a, `ponudeZaGrupu("Mlijeko").map((p) => [p.poslovnica, p.cijena])`), [[1, 1], [0, 1.2]], "cards: only A and B");
  assert.deepEqual(run(a, `ponudeZaGrupu("Kruh").map((p) => [p.poslovnica, p.cijena])`), [[0, 1.6]], "bread: A's own price (B is the same product, higher)");
  assert.deepEqual(run(a, "cijeneProizvoda(2)[1].map((x) => x[0])"), [0], "per chain X: only the cheaper in-circle store, never C or D");
  let k2 = run(a, "opisKombinacije(usporedbaPoslovnica().kombinacije[0], usporedbaPoslovnica().potpune[0])");
  assert.match(k2.tekst, /^2 dućana · ušteda 0,40 € prema jednom dućanu · X, Ulica 1, Mjesto A \(2,0 km\): Kruh · X, Ulica 2, Mjesto B \(8,0 km\): Mlijeko$/);
  // 30 km: C potpun 150, kombinacija 150 u jednoj poslovnici, ušteda 0.
  run(a, "stanje.radijus = 30; prikazi()");
  await cekaj();
  s = sazetak(a);
  assert.deepEqual(s.jedna[0], ["Y/Ulica 3", 150, true]);
  assert.deepEqual(s.komb[2], [150, 1]);
  k2 = run(a, "opisKombinacije(usporedbaPoslovnica().kombinacije[0], usporedbaPoslovnica().potpune[0])");
  assert.match(k2.tekst, /^1 dućan · jednako jednom dućanu/);
  assert.equal(run(a, "krug.poslovnice.some((x) => x.idx === 3)"), false, "D stays excluded");
  // 5 km: samo A.
  run(a, "stanje.radijus = 5; prikazi()");
  await cekaj();
  s = sazetak(a);
  assert.deepEqual(s.jedna, [["X/Ulica 1", 400, true]]);
  assert.deepEqual(s.komb[2], [400, 1]);
  // Uključiva granica: poslovnica točno na rubu je unutra, 1 m dalje nije (tolerancija 1e-6 km).
  a = app({ cjenici: { 0: A(), 1: B() } });
  run(a, `lokacije = new Map([["X|A", [${sjever(20)}, ${S.lon}, "nA", "adresa+mjesto"]], ["X|B", [${sjever(20.001)}, ${S.lon}, "nB", "adresa+mjesto"]]])`);
  lociraj(a, 20);
  assert.deepEqual(run(a, "krug.poslovnice.map((x) => x.idx)"), [0], "exactly 20 km inside, 20,001 km outside");
  assert.ok(Math.abs(run(a, "krug.poslovnice[0].km") - 20) < 1e-9);

  // 2. Potpunost.
  a = app({ cjenici: { 0: cjenik(0, [[0, 120]]), 1: cjenik(1, [[2, 200]]), 2: C } });
  lociraj(a, 20);
  await cekaj();
  s = sazetak(a);
  assert.deepEqual(s.jedna, [], "no single complete store");
  assert.deepEqual(s.komb[2], [440, 2], "A milk 240 + B bread 200 = 440, complete");
  k2 = run(a, "opisKombinacije(usporedbaPoslovnica().kombinacije[0], null)");
  assert.match(k2.tekst, /nijedna poslovnica nema sve, ušteda se ne računa/);
  a = app({ cjenici: { 0: cjenik(0, [[0, 120]]), 1: cjenik(1, [[5, 100]]), 2: C } });
  lociraj(a, 20);
  await cekaj();
  s = sazetak(a);
  assert.deepEqual(s.komb, { 2: null, 3: null, Infinity: null }, "no bread anywhere: incomplete, no total");
  run(a, "prikaziRezultate()");
  assert.notEqual(a.__cvorovi.ukupno.textContent, "0,00 €");
  assert.match(a.__cvorovi.nedostaje.textContent, /nema cijene/);
  assert.match(a.__cvorovi.kartice.children[1].children[1].children[2].textContent, /^Za ovu stavku nema odgovarajuće ponude/);

  // 3. Pakiranja: tražene 2 l; 1 l/100 -> 2 pak. 200; 1,5 l/140 -> 2 pak. 280. Kartice po jediničnoj cijeni (1,5 l prvo),
  // košarica po stvarnom trošku cijelih pakiranja (2 × 1 l).
  a = app({ cjenici: { 0: cjenik(0, [[0, 100], [3, 140], [2, 160]]) } });
  lociraj(a, 5);
  await cekaj();
  assert.deepEqual(run(a, `ponudeZaGrupu("Mlijeko").map((p) => podaci.proizvodi[p.i][0])`), ["Mlijeko M 1,5 l", "Mlijeko M 1 l"], "unit-price order kept");
  assert.deepEqual(run(a, `ponudeZaGrupu("Mlijeko").map((p) => brojPakiranja(stanje.popis[0], p))`), [2, 2]);
  assert.deepEqual(sazetak(a).jedna, [["X/Ulica 1", 360, true]], "basket uses 2 × 1 l = 200 + bread 160");
  assert.deepEqual(run(a, "troskoviPoslovnica()[0].ponude.map((p) => podaci.proizvodi[p.i][0])"), ["Mlijeko M 1 l", "Kruh 1 kom"]);
  run(a, "prikaziRezultate()");
  assert.equal(a.__cvorovi.kartice.children[0].children[1].children[0].textContent, "Mlijeko · 2 l", "requested quantity shown");
  run(a, "stanje.radijus = 10; prikazi()");
  await cekaj();
  assert.deepEqual(run(a, "trazenaKolicina(stanje.popis[0])"), 2, "radius change keeps the requested quantity");
  // Unos "2 l mlijeka" daje traženu količinu 2 l; "500 g sira" 0,5 kg.
  assert.deepEqual(run(a, `rastavi("2 l mlijeka")`), { naziv: "mlijeka", kom: 2, mjera: { jedinica: "l", iznos: 1 } });
  assert.deepEqual(run(a, `rastavi("500 g sira")`), { naziv: "sira", kom: 1, mjera: { jedinica: "kg", iznos: 0.5 } });
  assert.deepEqual(run(a, `rastavi("2 mlijeka")`), { naziv: "mlijeka", kom: 2 });

  // 4. Marke: A mlijeko M, B mlijeko N.
  a = app({ cjenici: { 0: A(), 1: B(), 2: C } });
  run(a, `postaviMarku(stanje.popis[0], "M")`);
  lociraj(a, 20);
  await cekaj();
  s = sazetak(a);
  assert.deepEqual(s.jedna, [["X/Ulica 1", 400, true]], "only M: B's milk N does not qualify");
  assert.deepEqual(s.komb[2], [400, 1]);
  assert.deepEqual(run(a, `ponudeZaGrupu("Mlijeko").map((p) => podaci.proizvodi[p.i][0])`), ["Mlijeko M 1 l"],
    "neither N nor the M chocolate (another kind of product) qualifies");
  run(a, "podaci.proizvodi[0][7] = -1; pogociCache.clear(); ponudeCache.clear(); troskoviCache = null;");
  assert.equal(run(a, `ponudeZaGrupu("Mlijeko").length`), 0, "unknown brand is not M");
  const spremljeno = a.__spremljeno;
  let b = app({ cjenici: {}, popis: [], spremljeno });
  assert.equal(run(b, "stanje.popis[0].marka"), "M", "filter survives reload");
  assert.deepEqual(run(b, "stanje.popis[0].mjera"), { jedinica: "l", iznos: 1 }, "requested quantity survives reload");
  b = app({ cjenici: {}, popis: [], spremljeno: JSON.stringify({ popis: [{ naziv: "Mlijeko", kom: 2 }] }) });
  assert.deepEqual(run(b, "[stanje.popis[0].marka, stanje.popis[0].mjera]"), [null, null], "old list: any brand");

  // 5. Asinkronost i osvježenja.
  // C kasni u krugu 30 km, prijelaz na 5 km: nakon odgovora C ostaje samo A.
  a = app({ cjenici: { 0: A(), 1: B(), 2: C } });
  a.__mreza.kasni.add(2);
  lociraj(a, 30);
  await cekaj();
  assert.equal(run(a, "krug.stanje"), "ucitava", "partial circle is not final while C is loading");
  assert.match(a.__cvorovi["lokacija-opis"].textContent, /Učitavam cijene — 2 od 3 poslovnica\./);
  assert.equal(run(a, `ponudeZaGrupu("Mlijeko").length`), 0, "no partial minimum presented while loading");
  run(a, "stanje.radijus = 5; prikazi()");
  await cekaj();
  a.__mreza.cekanja.forEach((f) => f());
  await cekaj();
  assert.deepEqual(sazetak(a).jedna, [["X/Ulica 1", 400, true]], "late C response does not change the 5 km result");
  // Pomak točke i promjena lanaca tijekom dohvata: isti mehanizam generacije.
  a = app({ cjenici: { 0: A(), 1: B(), 2: C } });
  a.__mreza.kasni.add(2);
  lociraj(a, 30);
  run(a, `stanje.iskljuceni = ["Y"]; promijeniPostavke()`);
  await cekaj();
  a.__mreza.cekanja.forEach((f) => f());
  await cekaj();
  assert.deepEqual(run(a, "krug.poslovnice.map((x) => x.idx)"), [0, 1], "chain Y excluded mid-load");
  assert.deepEqual(sazetak(a).komb[2], [360, 2]);
  a.__mreza.kasni.add(1);
  run(a, `postaviLokaciju({ lat: ${sjever(24)}, lon: ${S.lon}, naziv: "Pomak", priblizno: false })`);
  const gen = run(a, "generacijaKruga");
  run(a, `postaviLokaciju({ lat: ${S.lat}, lon: ${S.lon}, naziv: "Natrag", priblizno: false })`);
  assert.equal(run(a, "generacijaKruga"), gen + 1);
  // Kvar dohvata B: rezultat među učitanima (samo A), poruka i "Ponovi" samo za B; popis ostaje.
  a = app({ cjenici: { 0: A(), 1: B() } });
  a.__mreza.kvar.add(1);
  lociraj(a, 20);
  await cekaj();
  assert.equal(run(a, "krug.stanje"), "spremno");
  assert.deepEqual(run(a, "krug.neuspjele"), [1]);
  assert.match(a.__cvorovi["lokacija-opis"].textContent, /Dio cijena nije učitan \(1 od 2\) — Ponovi\./);
  assert.equal(a.__cvorovi["ponovi-krug"].hidden, false);
  s = sazetak(a);
  assert.deepEqual(s.jedna, [["X/Ulica 1", 400, true]]);
  assert.match(a.__cvorovi["poslovnice-status"].textContent, /najpovoljnije je samo među učitanim poslovnicama/);
  run(a, "prikaziRezultate()");
  assert.match(a.__cvorovi.nedostaje.textContent, /najpovoljnije samo među učitanim poslovnicama/);
  a.__mreza.kvar.delete(1);
  a.__mreza.pozivi.length = 0;
  await run(a, "ponoviNeuspjele()");
  await cekaj();
  assert.deepEqual(a.__mreza.pozivi, [1], "retry fetches only the failed store");
  assert.equal(run(a, "stanje.popis.length"), 2, "retry keeps the list");
  assert.deepEqual(sazetak(a).komb[2], [360, 2]);
  assert.equal(a.__cvorovi["ponovi-krug"].hidden, true);
  // Ponovni uvoz istog dana s drugim redoslijedom: datoteka drugog izdanja ili druge poslovnice se ne prihvaća.
  a = app({ cjenici: { 0: cjenik(0, [[0, 120], [2, 160]], "v0"), 1: Object.assign(B(), { poslovnica: "X|A" }) } });
  lociraj(a, 20);
  await cekaj();
  assert.equal(run(a, "krug.stanje"), "greska", "same date and count, but other build / other store: rejected");
  assert.equal(run(a, `ponudeZaGrupu("Mlijeko").length`), 0);
  // Ograničena paralelnost i bez ponovnog izračuna pri istom prikazu.
  const mnogo = Array.from({ length: 30 }, (_, k) => [0, "M" + k, "Ulica " + k, "Grad", 0]);
  a = app({ cjenici: Object.fromEntries(mnogo.map((_, k) => [k, { ...cjenik(0, [[0, 100 + k], [2, 150]]), poslovnica: "X|M" + k }])) });
  run(a, `podaci.poslovnice = ${JSON.stringify(mnogo)}; lokacije = new Map(podaci.poslovnice.map((p, k) => ["X|" + p[1], [${sjever(1)} + k / 1e4, ${S.lon}, "n", "adresa+mjesto"]])); krug.kljuc = "";`);
  lociraj(a, 20);
  await cekaj();
  assert.equal(run(a, "krug.poslovnice.length"), 30);
  assert.ok(a.__mreza.najvise <= 6, `at most 6 parallel downloads (${a.__mreza.najvise})`);
  run(a, "troskoviCache = null; globalThis.__izracuni = 0; const izvorni = izracunajTroskove; izracunajTroskove = () => { __izracuni++; return izvorni(); };");
  run(a, "prikaziJednuTrgovinu(); prikaziJednuTrgovinu(); prikaziJednuTrgovinu();");
  assert.equal(run(a, "__izracuni"), 1, "same circle and list: costs computed once for repeated renders");
  assert.match(a.__cvorovi["poslovnice-status"].textContent, /30 poslovnica u krugu od 20 km.*30 ima cijeli popis, prikazano 8 najpovoljnijih/);

  // 6. Statusi bez žargona.
  a = app({ cjenici: { 0: A() } });
  run(a, "prikazi()");
  assert.match(a.__cvorovi["lokacija-opis"].textContent, /^Odaberi lokaciju\./);
  run(a, `predloziLokaciju({ lat: ${S.lat}, lon: ${S.lon}, naziv: "Mjesto", priblizno: true }, "")`);
  assert.match(a.__cvorovi["lokacija-opis"].textContent, /^Potvrdi lokaciju na karti/);
  run(a, `lokacije = new Map(); primijeniKandidata()`);
  assert.match(a.__cvorovi["lokacija-opis"].textContent, /lokacije poslovnica trenutačno nisu dostupne/);
  run(a, `lokacije = new Map(${JSON.stringify(LOK)}); stanje.radijus = 5; postaviLokaciju({ lat: ${sjever(100)}, lon: ${S.lon}, naziv: "Daleko", priblizno: false })`);
  assert.match(a.__cvorovi["lokacija-opis"].textContent, /Nema poslovnica s dostupnim podacima unutar odabranog kruga\. Za neke poslovnice lokacija nije potvrđena \(1\)/);

  console.log("SPECIFIKACIJA PASS: 1) 20 km A=B=400, combination 360/2 stores, saving 40; 30 km C 150 alone; 5 km A 400; D never; "
    + "inclusive boundary (1e-6 km); 2) 440 without single store, no saving; no bread → no total; 3) 2 l: 2×1 l (200) over 2×1,5 l "
    + "(280), unit-price card order kept; 4) only M, unknown ≠ M, other kind excluded, reload/migration; 5) late C ignored after "
    + "30→5 km, chain/marker change, failed B → among loaded + retry only B, other build rejected, ≤6 parallel, costs memoized; 6) statuses");
})().catch((e) => { console.error(e); process.exit(1); });
