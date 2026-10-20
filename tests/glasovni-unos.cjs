const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const nodes = new Map(), instances = [], saved = [];
function node(id) {
 if (!nodes.has(id)) nodes.set(id, {hidden:true,textContent:'',classList:{add(){},remove(){}},setAttribute(){},focus(){this.focused=true;}});
 return nodes.get(id);
}
class Speech {
 constructor(){instances.push(this);}
 start(){this.started=true;}
 stop(){this.stopped=true;this.onend();}
 result(text){this.onresult({results:[[{transcript:text}]]});}
}
let source = fs.readFileSync(require('node:path').join(__dirname,'../site/aplikacija.js'),'utf8');
source = source.slice(0,source.indexOf('// ---------- Prikaz ----------'));
const context = vm.createContext({window:{SpeechRecognition:Speech},localStorage:{getItem:()=>null,setItem:(k,v)=>saved.push(JSON.parse(v))},document:{getElementById:node},setTimeout(){throw Error('single-item input must not schedule retries');}});
vm.runInContext(source+'\nfunction prikazi() {}',context);
const run=s=>vm.runInContext(s,context);
run('pokreniSlusanje()');
let current=instances.at(-1);
assert(current.started);assert.equal(current.lang,'hr-HR');assert.equal(current.continuous,false);assert.equal(current.interimResults,false);
current.result('mlijeko');
assert.deepEqual(Array.from(run('stanje.popis.map(x=>x.naziv)')),['Mlijeko'],'result is saved immediately, before end or a second click');
assert.equal(saved.at(-1).popis[0].naziv,'Mlijeko');
current.result('mlijeko');assert.equal(run('stanje.popis.length'),1,'duplicate result must not be added');
current.onend();assert.equal(run('slusac'),null);assert.equal(instances.length,1,'end never restarts');
run('pokreniSlusanje()');const second=instances.at(-1);current.result('zakašnjeli');
second.result('sok od naranče');second.onend();
assert.deepEqual(Array.from(run('stanje.popis.map(x=>x.naziv)')),['Mlijeko','Sok od naranče']);
run('pokreniSlusanje()');current=instances.at(-1);current.onend();
assert.equal(run('slusac'),null);assert.match(node('glasovni-nacrt').textContent,/Nije prepoznat/);assert.equal(instances.length,3);
for(const error of ['not-allowed','audio-capture','network','no-speech']){
 run('pokreniSlusanje()');current=instances.at(-1);current.onerror({error});current.onend();
 assert.equal(run('slusac'),null);assert(!node('glasovni-nacrt').hidden);assert.equal(run('stanje.popis.length'),2);
}
run('pokreniSlusanje(); pokreniSlusanje()');assert(instances.at(-1).stopped);assert.equal(run('slusac'),null);
Speech.prototype.start=function(){throw Error('unavailable');};
run('pokreniSlusanje()');assert.equal(run('slusac'),null);assert.match(node('glasovni-nacrt').textContent,/nije dostupan/);
const unsupported=vm.createContext({window:{},localStorage:{getItem:()=>null},document:{getElementById:node}});
vm.runInContext(source+'\nfunction prikazi() {}\npokreniSlusanje()',unsupported);
assert(node('unos').focused);assert.match(node('glasovni-nacrt').textContent,/ne podržava/);
console.log('VOICE PASS: one press per item, immediate persistence, repeated items, multiword name, no retries, stale callbacks, errors, stop, unsupported browser');
