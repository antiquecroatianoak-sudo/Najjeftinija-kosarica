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
assert.equal(redovi[0].children[0].children[0].children[0].textContent, "★ Najpovoljniji lanac");
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
console.log("ONE-STORE PASS: complete vs incomplete, X/Y, ties, cents, whole packs, kept quantity, row = opened cards, "
  + "difference to combination, no complete chain");
