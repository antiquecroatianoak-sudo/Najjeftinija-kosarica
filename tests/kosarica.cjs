const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
let source = fs.readFileSync(require('node:path').join(__dirname, '../site/aplikacija.js'), 'utf8');
source = source.slice(0, source.lastIndexOf('\nfor (const r of document.querySelectorAll'));
const context = vm.createContext({assert, window: {}, localStorage: {getItem: () => null}, document: {}});
vm.runInContext(source + `
podaci = {lanci: ['A', 'B', 'C'], proizvodi: [
 ['Mlijeko 200 ml', '200 ml', 0.2, 'l', 0, [0, 0.5, 1, 0.6]],
 ['Mlijeko 1 l', '1 l', 1, 'l', 0, [1, 1.2, 0, 1.1]],
 ['Kruh 500 g', '500 g', 0.5, 'kg', 0, [0, 1.5]],
 ['Kruh 1 kg', '1 kg', 1, 'kg', 0, [1, 2]],
 ['Jaja 10 kom', '10 kom', 10, 'kom', 0, [0, 2.5, 1, 3]],
 ['Mlijeko bez količine', '', 0, '', 0, [0, 0.1]],
 ['Mlijeko po kilogramu', '1 kg', 1, 'kg', 0, [0, 0.15]],
]};
rijeci = podaci.proizvodi.map(p => normaliziraj(p[0]).split(' '));
stanje.popis = [{naziv: 'Mlijeko', kom: 2}, {naziv: 'Kruh', kom: 1}];
const offers = ponudeZaGrupu('Mlijeko');
assert.equal(offers[0].i, 1, 'lowest price per litre beats smaller cheaper pack');
assert.equal(offers[0].lanac, 0, 'chain prices need not arrive sorted');
assert.equal(offers[0].poJedinici, 1.1);
let basket = usporedbaKosarice();
assert.equal(basket.najboljeMijesano, 3.1);
assert.equal(basket.zbroj.get(0).usporedno, 4.1);
assert.equal(basket.zbroj.get(1).usporedno, 3.2);
assert.equal(basket.zbroj.get(0).ukupno, 3.7);
assert.equal(basket.zbroj.get(1).ukupno, 4.4);
assert.equal(basket.zbroj.get(2).nema.length, 2, 'missing products never form a complete basket');
for (const row of basket.zbroj.values()) {
 if (!row.nema.length) assert(basket.najboljeMijesano <= row.usporedno + 1e-10);
}
stanje.popis[0].kom = 9;
const larger = usporedbaKosarice();
assert.equal(larger.zbroj.get(0).usporedno, basket.zbroj.get(0).usporedno, 'package counts do not change ranking');
assert.equal(larger.zbroj.get(0).ukupno, 11.4, 'checkout uses package count');
assert.equal(brojPakiranja({kom: 10}, ponuda(4, 0, 2.5)), 10, '10 means 10 packs, including eggs');
stanje.jedna = 'B'; ponudeCache.clear();
assert.equal(ponudeZaGrupu('Mlijeko')[0].lanac, 1);
assert.equal(usporedbaKosarice().najboljeMijesano, 3.1, 'benchmark stable while browsing one chain');
stanje.iskljuceni = ['A']; ponudeCache.clear();
assert.equal(usporedbaKosarice().najboljeMijesano, 3.2);
stanje.iskljuceni = ['A', 'B', 'C']; ponudeCache.clear();
assert.equal(usporedbaKosarice().sveMijesanoIma, false);
`, context);
console.log('BASKET TESTS PASS: normalized units, unsorted prices, package totals, missing items, filters');
