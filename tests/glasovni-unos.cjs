const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const Skupine = require('../site/skupine.js');
const nodes = new Map();
function node(id) {
 if (!nodes.has(id)) nodes.set(id, {hidden: false, textContent: '', classList: {toggle(){}}, setAttribute(){}, focus(){this.focused=true;}});
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
assert.equal(instances[0].continuous,false);
assert.equal(instances[0].interimResults,false);
assert.match(node('mikrofon-tekst').textContent,/Pokrećem/);
instances[0].onstart();
assert.match(node('mikrofon-tekst').textContent,/Pokrećem/,'service start is not microphone capture');
instances[0].onaudiostart();
assert.match(node('mikrofon-tekst').textContent,/Završi narudžbu/);
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
assert.equal(run('glasovniUnos'),null);assert.equal(timers.size,0);assert.equal(alerts.length,0);assert.match(node("glasovni-nacrt").textContent,/nije dopušten/);
assert.equal(run('stanje.popis.length'),8,'denied session does not erase saved list');
assert.deepEqual(Array.from(run('razdvojiGlasovniPopis("kruh dva mlijeka sok od naranče crno vino")')),['kruh','dva mlijeka','sok od naranče','crno vino']);
console.log('VOICE PASS: multiple items, two-button toggle, repeated sessions, pauses/restarts, no duplicate results, permission denial');


// Start never confirms: watchdog unlocks and cancels recognizer, old events ignored.
Speech.prototype.abort=function(){this.aborted=true;};
run('pokreniSlusanje()');
let current=instances.at(-1);
[...timers.values()][0]();
assert.equal(run('glasovniUnos'),null);
assert(current.aborted);
assert.match(node('glasovni-nacrt').textContent,/nije pokrenuo/);
const count=run('stanje.popis.length');
current.result('zakašnjeli rezultat');
assert.equal(run('stanje.popis.length'),count);
assert.equal(timers.size,0);
// Audio capture confirmed but no text: timeout, not an endless Listening label.
run('pokreniSlusanje()');current=instances.at(-1);current.onaudiostart();
assert.equal(timers.size,0,'silence after microphone capture must not finish the session');
current.onspeechstart();
[...timers.values()][0]();
assert.equal(run('glasovniUnos'),null);
assert.match(node('glasovni-nacrt').textContent,/nije vratilo tekst/);
// Missing end event after stop must not lock the button or lose interim text.
run('pokreniSlusanje()');current=instances.at(-1);current.result('banana',false);
run('pokreniSlusanje()');[...timers.values()][0]();
assert.equal(run('glasovniUnos'),null);
assert.equal(run('stanje.popis.at(-1).naziv'),'Banana');
// Empty restarts are bounded; audio/network errors have different explanations.
run('pokreniSlusanje()');current=instances.at(-1);current.onend();
const restart=[...timers.values()][0];timers.clear();restart();
current=instances.at(-1);current.onend();
assert.equal(run('glasovniUnos'),null);assert.equal(timers.size,0);
for(const error of ['audio-capture','network','service-not-allowed','language-not-supported']) {
 run('pokreniSlusanje()');current=instances.at(-1);current.onerror({error});
 assert.equal(run('glasovniUnos'),null);assert.equal(timers.size,0);
 assert(!node('glasovni-nacrt').hidden);
}
// Unsupported engine leaves a working text input and explains optional keyboard dictation.
const unsupported=vm.createContext({Skupine,window:{},localStorage:{getItem:()=>null},
 document:{getElementById:node,addEventListener(){}},setTimeout,clearTimeout});
vm.runInContext(source+'\nfunction prikazi() {}',unsupported);
vm.runInContext('pokreniSlusanje()',unsupported);
assert(node('unos').focused);assert.match(node('glasovni-nacrt').textContent,/tipkovnice/);
vm.runInContext('dodajIzTeksta(razdvojiGlasovniPopis("kruh mlijeko crno vino").join(", "))',unsupported);
assert.equal(vm.runInContext('stanje.popis.length',unsupported),3);
console.log('VOICE FAILURE PASS: start/audio/result watchdogs, late callbacks, missing end, bounded retries, error reasons, unsupported fallback');

// Several normal audio pauses keep the user-controlled session open.
run('pokreniSlusanje()');
for(let pause=0;pause<4;pause++) {
 current=instances.at(-1);current.onaudiostart();current.onerror({error:'no-speech'});current.onend();
 assert.notEqual(run('glasovniUnos'),null);
 const resume=[...timers.values()][0];timers.clear();resume();
}
current=instances.at(-1);current.result('rajčica');run('pokreniSlusanje()');current.onend();
assert.equal(run('stanje.popis.at(-1).naziv'),'Rajčica');assert.equal(timers.size,0);
console.log('PAUSE PASS: silence and repeated normal audio pauses never submit or erase the list');
