const assert=require('node:assert/strict');
const fs=require('fs');
const Skupine=require('../site/skupine.js');
const names=[
 'Kruh bijeli 50 g', 'Kruh polubijeli 150 g', 'Marka Domaći kruh 500 g', 'Ciabatta 250 g', 'Toast 500 g',
 'Vrećice za kruh 1 kom', 'Košarica za kruh', 'Kalup za kruh', 'Krušne mrvice 500 g Moj kruh', 'Kockice kruha 200 g',
 'Sok od naranče 100 ml', 'Marka Sok naranča 500 ml', 'Juice naranača 2 L', 'Sok od naranče i jabuke 1 L',
 'Sok jabuka 1 L', 'Sirup naranča 0,5 L', 'Sok nektar naranča 1 L', 'Sok Fizzy naranča 0,33 L',
 'Sok od naranče s pulpom 1 L', 'Sok naranče 100% 1 L',
 'Sir gouda 250 g', 'Sirup 1 L', 'BR.02 kist', 'Čips sir i luk 150 g', 'Sir Brie 200 g',
 'Jaja 10 kom', 'Boja za jaja', 'Ukrasno jaje 1 kom', 'Jaja plastična 6 kom',
 'Mlijeko 1 L', 'Mlijeko za tijelo 400 ml', 'Mlijeko kokosovo 400 ml', 'Čokolada s mlijekom 100 g',
 'Ulje suncokretovo 1 L', 'Ulje za motore 100 ml', 'Ulje mirisno 10 ml',
 'BRAŠNO GLATKO 1 KG', 'BRAŠNO KRMNO 40 KG', 'Kava 200 g', 'Šalica za kavu',
 'Sok mandarina naranča 1 L', 'Ulje maslinovo 0,25 L', 'Ulje maslinovo 1 L',
 'Mlijeko svježe 1 L', 'Mlijeko trajno 1 L', 'Brašno glatko 500 g',
];
const input=names.map(n=>[n,'',1,'kom',n.startsWith('Marka ')?1:0,[0,2]]);
const g=Skupine.pripremi(input);
function exact(q,wanted){assert.deepEqual([...g.pogoci(q)].sort((a,b)=>a-b),wanted.sort((a,b)=>a-b),q);}
exact('kruh',[0,1,2,3,4]);
exact('sok od naranče',[10,11,12,18,19]);
exact('sok od jabuke i naranče',[13]);
exact('sir',[20,24]); exact('jaja',[25]); exact('mlijeko',[29,43,44]); exact('ulje',[33,41,42]);
exact('brašno',[36,45]);exact('brašno krmno',[37]);exact('kava',[38]);
exact('mlijeko svježe',[43]);exact('maslinovo ulje',[41,42]);
assert(g.moguciPogoci('jaja').includes(28), 'nejasan naziv ostaje za pregled');
assert(!g.pogoci('sir').includes(22),'BR. nije Brie');
assert.equal(g.pogoci('nepoznati naziv'),null,'nepoznati upit ne blokira pretragu');
if (!process.argv[2]) { console.log('GROUP FIXTURES PASS'); process.exit(0); }
const p=JSON.parse(fs.readFileSync(process.argv[2]));
console.time('Cijeli cjenik');const all=Skupine.pripremi(p.proizvodi);console.timeEnd('Cijeli cjenik');
const pregled=['kruh','sok od naranče','sir','jaja','mlijeko','ulje','brašno','jogurt','maslac','riža','tjestenina','kava','voda','krumpir','jabuka'];
for(const q of pregled){const ids=all.pogoci(q);assert(ids.length>0,q);assert.equal(new Set(ids).size,ids.length);console.log(q,ids.length,'prepoznato;',all.moguciPogoci(q).length,'za pregled');}
const report={datum:p.datum,ukupno:all.ukupno,definicije:Skupine.definicije.length,skupine:all.katalog.length,prepoznataVrsta:all.ukupno-all.nerazvrstano,neutvrdjenaVrsta:all.nerazvrstano,napomena:'Automatska procjena vrste nije ručna potvrda točnosti. Neutvrđeni proizvodi ostaju u cjeniku i pretrazi.',katalog:all.katalog.map(({indeksi,...s})=>({...s,broj:indeksi.length}))};
fs.writeFileSync('classification-audit.json',JSON.stringify(report,null,2));
console.log(JSON.stringify({...report,katalog:undefined}));
console.log('GROUP TESTS PASS');
