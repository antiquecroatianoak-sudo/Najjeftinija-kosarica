// „Sve u jednom dućanu“: potpuni i nepotpuni lanci, izjednačeni pobjednici, cijela pakiranja, očuvanje količine,
// jednakost sa zbrojem kartica otvorenog lanca, razlika prema kombinaciji, bez potpunog lanca.
// Sintetički cjenik (nisu stvarne cijene): node tests/sve-u-jednom.cjs
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const Skupine = require("../site/skupine.js");

function scenarij(proizvodi, popis) {
  let izvor = fs.readFileSync(path.join(__dirname, "../site/aplikacija.js"), "utf8");
  izvor = izvor.slice(0, izvor.lastIndexOf("\nfor (const r of document.querySelectorAll"));
  const ctx = vm.createContext({ Skupine, window: { scrollTo() {} }, localStorage: { getItem: () => null, setItem() {} },
    document: { addEventListener() {} } });
  vm.runInContext(izvor + `
    const cvor = () => ({ children: [], hidden: false, textContent: "", className: "", set innerHTML(v) { this.children = []; },
      appendChild(c) { this.children.push(c); }, append(...c) { this.children.push(...c); }, setAttribute() {} });
    globalThis.__cvorovi = {};
    document.getElementById = (id) => __cvorovi[id] || (__cvorovi[id] = cvor());
    document.createElement = () => cvor();
    prikaziRezultate = () => {}; spremi = () => {};
    podaci = { datum: "2026-10-21", lanci: ["Konzum", "Lidl", "Plodine"], proizvodi: ${JSON.stringify(proizvodi)} };
    rijeci = podaci.proizvodi.map((x) => normaliziraj(x[0]).split(" "));
    klasifikacija = Skupine.pripremi(podaci.proizvodi, null, rijeci);
    stanje.popis = ${JSON.stringify(popis)};
    globalThis.__kartice = (ime) => {
      stanje.jedna = ime; ponudeCache.clear(); pogociCache.clear();
      stanje.odabir = odabirJedneTrgovine();
      let z = 0;
      for (const s of stanje.popis) {
        const lista = ponudeZaGrupu(s.naziv);
        if (!lista.length) continue;
        const p = lista[(stanje.odabir[s.naziv] || 0) % lista.length];
        z += p.cijena * brojPakiranja(s, p);
      }
      stanje.jedna = null; stanje.odabir = {}; ponudeCache.clear();
      return Math.round(z * 100) / 100;
    };
  `, ctx);
  return ctx;
}
const P = (naziv, iznos, jedinica, cijene) => [naziv, `${iznos} ${jedinica}`, iznos, jedinica, 0, cijene];
// Dvije litre mlijeka: referenca je najpovoljnija ponuda (1 l u Lidlu), pa Konzum treba 4 × 0,5 l.
const popis = [{ naziv: "Mlijeko", kom: 2 }, { naziv: "Kruh", kom: 1 }];
let app = scenarij([
  P("Mlijeko 0,5 l", 0.5, "l", [0, 0.6]),
  P("Mlijeko 1 l", 1, "l", [1, 1.1]),
  P("Kruh 500 g", 0.5, "kg", [0, 1.5, 1, 1.4, 2, 1.0]),
], popis);
let r = vm.runInContext("prikaziJednuTrgovinu()", app);
assert.deepEqual(Array.from(r.potpune, (x) => [x.ime, x.ukupno, x.najpovoljniji]), [["Lidl", 3.6, true], ["Konzum", 3.9, false]]);
assert.equal(vm.runInContext(`brojPakiranja(stanje.popis[0], ponudeZaGrupu("Mlijeko", new Set([0]))[0], true)`, app), 4,
  "two litres in Konzum: 4 × 0,5 l (whole packs, same quantity)");
assert.equal(Math.round(r.kombinacija * 100) / 100, 3.2, "milk 2,20 (Lidl) + bread 1,00 (Plodine)");
assert.deepEqual(Array.from(r.potpune, (x) => x.razlika), [0.4, 0.7]);
assert.equal(r.nepotpune.length, 1);
assert.equal(`${r.nepotpune[0].ime} ${r.nepotpune[0].pokriveno}/${r.nepotpune[0].stavki}`, "Plodine 1/2");
assert(!r.nepotpune[0].najpovoljniji, "a lower partial sum never wins");
for (const x of r.potpune) assert.equal(Math.round(x.ukupno * 100) / 100, app.__kartice(x.ime), `${x.ime}: row = opened cards`);
assert.equal(vm.runInContext("stanje.popis[0].kom", app), 2, "requested amount kept");
const redovi = app.__cvorovi["trgovine-usporedba"].children;
assert.equal(redovi.length, 2);
assert.match(redovi[0].children[0].className, /najpovoljniji/);
assert.equal(redovi[0].children[0].children[0].children[0].textContent, "★ Najniža procjena lanca", "chain row is an estimate from different stores");
assert.equal(app.__cvorovi["nema-potpune"].hidden, true);
// Izjednačeni: oba najpovoljnija, na cent.
app = scenarij([P("Mlijeko 1 l", 1, "l", [0, 0.1, 1, 0.2]), P("Kruh 500 g", 0.5, "kg", [0, 0.2, 1, 0.1])],
  [{ naziv: "Mlijeko", kom: 1 }, { naziv: "Kruh", kom: 1 }]);
