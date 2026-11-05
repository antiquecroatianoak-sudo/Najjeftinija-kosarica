// Mali katalog za izvornu Android aplikaciju, izveden iz objavljenog cjenika (proizvodi.json).
// Ne mijenja cijene: svaka cijena je najniža objavljena cijena proizvoda u lancu (procjena po lancu, ne poslovnica).
// Uporaba: node scripts/app_katalog.cjs <proizvodi.json> <izlaz.json> [lanci odvojeni zarezom]
"use strict";
const fs = require("node:fs");
const path = require("node:path");
const zlib = require("node:zlib");
const Skupine = require("../site/skupine.js");

const JEDINICE = ["kg", "l", "kom"];
// Zadane količine iz vlasnikovih uputa; ostale skupine dobivaju najčešće pakiranje.
const ZADANO = { kruh: [0.5, "kg"], mlijeko: [1, "l"], krumpir: [1, "kg"], jaja: [10, "kom"] };
const PRVI_LANCI = ["konzum", "lidl", "kaufland", "spar", "plodine"];

function izgradi(podaci, trazeniLanci = PRVI_LANCI) {
  if (podaci.verzija !== 2 || !Array.isArray(podaci.proizvodi)) throw new Error("Nepoznat oblik cjenika");
  const kljuc = (s) => String(s).toLowerCase().replace(/[^a-z]/g, "");
  const odabrani = [];
  podaci.lanci.forEach((ime, i) => { if (trazeniLanci.includes(kljuc(ime))) odabrani.push(i); });
  if (!odabrani.length) throw new Error("Nijedan traženi lanac nije u cjeniku: " + trazeniLanci.join(","));
  const lokalni = new Map(odabrani.map((g, j) => [g, j]));

  const s = Skupine.pripremi(podaci.proizvodi);
  const z = Skupine.zaAplikaciju();
  const grupe = z.vrste.map((v) => ({ id: v.id, naziv: v.naziv, aliasi: v.aliasi }));
  const indeksGrupe = new Map(grupe.map((g, i) => [g.id, i]));
  const marke = [], indeksMarke = new Map();
  const proizvodi = [];
  const pakiranja = new Map();
  const stat = { ulaz: podaci.proizvodi.length, bezSkupine: 0, bezKolicine: 0, bezOdabranihLanaca: 0, sumnjivaCijena: 0 };

  podaci.proizvodi.forEach((p, i) => {
    const vrsta = s.vrstaProizvoda(i);
    if (!vrsta) { stat.bezSkupine++; return; }
    const jed = JEDINICE.indexOf(p[3]);
    if (!(p[2] > 0) || jed < 0) { stat.bezKolicine++; return; }
    const cijene = [];
    const lanciCijena = p[5], ponude = p[6] || [];
    for (let k = 0, red = 0; k < lanciCijena.length; k += 2, red++) {
      const lj = lokalni.get(lanciCijena[k]);
      if (lj === undefined) continue;
      const eur = lanciCijena[k + 1];
      // Sumnjive cijene (0 € ili ekstremno visoke za jedinicu) ne ulaze u usporedbu.
      const poJedinici = eur / p[2];
      if (!(eur > 0) || poJedinici > 2000) { stat.sumnjivaCijena++; continue; }
      const pon = ponude[red] || [];
      const zastavice = (pon[3] ? 1 : 0) | (pon[2] > eur + 0.005 ? 2 : 0); // 1 akcija, 2 poslovnice imaju različite cijene
      cijene.push(lj, Math.round(eur * 100), zastavice);
    }
    if (!cijene.length) { stat.bezOdabranihLanaca++; return; }
    let m = -1;
    const marka = p[7] >= 0 && podaci.marke ? podaci.marke[p[7]] : "";
    if (marka) {
      if (!indeksMarke.has(marka)) { indeksMarke.set(marka, marke.length); marke.push(marka); }
      m = indeksMarke.get(marka);
    }
    const rijeci = Skupine.analiziraj(p[0], p[4]).rijeci.join(" ");
    const g = indeksGrupe.get(vrsta);
    proizvodi.push([p[0], m, p[2], jed, g, rijeci, cijene]);
    const kl = g + "|" + jed;
    pakiranja.set(kl, (pakiranja.get(kl) || []).concat(p[2]));
  });

  // Zadana količina: iz uputa ili najčešće pakiranje u najčešćoj jedinici skupine.
  grupe.forEach((gr, gi) => {
    if (ZADANO[gr.id]) { gr.zadano = [ZADANO[gr.id][0], JEDINICE.indexOf(ZADANO[gr.id][1])]; return; }
    let najbolje = null;
    for (let j = 0; j < JEDINICE.length; j++) {
      const lista = pakiranja.get(gi + "|" + j);
      if (lista && (!najbolje || lista.length > najbolje.lista.length)) najbolje = { j, lista };
    }
    if (!najbolje) return;
    const broj = new Map();
    for (const x of najbolje.lista) broj.set(x, (broj.get(x) || 0) + 1);
    const cesto = [...broj].sort((a, b) => b[1] - a[1] || a[0] - b[0])[0][0];
    gr.zadano = [cesto, najbolje.j];
  });

  return {
    katalog: {
      verzija: 1, drzava: "HR", valuta: "EUR", jezik: "hr",
      datum: podaci.datum, izdanje: podaci.izdanje || "", azurirano: podaci.azurirano || "",
      napomena: "Cijene su iz službenih cjenika trgovina. Cijena na blagajni i dostupnost proizvoda mogu se razlikovati.",
      vrstaCijene: "najniza-u-lancu",
      lanci: odabrani.map((i) => podaci.lanci[i]),
      jedinice: JEDINICE,
      prijedlozi: z.prijedlozi, nastavci: z.nastavci, zamjene: z.zamjene,
      grupe, marke, proizvodi,
    },
    stat: { ...stat, izlaz: proizvodi.length, lanaca: odabrani.length },
  };
}

if (require.main === module) {
  const [ulaz, izlaz, lanci] = process.argv.slice(2);
  if (!ulaz || !izlaz) { console.error("Uporaba: node scripts/app_katalog.cjs <proizvodi.json> <izlaz.json> [lanci]"); process.exit(2); }
  const podaci = JSON.parse(fs.readFileSync(ulaz, "utf8"));
  const { katalog, stat } = izgradi(podaci, lanci ? lanci.split(",").map((x) => x.trim().toLowerCase()) : PRVI_LANCI);
  if (stat.izlaz < 100) throw new Error("Premalo proizvoda za aplikaciju: " + JSON.stringify(stat));
  fs.mkdirSync(path.dirname(path.resolve(izlaz)), { recursive: true });
  const json = JSON.stringify(katalog);
  fs.writeFileSync(izlaz, json);
  fs.writeFileSync(izlaz + ".gz", zlib.gzipSync(json, { level: 9 }));
  console.log(JSON.stringify({ ...stat, datum: katalog.datum, lanci: katalog.lanci, kB: Math.round(json.length / 1000),
    gzipKB: Math.round(fs.statSync(izlaz + ".gz").size / 1000) }));
}

module.exports = { izgradi, PRVI_LANCI };
