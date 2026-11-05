// Testovi logike aplikacije (glasovni popis, količine, rezultati A/B/C, zamjena).   node --test tests/
import { test, before } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, readdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

import { norm, korijen, prikazPakiranja, eur, uOsnovnu } from '../app/js/tekst.js';
import { pripremiGrupe, rastavi, prepoznaj, kanon, blizu } from '../app/js/popis.js';
import { Baza, pragPoslovnica, rezultatA, rezultatB, rezultatC, nacinKupnje, procjenaUstede, akcije, udaljenost } from '../app/js/usporedba.js';

const KORIJEN = join(dirname(fileURLToPath(import.meta.url)), '..');
let baza; let grupe; let poslovnice; let izlaz;
const gid = (id) => grupe.findIndex((g) => g.id === id);
const prodavaciLanaca = (b, lanci = Object.keys(b.lanci)) => lanci.map((id) => ({ id, naziv: id, cijena: b.lanci[id].cijena }));

before(() => {
  const tmp = mkdtempSync(join(tmpdir(), 'kosarica-'));
  execFileSync('python3', ['-c', `import sys; sys.path.insert(0, ${JSON.stringify(join(KORIJEN, 'tests'))}); import primjer; primjer.napravi_sve(__import__('pathlib').Path(${JSON.stringify(tmp)}))`]);
  izlaz = join(tmp, 'izlaz');
  execFileSync('python3', [join(KORIJEN, 'uvoz/uvoz.py'), '--arhiva', join(tmp, '2026-11-05.zip'), join(tmp, '2026-11-04.zip'),
    '--izlaz', izlaz, '--bez-dopune', '--privremeno', join(tmp, 'tmp')]);
  grupe = JSON.parse(readFileSync(join(izlaz, 'grupe.json'))).grupe;
  baza = new Baza(JSON.parse(readFileSync(join(izlaz, 'proizvodi.json'))), grupe);
  poslovnice = JSON.parse(readFileSync(join(izlaz, 'poslovnice.json'))).p;
  pripremiGrupe(grupe);
});

test('normalizacija je ista kao u uvozu', () => {
  assert.equal(norm('Mlijeko SVJEŽE 2,8% m.m.'), 'mlijeko svjeze 2 8% m m');
  assert.equal(norm('Čokolada  đ'), 'cokolada d');
  assert.equal(korijen('jabuke'), 'jabuk');
});

test('prikaz količine i cijene', () => {
  assert.equal(prikazPakiranja(0.5, 'kg'), '500 g');
  assert.equal(prikazPakiranja(1.5, 'l'), '1,5 l');
  assert.equal(prikazPakiranja(10, 'kom'), '10 kom');
  assert.equal(eur(129), '1,29 €');
  assert.deepEqual(uOsnovnu(500, 'g'), [0.5, 'kg']);
});

test('glasovni popis: količine, jedinice i zadane količine', () => {
  const s = rastavi('dvije litre mlijeka, kruh i deset jaja');
  assert.equal(s.length, 3);
  assert.deepEqual([s[0].g, s[0].kolicina, s[0].jedinica, s[0].zadano], [gid('mlijeko'), 2, 'l', false]);
  assert.deepEqual([s[1].g, s[1].pg, s[1].kolicina, s[1].jedinica, s[1].zadano], [gid('kruh'), -1, 500, 'g', true]);
  assert.deepEqual([s[2].g, s[2].kolicina, s[2].jedinica], [gid('jaja'), 10, 'kom']);
  const k = rastavi('pola kile krumpira i 1,5 l vode');
  assert.deepEqual([k[0].g, k[0].kolicina, k[0].jedinica], [gid('krumpir'), 0.5, 'kg']);
  assert.deepEqual([k[1].g, k[1].kolicina, k[1].jedinica], [gid('voda'), 1.5, 'l']);
  const d = rastavi('dva mlijeka');
  assert.deepEqual([d[0].kolicina, d[0].jedinica], [2, 'l']);       // 2 × zadano 1 l
  const m = rastavi('500 grama sira, jedan i pol kilogram jabuka');
  assert.deepEqual([m[0].g, m[0].kolicina, m[0].jedinica], [gid('sir'), 500, 'g']);
  assert.deepEqual([m[1].g, m[1].kolicina, m[1].jedinica], [gid('jabuke'), 1.5, 'kg']);
});