r = vm.runInContext("prikaziJednuTrgovinu()", app);
assert.deepEqual(Array.from(r.potpune, (x) => x.najpovoljniji), [true, true]);
// Nijedan lanac nema sve: bez pobjednika i jasna poruka.
app = scenarij([P("Mlijeko 1 l", 1, "l", [0, 1.1]), P("Kruh 500 g", 0.5, "kg", [1, 1.4])], popis);
r = vm.runInContext("prikaziJednuTrgovinu()", app);
assert.equal(r.potpune.length, 0);
assert.equal(app.__cvorovi["nema-potpune"].hidden, false);
assert(r.nepotpune.every((x) => !x.najpovoljniji));
// Prijavljeni slučaj (#11, 6318975930): referenca 1 l. Lidl ima 1 l za 1,00 € i 2 l za 1,60 € (niža jedinična cijena):
// lanac i kombinacija moraju uzeti 1,00 €, a otvoreni Lidl isto što i redak.
app = scenarij([P("Mlijeko 1 l", 1, "l", [0, 0.9, 1, 1]), P("Mlijeko 2 l", 2, "l", [1, 1.6])], [{ naziv: "Mlijeko", kom: 1 }]);
vm.runInContext(`stanje.odabir = { Mlijeko: 1 }; ponudeCache.clear();`, app);
assert.equal(vm.runInContext(`referentnaPonuda("Mlijeko").i`, app), 0, "reference is the 1 l pack");
r = vm.runInContext("prikaziJednuTrgovinu()", app);
const lidl = r.potpune.find((x) => x.ime === "Lidl");
assert.equal(lidl.ukupno, 1, "Lidl: 1 l for 1,00 €, not 2 l for 1,60 €");
assert.equal(Math.round(r.kombinacija * 100) / 100, 0.9);
vm.runInContext(`globalThis.__ref = stanje.odabir;`, app);
// Zbroj kartica otvorenog Lidla s istom referencom (odabirJedneTrgovine uzima ponudu retka).
assert.equal(vm.runInContext(`(() => { const svi = { ...stanje.odabir }; stanje.odabirSvi = svi; stanje.jedna = "Lidl"; ponudeCache.clear();
  stanje.odabir = odabirJedneTrgovine(); const lista = ponudeZaGrupu("Mlijeko"); const p = lista[(stanje.odabir.Mlijeko || 0) % lista.length];
  const z = p.cijena * brojPakiranja(stanje.popis[0], p); stanje.jedna = null; stanje.odabir = svi; ponudeCache.clear(); return z; })()`, app), 1,
  "opened Lidl cards equal its row");
// Pobjednik kombinacije se mijenja zbog zaokruživanja: 3 l; A ima 2 l (0,80 €/l, 2 pakiranja = 3,20 €), B 1 l (0,90 €/l, 3 = 2,70 €).
app = scenarij([P("Mlijeko 2 l", 2, "l", [0, 1.6]), P("Mlijeko 1 l", 1, "l", [1, 0.9])], [{ naziv: "Mlijeko", kom: 3 }]);
vm.runInContext(`stanje.odabir = { Mlijeko: 1 }; ponudeCache.clear();`, app);
r = vm.runInContext("prikaziJednuTrgovinu()", app);
assert.deepEqual(Array.from(r.potpune, (x) => [x.ime, Math.round(x.ukupno * 100) / 100, x.najpovoljniji]), [["Lidl", 2.7, true], ["Konzum", 3.2, false]],
  "whole-pack cost decides, not the lower unit price");
assert.equal(Math.round(r.kombinacija * 100) / 100, 2.7);
assert.equal(vm.runInContext("stanje.popis[0].kom", app), 3, "requested amount kept");
// Nedjeljivo pakiranje: za 1 l postoji samo 5 l → jedno cijelo pakiranje, iznos cijelog pakiranja.
app = scenarij([P("Mlijeko 1 l", 1, "l", [0, 1.0]), P("Mlijeko 5 l", 5, "l", [1, 3.0])], [{ naziv: "Mlijeko", kom: 1 }]);
r = vm.runInContext("prikaziJednuTrgovinu()", app);
assert.equal(r.potpune.find((x) => x.ime === "Lidl").ukupno, 3, "a 5 l pack is not split");
// Lanac bez ijedne stavke (0/Y) također je prikazan, odvojeno i bez iznosa.
assert.equal(r.nepotpune.length, 1);
assert.equal(`${r.nepotpune[0].ime} ${r.nepotpune[0].pokriveno}/${r.nepotpune[0].stavki}`, "Plodine 0/1");
assert.equal(app.__cvorovi["trgovine-nepotpune"].children[0].children[0].children[1].textContent, "—");
// Stvarne poslovnice (review #12): Konzum ima mlijeko samo u jednoj, a kruh samo u drugoj poslovnici. Procjena lanca
// "ima sve" (različite poslovnice), ali nijedna stvarna poslovnica nema cijeli popis; potpuna je samo Lidl poslovnica.
app = scenarij([P("Mlijeko 1 l", 1, "l", [0, 1.0, 1, 1.2]), P("Kruh 500 g", 0.5, "kg", [0, 0.9, 1, 1.1])],
  [{ naziv: "Mlijeko", kom: 1 }, { naziv: "Kruh", kom: 1 }]);
