// Katalog za Android aplikaciju: samo odabrani lanci, prepoznate skupine, poznata količina, odbačene sumnjive cijene,
// zastavice akcije i raspona, zadane količine. Sintetički cjenik (nisu stvarne cijene): node tests/app-katalog.cjs
const assert = require("node:assert/strict");
const { izgradi } = require("../scripts/app_katalog.cjs");

// [naziv, opis, iznos, jedinica, rijeciMarke, [lanac, cijena, ...], [[poslovnica, broj, najvisa, akcija], ...], marka]
const podaci = {
  verzija: 2, datum: "2026-11-05", izdanje: "t1", lanci: ["Konzum", "Lidl", "Tommy"], marke: ["Dukat", "Z bregov"],
  proizvodi: [
    ["Dukat mlijeko 2,8% m.m. 1 l", "1 l", 1, "l", 1, [1, 0.99, 0, 1.19], [[3, 40, 0.99, 1], [1, 300, 1.39, 0]], 0],
    ["Z bregov mlijeko 1 l", "1 l", 1, "l", 2, [2, 0.89, 0, 1.09], [[9, 5, 0.89, 0], [1, 2, 1.09, 0]], 1],
    ["Kruh bijeli 500 g", "500 g", 0.5, "kg", 0, [0, 1.29], [[2, 10, 1.29, 0]], -1],
    ["Kruh polubijeli 600 g", "600 g", 0.6, "kg", 0, [0, 0], [[2, 1, 0, 0]], -1],
    ["Nepoznata stvar xyz", "", 0, "", 0, [0, 2.5], [[2, 1, 2.5, 0]], -1],
    ["Jaja M 10 kom", "10 kom", 10, "kom", 0, [2, 2.49], [[9, 1, 2.49, 0]], -1],
    ["Riža 1 kg", "1 kg", 1, "kg", 0, [1, 1.5, 0, 1.6], [[3, 1, 1.5, 0], [1, 1, 1.6, 0]], -1],
    ["Riža 1 kg dugo zrno", "1 kg", 1, "kg", 0, [0, 1.7], [[2, 1, 1.7, 0]], -1],
    ["Riža 500 g", "500 g", 0.5, "kg", 0, [0, 0.9], [[2, 1, 0.9, 0]], -1],
    // Tjestenina: 9 uobičajenih ponuda (≈ 2 €/kg) i jedna nemoguće niska (0,05 € za 500 g) i jedna ekstremno visoka.
    ...Array.from({ length: 9 }, (_, i) => [`Tjestenina špageti ${i} 500 g`, "500 g", 0.5, "kg", 0, [0, 0.9 + i * 0.05], [[2, 1, 0.9 + i * 0.05, 0]], -1]),
    ["Tjestenina penne greška 500 g", "500 g", 0.5, "kg", 0, [0, 0.05, 1, 1.1], [[2, 1, 0.05, 0], [3, 1, 1.1, 0]], -1],
    ["Tjestenina fusilli greška 500 g", "500 g", 0.5, "kg", 0, [0, 25], [[2, 1, 25, 0]], -1],
  ],
};

const { katalog, stat } = izgradi(podaci, ["konzum", "lidl"]);
assert.deepEqual(katalog.lanci, ["Konzum", "Lidl"]);
assert.equal(katalog.valuta, "EUR");
assert.equal(katalog.drzava, "HR");
const ime = (p) => p[0];
const nazivi = katalog.proizvodi.map(ime);
// Jaja su samo u Tommyju (nije odabran), nepoznata stvar nema skupinu, kruh 0 € je sumnjiva cijena.
assert.ok(!nazivi.includes("Jaja M 10 kom"));
assert.ok(!nazivi.includes("Nepoznata stvar xyz"));
assert.ok(!nazivi.includes("Kruh polubijeli 600 g"));
assert.ok(stat.sumnjivaCijena >= 1);
assert.ok(stat.bezOdabranihLanaca >= 1);

const dukat = katalog.proizvodi.find((p) => p[0].startsWith("Dukat"));
// Lidl (lokalno 1) 0,99 € s akcijom i rasponom (najviša 0,99 = bez raspona), Konzum (0) 1,19 € s rasponom do 1,39.
assert.deepEqual(dukat[6], [1, 99, 1, 0, 119, 2]);
assert.equal(katalog.marke[dukat[1]], "Dukat");
assert.equal(katalog.jedinice[dukat[3]], "l");
assert.equal(katalog.grupe[dukat[4]].id, "mlijeko");
assert.ok(dukat[5].split(" ").includes("mlijeko"));