test('glasovni popis: podgrupe i nepoznate riječi', () => {
  const kruh = grupe[gid('kruh')];
  const p = prepoznaj('kruh sa sjemenkama');
  assert.equal(p.g, gid('kruh'));
  assert.equal(kruh.pod[p.pg].id, 'sjemenke');
  const t = prepoznaj('trajno mlijeko');
  assert.equal(grupe[t.g].pod[t.pg].id, 'trajno');
  const n = rastavi('nutella');
  assert.equal(n[0].g, gid('dzem'));
  const x = rastavi('špageti barilla');
  assert.equal(x[0].g, gid('tjestenina'));
  const z = rastavi('kvrgavi zmaj');
  assert.equal(z[0].g, -1);
  assert.equal(z[0].upit, 'kvrgavi zmaj');
});

test('rezultat A: "kruh" traži sve vrste kruha i nalazi najjeftiniji za 500 g', () => {
  const [stavka] = rastavi('kruh');
  const [a] = rezultatA(baza, [stavka], prodavaciLanaca(baza));
  assert.ok(a.rang.length >= 5, 'sve vrste kruha');
  assert.ok(a.rang.every((r) => baza.p[r.i][4] === gid('kruh')));
  assert.ok(!a.rang.some((r) => baza.p[r.i][0].startsWith('Brašno')));
  for (let k = 1; k < a.rang.length; k++) assert.ok(a.rang[k - 1].trosak <= a.rang[k].trosak);
  // 310 g kruh: za 500 g trebaju 2 pakiranja
  const mali = a.rang.find((r) => baza.p[r.i][6] === '3850104000066');
  assert.equal(mali.pakiranja, 2);
  assert.equal(mali.trosak, mali.cijena * 2);
});

test('rezultat A: mlijeko 1 l uzima i dva pakiranja od 0,5 l kad je to jeftinije, i prikazuje broj pakiranja', () => {
  const stavka = { id: 'x', g: gid('mlijeko'), pg: -1, kolicina: 1, jedinica: 'l' };
  const nacin = nacinKupnje(baza, stavka);
  const pola = nacin.opcije.find((o) => baza.p[o.i][2] === 0.5);
  assert.equal(pola.pakiranja, 2);
  const [a] = rezultatA(baza, [stavka], prodavaciLanaca(baza));
  assert.ok(a.najbolja.trosak <= Math.min(...a.rang.map((r) => r.trosak)));
});

test('zamjena: odbijeni proizvod se preskače, sljedeći je sljedeći najjeftiniji', () => {
  const stavka = { id: 'x', g: gid('kruh'), pg: -1, kolicina: 500, jedinica: 'g', odbijeni: [] };
  const [prije] = rezultatA(baza, [stavka], prodavaciLanaca(baza));
  stavka.odbijeni.push(prije.najbolja.i);
  const [poslije] = rezultatA(baza, [stavka], prodavaciLanaca(baza));
  assert.equal(poslije.najbolja.i, prije.rang[1].i);
  const b = rezultatB(baza, [stavka], prodavaciLanaca(baza));
  assert.ok(b.every((r) => !r.stavke[0] || r.stavke[0].i !== prije.najbolja.i));
});

test('rezultat B i C: zbroj, nedostajuće stavke, par trgovina nije skuplji od jedne', () => {
  const stavke = rastavi('mlijeko, kruh, jaja, kava, pileća prsa, banane');
  const pr = prodavaciLanaca(baza);
  const b = rezultatB(baza, stavke, pr);
  assert.equal(b.length, pr.length);
  for (const r of b) assert.equal(r.ukupno, r.stavke.reduce((s, p) => s + (p ? p.trosak : 0), 0));
  for (let k = 1; k < b.length; k++) assert.ok(b[k - 1].nedostaje < b[k].nedostaje || (b[k - 1].nedostaje === b[k].nedostaje && b[k - 1].ukupno <= b[k].ukupno));
  // Studenac nema pileća prsa u primjeru
  const studenac = b.find((r) => r.prodavac.id === 'studenac');
  assert.ok(studenac.nedostaje >= 1);
  const c = rezultatC(b);
  assert.ok(c.length > 0);
  const najB = b.find((r) => r.nedostaje === 0);
  assert.ok(c[0].ukupno <= najB.ukupno);
  // A je donja granica svega
  const a = rezultatA(baza, stavke, pr).reduce((s, r) => s + (r.najbolja ? r.najbolja.trosak : 0), 0);
  assert.ok(a <= c[0].ukupno);
  const u = procjenaUstede(b, najB.ukupno);
  assert.ok(u.usteda >= 0 && u.prosjek >= najB.ukupno);
});