vm.runInContext(`
  podaci.poslovnice = [[0, "K1", "Ilica 1", "Zagreb"], [0, "K2", "Vukovarska 2", "Zagreb"], [1, "L1", "Savska 3", "Zagreb"]];
  for (const p of podaci.proizvodi) p[6] = [];
  podaci.proizvodi[0][6] = [[0, 1, 1.0, 0], [2, 1, 1.2, 0]];
  podaci.proizvodi[1][6] = [[1, 1, 0.9, 0], [2, 1, 1.1, 0]];
  cjeniciPoslovnica.set(0, new Map([[0, 100]]));
  cjeniciPoslovnica.set(1, new Map([[1, 90]]));
  cjeniciPoslovnica.set(2, new Map([[0, 120], [1, 110]]));
  stanje.poslovnice = ["Konzum|K1", "Konzum|K2", "Lidl|L1"];
`, app);
r = vm.runInContext("prikaziJednuTrgovinu()", app);
assert.deepEqual(Array.from(r.potpune, (x) => x.ime), ["Konzum", "Lidl"], "chain estimate: Konzum from two different stores");
assert.deepEqual(Array.from(r.poslovnice.potpune, (x) => [x.ime, x.adresa, Math.round(x.ukupno * 100) / 100, x.najpovoljnija]),
  [["Lidl", "Savska 3, Zagreb", 2.3, true]], "only a store with the whole list is complete");
assert.deepEqual(Array.from(r.poslovnice.ostale, (x) => `${x.adresa} ${x.pokriveno}/${x.stavki}`),
  ["Vukovarska 2, Zagreb 1/2", "Ilica 1, Zagreb 1/2"], "partial stores: more items, then lower partial sum");
assert.equal(app.__cvorovi["nema-potpune-poslovnice"].hidden, true);
vm.runInContext(`stanje.poslovnice = ["Konzum|K1", "Konzum|K2"];`, app);
r = vm.runInContext("prikaziJednuTrgovinu()", app);
assert.equal(r.poslovnice.potpune.length, 0);
assert.equal(app.__cvorovi["nema-potpune-poslovnice"].hidden, false, "no common store: no complete one-store basket");
assert.equal(vm.runInContext(`opisIzvoraCijene(ponudeZaGrupu("Mlijeko")[0])`, app),
  "Poslovnica: Ilica 1, Zagreb · arhiva cijene.dev, nije provjereno sa službenim cjenikom");
vm.runInContext(`podaci.proizvodi[0][6][0] = [0, 3, 1.5, 1]; ponudeCache.clear();`, app);
assert.equal(vm.runInContext(`opisIzvoraCijene(ponudeZaGrupu("Mlijeko")[0])`, app),
  "Poslovnica: Ilica 1, Zagreb · arhiva cijene.dev, nije provjereno sa službenim cjenikom · akcijska cijena · u drugim poslovnicama lanca do 1,50 € (provjeri)");
// Službeni cjenik: poslovnica nosi indeks datoteke, ponuda redak i naziv akcije.
vm.runInContext(`podaci.izvori = [["https://k.hr/c.csv", "2026-10-21"]]; podaci.poslovnice[0][4] = 0;
  podaci.proizvodi[0][6][0] = [0, 3, 1.5, 1, 17, "TNC"]; ponudeCache.clear();`, app);
assert.equal(vm.runInContext(`opisIzvoraCijene(ponudeZaGrupu("Mlijeko")[0])`, app),
  "Poslovnica: Ilica 1, Zagreb · službeni cjenik, redak 17 · akcija: TNC · u drugim poslovnicama lanca do 1,50 € (provjeri)");

console.log("ONE-STORE PASS: complete vs incomplete, X/Y, ties, cents, whole packs, kept quantity, row = opened cards, "
  + "difference to combination, no complete chain, whole-pack cost over unit price (#11 report), winner change by rounding, "
  + "indivisible pack, 0/Y chains shown, real stores: only a store with the whole list is complete, no common store → "
  + "no one-store basket, chain row labelled as estimate, price shows its store / promotion / range");