// Z bregov: samo Konzum (Tommy nije odabran).
const zb = katalog.proizvodi.find((p) => p[0].startsWith("Z bregov"));
assert.deepEqual(zb[6], [0, 109, 0]);

const grupa = (id) => katalog.grupe.find((g) => g.id === id);
assert.deepEqual(grupa("mlijeko").zadano, [1, 1]);
assert.deepEqual(grupa("kruh").zadano, [0.5, 0]);
assert.deepEqual(grupa("jaja").zadano, [10, 2]);
// Riža: najčešće pakiranje 1 kg.
assert.deepEqual(grupa("riza").zadano, [1, 0]);
assert.ok(Array.isArray(grupa("mlijeko").aliasi[0]));
assert.ok(katalog.prijedlozi.includes("za"));

// Sumnjiva cijena u odnosu na skupinu: Konzumova 0,05 € ispada, Lidlova 1,10 € ostaje; 25 € za 500 g ispada cijeli proizvod.
const penne = katalog.proizvodi.find((p) => p[0].startsWith("Tjestenina penne"));
assert.deepEqual(penne[6], [1, 110, 0]);
assert.ok(!katalog.proizvodi.some((p) => p[0].startsWith("Tjestenina fusilli")));
assert.equal(stat.sumnjivaUOdnosuNaSkupinu, 2);

assert.throws(() => izgradi(podaci, ["nepostojeci"]), /Nijedan/);
console.log("app-katalog: sve provjere prošle");

// Ispitni katalog za Kotlin testove jezgre: generira ga isti graditelj, pa se oblik ne može razići.
const fs = require("node:fs");
const path = require("node:path");
const ispitni = {
  verzija: 2, datum: "2026-11-05", izdanje: "kotlin", lanci: ["Konzum", "Lidl", "Kaufland"], marke: ["Dukat", "Z bregov"],
  proizvodi: [
    ["Dukat mlijeko 2,8% m.m. 1 l", "1 l", 1, "l", 1, [1, 0.99, 0, 1.19], [[3, 40, 0.99, 1], [1, 300, 1.39, 0]], 0],
    ["Z bregov mlijeko 1 l", "1 l", 1, "l", 2, [0, 0.95, 2, 1.05], [[1, 5, 0.95, 0], [9, 2, 1.05, 0]], 1],
    ["Mlijeko trajno 0,5 l", "500 ml", 0.5, "l", 0, [2, 0.45], [[9, 1, 0.45, 0]], -1],
    ["Zobeno mlijeko 1 l", "1 l", 1, "l", 0, [1, 1.49], [[3, 1, 1.49, 0]], -1],
    ["Kruh bijeli 500 g", "500 g", 0.5, "kg", 0, [0, 1.29, 1, 1.19], [[2, 10, 1.29, 0], [3, 1, 1.19, 0]], -1],
    ["Kruh crni 700 g", "700 g", 0.7, "kg", 0, [0, 1.59], [[2, 10, 1.59, 0]], -1],
    ["Jaja M 10 kom", "10 kom", 10, "kom", 0, [1, 2.29, 2, 2.49], [[3, 1, 2.29, 0], [9, 1, 2.49, 0]], -1],
    ["Jaja L 6 kom", "6 kom", 6, "kom", 0, [0, 1.69], [[2, 1, 1.69, 0]], -1],
    ["Sir gauda 400 g", "400 g", 0.4, "kg", 0, [0, 3.99, 2, 3.49], [[2, 1, 3.99, 0], [9, 1, 3.49, 0]], -1],
    ["Sir svježi 250 g", "250 g", 0.25, "kg", 0, [1, 1.19], [[3, 1, 1.19, 0]], -1],
    ["Rajčica 1 kg", "1 kg", 1, "kg", 0, [2, 1.99], [[9, 1, 1.99, 0]], -1],
  ],
};
const izlaz = path.join(__dirname, "../android/jezgra/src/test/resources/katalog-test.json");
const novi = JSON.stringify(izgradi(ispitni, ["konzum", "lidl", "kaufland"]).katalog, null, 0);
if (process.argv.includes("--zapisi")) {
  fs.mkdirSync(path.dirname(izlaz), { recursive: true });
  fs.writeFileSync(izlaz, novi);
}
assert.equal(fs.readFileSync(izlaz, "utf8"), novi, "Ispitni katalog za Kotlin nije usklađen: node tests/app-katalog.cjs --zapisi");
console.log("app-katalog: ispitni katalog za Kotlin usklađen");