test('samo odabrane trgovine se pretražuju', () => {
  const stavke = rastavi('mlijeko i kruh');
  const a = rezultatA(baza, stavke, prodavaciLanaca(baza, ['konzum', 'spar']));
  for (const r of a) for (const x of r.rang) assert.ok(['konzum', 'spar'].includes(x.prodavac.id));
});

test('stvarna poslovnica: cijene iz datoteke poslovnice, bez pogrešne 100× cijene', () => {
  const konzumSplit = poslovnice.find((p) => p[0] === 'konzum' && p[3] === 'Split');
  const dat = JSON.parse(readFileSync(join(izlaz, 's', konzumSplit[7] + '.json')));
  const cijene = baza.cijenePoslovnice('konzum', dat);
  const mlijeko = baza.poBarkodu.get('3850108000021');
  assert.equal(cijene[mlijeko], 0, 'pogrešna cijena (100×) je odbačena, proizvod se ne prikazuje u toj poslovnici');
  const kava = baza.poBarkodu.get('3850115000011');
  assert.ok(cijene[kava] > baza.lanci.konzum.cijena[kava], 'Split je skuplji od uobičajene cijene u primjeru');
  // sve datoteke se mogu pročitati
  for (const f of readdirSync(join(izlaz, 's'))) {
    const d = JSON.parse(readFileSync(join(izlaz, 's', f)));
    assert.equal(d.d.length, d.c.length);
  }
});

test('akcije i udaljenost', () => {
  const ak = akcije(baza, Object.keys(baza.lanci));
  assert.ok(ak.length > 0);
  assert.ok(ak.every((x) => x.redovna > x.cijena));
  for (let k = 1; k < ak.length; k++) assert.ok(ak[k - 1].popust >= ak[k].popust);
  const km = udaljenost(45.815, 15.9819, 45.3271, 14.4422);   // Zagreb–Rijeka ≈ 131 km zračno
  assert.ok(km > 120 && km < 140);
});

test('marka ili posebna riječ sužava pretragu unutar grupe ("Dukat mlijeko", "nutella")', () => {
  const [s] = rastavi('dukat mlijeko');
  assert.equal(s.g, gid('mlijeko'));
  assert.equal(s.filtar, 'dukat');
  const k = baza.kandidati(s);
  assert.ok(k.length > 0 && k.every((i) => baza.p[i][1] === 'Dukat'));
  const [obicno] = rastavi('mlijeko');
  assert.equal(obicno.filtar, '');
  assert.ok(baza.kandidati(obicno).length > k.length);
  const [j] = rastavi('jana');
  assert.equal(j.g, gid('voda'));
  assert.ok(baza.kandidati(j).every((i) => baza.p[i][1] === 'Jana'));
  // riječ koje nema u grupi ne smije isprazniti rezultat
  const [n] = rastavi('zmajeva voda');
  assert.equal(n.g, gid('voda'));
  assert.equal(n.filtar, 'zmajeva');
  assert.ok(!baza.filtarPronaden(n));
  assert.ok(baza.kandidati(n).length >= 2);
  assert.equal(rastavi('nutella')[0].filtar, 'nutella');
  assert.equal(rastavi('kruh sa sjemenkama')[0].filtar, '');
  assert.equal(rastavi('pileća prsa')[0].filtar, '');
});

