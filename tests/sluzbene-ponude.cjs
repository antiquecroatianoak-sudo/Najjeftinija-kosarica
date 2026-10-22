// Samo ponude potvrđene službenim cjenikom sudjeluju u poretku, najpovoljnijem i zbrojevima (pregled #12, 6326498287).
// Sintetički cjenik: node tests/sluzbene-ponude.cjs
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const Skupine = require("../site/skupine.js");

function scenarij(proizvodi, poslovnice, popis) {
  let izvor = fs.readFileSync(path.join(__dirname, "../site/aplikacija.js"), "utf8");
  izvor = izvor.slice(0, izvor.lastIndexOf("\nfor (const r of document.querySelectorAll"));
  const ctx = vm.createContext({ Skupine, window: { scrollTo() {} }, localStorage: { getItem: () => null, setItem() {} },
    document: { addEventListener() {} } });
  vm.runInContext(izvor + require("./sluzbeno-pomoc.cjs") + `
    const cvor = () => ({ children: [], hidden: false, textContent: "", className: "", set innerHTML(v) { this.children = []; },
      appendChild(c) { this.children.push(c); }, append(...c) { this.children.push(...c); }, setAttribute() {} });
    globalThis.__cvorovi = {};
    document.getElementById = (id) => __cvorovi[id] || (__cvorovi[id] = cvor());
    document.createElement = () => cvor();
    prikaziRezultate = () => {}; spremi = () => {};
    podaci = { datum: "2026-10-21", lanci: ["Sekundarni", "Službeni"], izvori: [["https://lanac.hr/cjenik.csv", "2026-10-21"]],
      poslovnice: ${JSON.stringify(poslovnice)}, proizvodi: ${JSON.stringify(proizvodi)} };
    rijeci = podaci.proizvodi.map((x) => normaliziraj(x[0]).split(" "));
    klasifikacija = Skupine.pripremi(podaci.proizvodi, null, rijeci);
    stanje.popis = ${JSON.stringify(popis)};
  `, ctx);
  return ctx;
}
const POSL = [[0, "S1", "Ilica 1", "Zagreb", -1], [1, "O1", "Savska 3", "Zagreb", 0]];
const popis = [{ naziv: "Mlijeko", kom: 1 }];

// Sekundarna 1,09 € (arhiva cijene.dev) nasuprot službenoj 1,20 €: pobjeđuje službena, sekundarna ostaje označena.
let app = scenarij([["Mlijeko 1 l", "1 l", 1, "l", 0, [0, 1.09, 1, 1.2], [[0, 1, 1.09, 0], [1, 1, 1.2, 0, 7, ""]]]], POSL, popis);
let p = vm.runInContext(`ponudeZaGrupu("Mlijeko")[0]`, app);
assert.equal(p.lanac, 1, "the official offer of the same product is kept and shown");
assert.equal(p.cijena, 1.2);
assert.equal(vm.runInContext(`imaJedinicnu(ponudeZaGrupu("Mlijeko")[0])`, app), true);
assert.equal(vm.runInContext(`imaJedinicnu(ponuda(0, 0, 1.09))`, app), false, "secondary offer never ranks");
let r = vm.runInContext("prikaziJednuTrgovinu()", app);
assert.deepEqual(Array.from(r.potpune, (x) => x.ime), ["Službeni"]);
assert.equal(Math.round(r.kombinacija * 100) / 100, 1.2, "combination uses only confirmed prices");
assert(r.nepotpune.some((x) => x.ime === "Sekundarni" && x.ukupno === 0), "secondary chain is not complete and adds nothing");
vm.runInContext(`cjeniciPoslovnica.set(0, new Map([[0, 109]])); cjeniciPoslovnica.set(1, new Map([[0, 120]]));
  uKrug([0, 1]);`, app);
r = vm.runInContext("prikaziJednuTrgovinu()", app);
assert.deepEqual(Array.from(r.poslovnice.potpune, (x) => [x.adresa, Math.round(x.ukupno * 100) / 100, x.najpovoljnija]),
  [["Savska 3, Zagreb", 1.2, true]], "only the store with an official price list makes a confirmed complete basket");

// Samo sekundarna ponuda: vidljiva i označena, ali nema potvrđene najjeftinije ni potpune košarice.
app = scenarij([["Mlijeko 1 l", "1 l", 1, "l", 0, [0, 1.09], [[0, 1, 1.09, 0]]]], POSL, popis);
p = vm.runInContext(`ponudeZaGrupu("Mlijeko")[0]`, app);
assert.equal(p.lanac, 0);
assert.equal(p.sluzbena, false);
assert.equal(vm.runInContext(`imaJedinicnu(ponudeZaGrupu("Mlijeko")[0])`, app), false);
r = vm.runInContext("prikaziJednuTrgovinu()", app);
assert.equal(r.potpune.length, 0);
assert.equal(r.kombinacija, null);
assert.equal(app.__cvorovi["nema-potpune"].hidden, false);
vm.runInContext(`cjeniciPoslovnica.set(0, new Map([[0, 109]])); uKrug([0]);`, app);
r = vm.runInContext("prikaziJednuTrgovinu()", app);
assert.equal(r.poslovnice.potpune.length, 0);
assert.equal(app.__cvorovi["nema-potpune-poslovnice"].hidden, false);
assert.equal(vm.runInContext(`opisIzvoraCijene(ponudeZaGrupu("Mlijeko")[0])`, app),
  "Poslovnica: Ilica 1, Zagreb · arhiva cijene.dev, nije provjereno sa službenim cjenikom");
// Stari / offline oblik (verzija 2 bez traga "izvori") i neispravan trag: ništa nije implicitno potvrđeno.
for (const [opis, postavi] of [["no sources at all", "delete podaci.izvori; delete podaci.poslovnice;"],
  ["sources not a list", "podaci.izvori = 'x';"],
  ["source without https URL", "podaci.izvori = [['ftp://x', '2026-10-21']];"],
  ["source without a date", "podaci.izvori = [['https://lanac.hr/c.csv', '']];"]]) {
  app = scenarij([["Mlijeko 1 l", "1 l", 1, "l", 0, [1, 1.2], [[1, 1, 1.2, 0, 7, ""]]]], POSL, popis);
  vm.runInContext(postavi + " ponudeCache.clear();", app);
  p = vm.runInContext(`ponudeZaGrupu("Mlijeko")[0]`, app);
  assert.equal(p.cijena, 1.2, `${opis}: offer stays visible`);
  assert.equal(p.sluzbena, false, `${opis}: not confirmed`);
  assert.equal(vm.runInContext(`imaJedinicnu(ponudeZaGrupu("Mlijeko")[0])`, app), false, `${opis}: not ranked`);
  r = vm.runInContext("prikaziJednuTrgovinu()", app);
  assert.equal(r.potpune.length, 0, `${opis}: no confirmed complete basket`);
  assert.equal(r.kombinacija, null, `${opis}: no confirmed combination`);
}

console.log("CONFIRMED-ONLY PASS: secondary 1,09 vs official 1,20 → official wins and is shown; secondary never ranks, "
  + "adds nothing to chain, combination or store totals; only-secondary → no confirmed cheapest and no complete basket; labelled; old/offline data without (or with an invalid) source trace is never implicitly confirmed");
