const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const Skupine = require('../site/skupine.js');
const nodes = new Map();
function node(id) {
 if (!nodes.has(id)) nodes.set(id, {hidden: false, textContent: '', classList: {toggle(){}}, setAttribute(){}});
 return nodes.get(id);
}
const instances = [], timers = new Map(), alerts = [];
let timerID = 0;
class Speech {
 constructor(){instances.push(this);}
 start(){this.started=true;}
 stop(){this.stopped=true;}
 result(text, final=true) {
  const r = [{transcript: text}]; r.isFinal = final;
  this.onresult({results: [r], resultIndex: 0});
 }
}
let source = fs.readFileSync(require('node:path').join(__dirname, '../site/aplikacija.js'), 'utf8');
source = source.slice(0, source.indexOf('// ---------- Prikaz ----------'));
const context = vm.createContext({assert, Skupine, window: {SpeechRecognition: Speech}, localStorage: {getItem:()=>null,setItem(){}}, document: {getElementById: node,addEventListener(){}}, alert: s=>alerts.push(s), setTimeout: f=>{timers.set(++timerID,f);return timerID;}, clearTimeout: id=>timers.delete(id)});
vm.runInContext(source + '\nfunction prikazi() {}', context);
const run = s => vm.runInContext(s, context);
run('pokreniSlusanje()');
assert.equal(instances[0].continuous,true);
instances[0].result('kruh mlijeko sok od naranče crno vino',false);
run('assert.equal(stanje.popis.length,0)');
instances[0].result('kruh mlijeko sok od naranče crno vino');
instances[0].result('kruh mlijeko sok od naranče crno vino');
run('pokreniSlusanje()');assert(instances[0].stopped);instances[0].onend();
assert.deepEqual(Array.from(run('stanje.popis.map(x=>x.naziv)')),['Kruh','Mlijeko','Sok od naranče','Crno vino']);
run('assert.equal(glasovniUnos,null); pokreniSlusanje()');
instances[1].result('sir maslac');run('pokreniSlusanje()');instances[1].onend();
assert.equal(run('stanje.popis.length'),6,'second dictation appends without clearing first');
run('pokreniSlusanje()');instances[2].result('jogurt');instances[2].onend();
assert.equal(run('stanje.popis.length'),6,'pause does not submit');
const pending=[...timers.values()];timers.clear();pending.forEach(f=>f());
assert.equal(instances.length,4);instances[3].result('jaja');
run('pokreniSlusanje()');instances[3].onend();
assert.deepEqual(Array.from(run('stanje.popis.slice(-2).map(x=>x.naziv)')),['Jogurt','Jaja']);
run('pokreniSlusanje()');instances[4].onend();
run('pokreniSlusanje()');assert.equal(timers.size,0,'stop during pause cancels restart');
assert.equal(run('glasovniUnos'),null);
run('pokreniSlusanje()');instances[5].onerror({error:'not-allowed'});instances[5].onend();
assert.equal(run('glasovniUnos'),null);assert.equal(timers.size,0);assert.equal(alerts.length,1);
assert.equal(run('stanje.popis.length'),8,'denied session does not erase saved list');
assert.deepEqual(Array.from(run('razdvojiGlasovniPopis("kruh dva mlijeka sok od naranče crno vino")')),['kruh','dva mlijeka','sok od naranče','crno vino']);
console.log('VOICE PASS: multiple items, two-button toggle, repeated sessions, pauses/restarts, no duplicate results, permission denial');
