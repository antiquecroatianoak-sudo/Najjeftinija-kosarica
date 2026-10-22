// Izolacija offline cachea (pregled #12, 6339806449): aktivacija ove aplikacije briše samo vlastite stare cacheove,
// a offline odgovor dolazi samo iz vlastitog cachea i vlastitog opsega. node tests/sw.cjs
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const assert = require("node:assert/strict");

const SCOPE = "https://antiquecroatianoak-sudo.github.io/Najjeftinija-kosarica/";
function okolina() {
  const spremista = new Map();
  const otvori = (ime) => {
    if (!spremista.has(ime)) spremista.set(ime, new Map());
    const m = spremista.get(ime);
    return { async put(r, odg) { m.set(typeof r === "string" ? r : r.url, odg); }, async addAll() {},
      async match(r, o) { let u = typeof r === "string" ? r : r.url; if (o && o.ignoreSearch) u = u.split("?")[0]; return m.get(u); } };
  };
  const caches = { async keys() { return [...spremista.keys()]; }, async delete(ime) { return spremista.delete(ime); },
    async open(ime) { return otvori(ime); },
    async match(r) { for (const m of spremista.values()) if (m.has(r.url)) return m.get(r.url); } };
  const slusatelji = {};
  const ctx = vm.createContext({ caches, Response: class { constructor(t, o) { this.tekst = t; this.status = o.status; } },
    self: { addEventListener: (ime, f) => { slusatelji[ime] = f; }, registration: { scope: SCOPE },
      skipWaiting() {}, clients: { claim: async () => {} }, location: { origin: "https://antiquecroatianoak-sudo.github.io" } },
    fetch: async () => { throw new Error("offline"); } });
  vm.runInContext(fs.readFileSync(path.join(__dirname, "../site/sw.js"), "utf8"), ctx);
  return { ctx, spremista, slusatelji, otvori };
}

(async () => {
  const { ctx, spremista, slusatelji, otvori } = okolina();
  const CACHE = vm.runInContext("CACHE", ctx);
  await otvori("kosarica-v1").put(SCOPE + "index.html", "stari");
  await otvori("gradjevina-v13").put("https://antiquecroatianoak-sudo.github.io/Najjeftiniji-gradjevinski-materijal/index.html", "tuđi");
  await otvori("gradjevina-v13").put(SCOPE + "samo-tudji.json", "tuđi");
  await otvori("nepovezan-cache").put("https://x.hr/a", "x");
  await otvori(CACHE).put(SCOPE + "index.html", "vlastiti");
  const cekaj = [];
  slusatelji.activate({ waitUntil: (p) => cekaj.push(p) });
  await Promise.all(cekaj);
  assert.deepEqual([...spremista.keys()].sort(), [CACHE, "gradjevina-v13", "nepovezan-cache"].sort(),
    "only this app's old cache is deleted; the other app's and unrelated caches stay");

  const odgovori = async (url) => {
    let p = null;
    slusatelji.fetch({ request: { method: "GET", url }, respondWith: (x) => { p = x; }, waitUntil() {} });
    return p ? await p : "nije presretnuto";
  };
  assert.equal(await odgovori(SCOPE + "index.html?v=2"), "vlastiti", "own offline resource is served from own cache");
  assert.equal((await odgovori(SCOPE + "samo-tudji.json")).status, 503, "never served from another app's cache");
  assert.equal(await odgovori("https://antiquecroatianoak-sudo.github.io/Najjeftiniji-gradjevinski-materijal/index.html"),
    "nije presretnuto", "requests outside this app's scope are not intercepted");
  assert.equal(await odgovori("https://tile.openstreetmap.org/1/1/1.png"), "nije presretnuto");
  console.log("SW PASS: activation deletes only own old kosarica- caches; other app + unrelated caches kept; offline only from own cache and scope");
})().catch((e) => { console.error(e); process.exit(1); });
