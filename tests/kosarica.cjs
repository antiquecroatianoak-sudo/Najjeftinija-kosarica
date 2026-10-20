const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
let source = fs.readFileSync(require('node:path').join(__dirname, '../site/aplikacija.js'), 'utf8');
source = source.slice(0, source.lastIndexOf('\nfor (const r of document.querySelectorAll'));
const context = vm.createContext({assert, window: {}, localStorage: {getItem: () => null}, document: {addEventListener: () => {}}});
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
assert.equal(basket.najboljeMijesano, 4.2);
assert.equal(basket.zbroj.get(0).usporedno, 5.2);
assert.equal(basket.zbroj.get(1).usporedno, 4.4);
assert.equal(basket.zbroj.get(0).ukupno, 5.2);
assert.equal(basket.zbroj.get(1).ukupno, 4.4);
assert.equal(basket.zbroj.get(2).nema.length, 2, 'missing products never form a complete basket');
for (const row of basket.zbroj.values()) {
 if (!row.nema.length) assert(basket.najboljeMijesano <= row.usporedno + 1e-10);
}
stanje.popis[0].kom = 9;
const larger = usporedbaKosarice();
assert.equal(larger.zbroj.get(0).usporedno, 12.9, 'all chains compare the selected nine litres and one kg');
assert.equal(larger.zbroj.get(0).ukupno, 12.9, 'checkout uses package count');
assert.equal(brojPakiranja({kom: 10}, ponuda(4, 0, 2.5)), 10, '10 means 10 packs, including eggs');
stanje.jedna = 'B'; ponudeCache.clear();
assert.equal(ponudeZaGrupu('Mlijeko')[0].lanac, 1);
assert.equal(usporedbaKosarice().najboljeMijesano, 11.9, 'benchmark stable while browsing one chain');
stanje.iskljuceni = ['A']; ponudeCache.clear();
assert(Math.abs(usporedbaKosarice().najboljeMijesano - 12.8) < 1e-9);
// Regression: two one-litre packs must compare against ten 200 ml packs.
stanje.jedna = null; stanje.iskljuceni = []; stanje.odabir = {};
stanje.popis = [{naziv: 'Mlijeko', kom: 2}];
podaci.proizvodi[0][5].push(2, 0.5); pogociCache.clear(); ponudeCache.clear();
const sameVolume = usporedbaKosarice();
assert.equal(sameVolume.zbroj.get(2).usporedno, 5);
assert.equal(sameVolume.zbroj.get(2).ukupno, 5, 'ten 200 ml packs cost five euros for two litres');
assert(sameVolume.jedinice[0].includes('2 l'));
assert.equal(sameVolume.najboljeMijesano, 2.2);
stanje.popis[0].kom = 3;
const threeLitres = usporedbaKosarice();
assert.equal(threeLitres.zbroj.get(2).ukupno, 7.5, '15 small packs supply the same three litres');
// A selected alternative changes the reference amount, not just the name.
stanje.odabir.Mlijeko = 1;
assert(usporedbaKosarice().jedinice[0].includes('0,6 l'));
stanje.iskljuceni = ['A', 'B', 'C']; ponudeCache.clear();
assert.equal(usporedbaKosarice().sveMijesanoIma, false);
prikazi = prikaziRezultate = () => {}; // UI rendering is not under test here
// Regression: browsing one chain must not change the reference quantity
// when chains sell the same group in different package volumes.
podaci = {lanci: ['A', 'B'], proizvodi: [
 ['Mlijeko 1 l', '1 l', 1, 'l', 0, [0, 1]],
 ['Mlijeko 100 ml', '100 ml', 0.1, 'l', 0, [1, 0.2]],
]};
rijeci = podaci.proizvodi.map(p => normaliziraj(p[0]).split(' '));
pogociCache.clear(); ponudeCache.clear();
stanje.iskljuceni = []; stanje.jedna = null; stanje.odabir = {}; stanje.odabirSvi = {};
stanje.popis = [{naziv: 'Mlijeko', kom: 1}];
const allChains = usporedbaKosarice();
assert.deepEqual([...allChains.jedinice], ['Mlijeko: 1 l']);
assert.equal(allChains.najboljeMijesano, 1);
assert.equal(allChains.zbroj.get(1).ukupno, 2, 'ten 100 ml packs in B supply the litre');
stanje.jedna = 'B'; promijeniPostavke(true);
assert.equal(ponudeZaGrupu('Mlijeko')[0].lanac, 1, 'list still shows only chain B');
const oneChain = usporedbaKosarice();
assert.deepEqual([...oneChain.jedinice], ['Mlijeko: 1 l'], 'chain B view keeps one litre');
assert.equal(oneChain.najboljeMijesano, 1);
assert.equal(oneChain.zbroj.get(1).usporedno, 2);
assert.equal(oneChain.zbroj.get(1).ukupno, 2);
assert.equal(brojPakiranja(stanje.popis[0], ponudeZaGrupu('Mlijeko')[0]), 10, 'card in chain B buys ten 100 ml packs for the litre');
stanje.popis[0].kom = 3;
assert.deepEqual([...usporedbaKosarice().jedinice], ['Mlijeko: 3 l'], 'quantity changes still apply in one-chain view');
// A chosen alternative from the all-chains view survives entering and leaving one chain.
stanje.popis[0].kom = 1; stanje.jedna = null; promijeniPostavke(true);
promijeni('Mlijeko', +1);
assert(usporedbaKosarice().jedinice[0].includes('0,1 l'));
stanje.odabirSvi = {...stanje.odabir}; stanje.jedna = 'A'; promijeniPostavke(true);
assert(usporedbaKosarice().jedinice[0].includes('0,1 l'), 'reference kept in chain A view');
promijeni('Mlijeko', +1);
assert(usporedbaKosarice().jedinice[0].includes('0,1 l'), 'browsing inside one chain does not move the reference');
stanje.jedna = null; promijeniPostavke(true);
assert.equal(stanje.odabir.Mlijeko, 1, 'leaving one chain restores the all-chains choice');
// Changing allowed chains resets the reference to the cheapest offer.
stanje.iskljuceni = ['B']; promijeniPostavke();
assert.deepEqual([...usporedbaKosarice().jedinice], ['Mlijeko: 1 l']);
// Regression: the prominent chain amount equals the sum of that chain's cards once opened.
podaci = {lanci: ['A', 'B', 'C'], proizvodi: [
 ['Mlijeko 1 l', '1 l', 1, 'l', 0, [0, 1, 1, 1.5]],
 ['Mlijeko 200 ml', '200 ml', 0.2, 'l', 0, [1, 0.25, 2, 0.4]],
 ['Kruh 500 g', '500 g', 0.5, 'kg', 0, [0, 1.2, 2, 1]],
 ['Kruh bez mase', '', 0, '', 0, [1, 0.9]],
 ['Jaja 10 kom', '10 kom', 10, 'kom', 0, [0, 2, 1, 2.4, 2, 2.2]],
]};
rijeci = podaci.proizvodi.map(p => normaliziraj(p[0]).split(' '));
pogociCache.clear(); ponudeCache.clear();
stanje.iskljuceni = []; stanje.jedna = null; stanje.odabir = {}; stanje.odabirSvi = {};
stanje.popis = [{naziv: 'Mlijeko', kom: 2}, {naziv: 'Kruh', kom: 1}, {naziv: 'Jaja', kom: 1}];
// Same two lines prikaziRezultate uses for each card.
const zbrojKartica = () => stanje.popis.reduce((sum, st) => {
  const ponude = ponudeZaGrupu(st.naziv);
  if (!ponude.length) return sum;
  const p = ponude[(stanje.odabir[st.naziv] || 0) % ponude.length];
  return sum + p.cijena * brojPakiranja(st, p);
}, 0);
const blizu = (a, b, poruka) => assert(Math.abs(a - b) < 1e-9, poruka + ': ' + a + ' != ' + b);
const redovi = usporedbaKosarice().zbroj;
for (const [l, ime] of ['A', 'B', 'C'].entries()) {
  stanje.jedna = ime; promijeniPostavke(true);
  blizu(redovi.get(l).ukupno, zbrojKartica(), 'chain ' + ime + ' row equals its opened cards');
  stanje.jedna = null; promijeniPostavke(true);
}
assert.equal(redovi.get(1).ukupno, 10 * 0.25 + 0.9 + 2.4, 'B: ten 200 ml packs, unranked bread, eggs');
assert.deepEqual([...redovi.get(1).nema], ['Kruh'], 'bread without mass is not comparable in B');
assert.deepEqual([...redovi.get(1).neusporedivo], ['Kruh'], 'but its price still counts in the B checkout amount');
assert(redovi.get(0).usporedno === redovi.get(0).ukupno, 'A sells exactly the reference packs');
// A chosen alternative inside an opened chain moves that chain's row with the cards.
stanje.jedna = 'B'; promijeniPostavke(true);
promijeni('Mlijeko', +1);
blizu(usporedbaKosarice().zbroj.get(1).ukupno, zbrojKartica(), 'B row follows the alternative chosen in B');
assert.deepEqual([...usporedbaKosarice().jedinice].slice(0, 1), ['Mlijeko: 2 l'], 'reference quantity unchanged');
// An alternative chosen in the all-chains view changes the reference for every chain row and card.
stanje.jedna = null; promijeniPostavke(true);
stanje.odabir = {Mlijeko: 1}; stanje.odabirSvi = {Mlijeko: 1};
const alt = usporedbaKosarice();
assert.deepEqual([...alt.jedinice].slice(0, 1), ['Mlijeko: 0,4 l']);
for (const [l, ime] of ['A', 'B', 'C'].entries()) {
  stanje.jedna = ime; promijeniPostavke(true);
  blizu(alt.zbroj.get(l).ukupno, zbrojKartica(), 'chain ' + ime + ' row equals its cards after an all-chains alternative');
  stanje.jedna = null; promijeniPostavke(true);
}
assert.equal(alt.zbroj.get(0).ukupno, 1 + 1.2 + 2, 'A buys one whole litre for 0,4 l');
`, context);
console.log('BASKET TESTS PASS: normalized units, unsorted prices, package totals, missing items, filters');
