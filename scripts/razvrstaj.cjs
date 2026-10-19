// Obnavlja skupine nakon uvoza cjenika. Ne mijenja izvorne cijene ni artikle.
const fs = require('node:fs');
const path = require('node:path');
const Skupine = require('../site/skupine.js');
const source = process.argv[2] || path.join(__dirname, '../site/data/proizvodi.json');
const output = process.argv[3] || path.join(path.dirname(source), 'skupine.json');
const podaci = JSON.parse(fs.readFileSync(source, 'utf8'));
if (podaci.verzija !== 2 || !Array.isArray(podaci.proizvodi) || !podaci.proizvodi.length) throw new Error('Nema valjanog cjenika za razvrstavanje');
const skupine = Skupine.pripremi(podaci.proizvodi);
const indeks = skupine.izvezi();
indeks.datum = podaci.datum;
fs.mkdirSync(path.dirname(output), {recursive:true});
fs.writeFileSync(output + '.tmp', JSON.stringify(indeks));
fs.renameSync(output + '.tmp', output);
console.log(JSON.stringify({proizvoda: skupine.ukupno, skupina: skupine.katalog.length,
  automatskiPrepoznato: skupine.ukupno - skupine.nerazvrstano, neutvrdjenaVrsta: skupine.nerazvrstano}));