test('ne nudi pakiranje mnogo veće od traženog kad postoji primjereno', () => {
  const stavka = { id: 'v', g: gid('voda'), pg: -1, kolicina: 1.5, jedinica: 'l' };
  const n = nacinKupnje(baza, stavka);
  assert.ok(n.opcije.every((o) => baza.p[o.i][2] * o.pakiranja <= 1.5 * 2.5));
  assert.ok(!n.opcije.some((o) => baza.p[o.i][2] === 9), 'nema 6×1,5 l za 1,5 l');
  // samo veliko pakiranje: ipak se nudi
  const velika = { id: 'v2', g: gid('voda'), pg: -1, kolicina: 9, jedinica: 'l' };
  assert.ok(nacinKupnje(baza, velika).opcije.some((o) => baza.p[o.i][2] === 9));
});

test('prepoznavanje govora: "mljeko", "mleko", jedno krivo slovo – ista grupa kao "mlijeko" (prijava vlasnika)', () => {
  const grupe = JSON.parse(readFileSync(join(KORIJEN, 'uvoz', 'grupe.json'), 'utf8')).grupe;
  pripremiGrupe(grupe);
  const id = (t) => { const p = prepoznaj(t); return p ? grupe[p.g].id : null; };
  for (const t of ['mlijeko', 'mljeko', 'mleko', 'Mljeko.', 'mlieko', 'dvije litre mljeka']) {
    assert.equal(grupe[rastavi(t)[0].g].id, 'mlijeko', t);
  }
  assert.equal(rastavi('mljeko')[0].jedinica, 'l');                     // ne "1 pakiranje"
  for (const t of ['mljeko', 'mleko', 'mlieko', 'Mlijeka']) assert.equal(rastavi(t)[0].filtar, '', `${t}: drugi zapis imena grupe nije filtar marke`);
  assert.equal(rastavi('Dukat mlijeko')[0].filtar, 'dukat');           // prava marka i dalje sužava
  assert.equal(id('beli kruh'), 'kruh');
  assert.equal(id('jogrut'), 'jogurt');
  assert.equal(id('salama'), 'suhomesnato');                            // slične riječi ostaju različite
  assert.equal(id('salata'), 'salata');
  assert.equal(id('sirup'), 'sok');
  assert.equal(id('xyzabc'), null);
  assert.equal(kanon('mlijeko'), kanon('mljeko'));
  assert.ok(blizu('mlieko', 'mleko') && blizu('jogrut', 'jogurt') && !blizu('sir', 'sirup'));
});

test('procjena po lancu: proizvod iz samo jedne poslovnice velikog lanca nije cijena lanca', () => {
  assert.equal(pragPoslovnica(188), 2);
  assert.equal(pragPoslovnica(3), 1);
  const proizvodi = {
    p: [['Vino Arabella Merlot', 'Arabella', 0.75, 'l', -1, -1, ''], ['Vino crno 0,75 l', '', 0.75, 'l', -1, -1, '']],
    l: {
      veliki: { i: [0, 1], t: [20, 399], n: [0, 0], x: [0, 0], r: [0, 0], s: [1, 188] },
      mali: { i: [0], t: [25], n: [0], x: [0], r: [0], s: [1] },
    },
  };
  const b = new Baza(proizvodi, []);
  assert.equal(b.lanci.veliki.procjena[0], 0);                          // 1 od 188 poslovnica: nije u procjeni
  assert.equal(b.lanci.veliki.procjena[1], 399);
  assert.equal(b.lanci.veliki.cijena[0], 20);                           // stvarna poslovnica i dalje ima cijenu
  assert.equal(b.lanci.mali.procjena[0], 25);                           // mali lanac: svaki proizvod vrijedi
});

test('neobično niska cijena se označi, ali se ne briše ni ne premješta', () => {
  const p = [['Pileći batak-zabatak za gastro', '', 1, 'kg', 0, -1, '']];
  const l = { a: { i: [0], t: [29], n: [0], x: [0], r: [0], s: [1] } };
  for (let k = 1; k <= 30; k++) { p.push([`Pileći batak ${k}`, '', 1, 'kg', 0, -1, '']); l[`c${k}`] = { i: [k], t: [400 + k], n: [0], x: [0], r: [0], s: [5] }; }
  const b = new Baza({ p, l }, [{ id: 'piletina', pod: [] }]);
  assert.equal(b.sumnjivoNiska(0, 29), true);                // 0,29 €/kg prema ~4 €/kg
  assert.equal(b.sumnjivoNiska(1, 401), false);
  assert.equal(b.lanci.a.cijena[0], 29);                     // cijena ostaje u usporedbi
});
