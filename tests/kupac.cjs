// Provjera "kao kupac" sa STVARNIM podacima (cijeli objavljeni data/hr), veličina mobitela, lokacija Zagreb.
//   node tests/kupac.cjs <mapa-aplikacije-sa-stvarnim-podacima> [mapa-za-snimke] [korak...]
// Koraci: status, lokacija (zadano: svi). Mjeri vrijeme i javlja ako se zaslon "zaglavi".
const { chromium, devices } = require('playwright');
const http = require('http');
const fs = require('fs');
const path = require('path');

const KORIJEN = path.resolve(process.argv[2]);
const SNIMKE = process.argv[3] ? path.resolve(process.argv[3]) : null;
const KORACI = process.argv.slice(4);
const VRSTE = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.webmanifest': 'application/manifest+json' };

function posluzitelj() {
  return new Promise((ok) => {
    const s = http.createServer((req, res) => {
      let p = decodeURIComponent(new URL(req.url, 'http://x').pathname);
      if (p.endsWith('/')) p += 'index.html';
      const f = path.join(KORIJEN, p);
      if (!f.startsWith(KORIJEN) || !fs.existsSync(f)) { res.writeHead(404); res.end('nema'); return; }
      res.writeHead(200, { 'content-type': VRSTE[path.extname(f)] || 'application/octet-stream' });
      fs.createReadStream(f).pipe(res);
    });
    s.listen(0, '127.0.0.1', () => ok(s));
  });
}

let neuspjeha = 0;
const provjeri = (uvjet, poruka) => { console.log(`  ${uvjet ? '✓' : '✗'} ${poruka}`); if (!uvjet) neuspjeha++; };
const t0 = () => Date.now();

(async () => {
  const srv = await posluzitelj();
  const url = `http://127.0.0.1:${srv.address().port}/`;
  const preglednik = await chromium.launch();
  const kontekst = await preglednik.newContext({ ...devices['Pixel 7'], locale: 'hr-HR',
    geolocation: { latitude: 45.8131, longitude: 15.9775 }, permissions: ['geolocation'] });
  await kontekst.route(/tile\.openstreetmap\.org/, (r) => r.abort());
  const s = await kontekst.newPage();
  const greske = [];
  s.on('pageerror', (e) => greske.push('pageerror: ' + e.message));
  s.on('console', (m) => { if (m.type() === 'error' && !/tile\.openstreetmap|ERR_FAILED|net::/.test(m.text())) greske.push('console: ' + m.text()); });
  const snimi = async (ime) => { if (SNIMKE) { fs.mkdirSync(SNIMKE, { recursive: true }); await s.screenshot({ path: path.join(SNIMKE, ime + '.png') }); } };
  const korak = (k) => !KORACI.length || KORACI.includes(k);

  let t = t0();
  await s.goto(url);
  await s.waitForSelector('#upisPolje', { timeout: 60000 });
  console.log(`Učitavanje aplikacije sa stvarnim podacima: ${((Date.now() - t) / 1000).toFixed(1)} s`);

  if (korak('status')) {
    console.log('Status podataka');
    await s.click('nav [data-idi="vise"]');
    await s.click('[data-idi="status"]');
    await s.waitForTimeout(500);
    const txt = await s.locator('body').innerText();
    provjeri(/5\. ?11\. ?2026|05\.11\.2026|2026-11-05/.test(txt), 'datum cijena je prikazan');
    provjeri(/Konzum/.test(txt) && /Lidl/.test(txt) && /Studenac/.test(txt), 'lanci su navedeni');
    await snimi('status');
  }

  if (korak('lokacija')) {
    console.log('Lokacija');
    await s.click('nav [data-idi="popis"]');
    await s.waitForSelector('#upisPolje');
    await s.fill('#upisPolje', 'mlijeko, kruh, jaja');
    await s.press('#upisPolje', 'Enter');
    await s.waitForSelector('.stavka');
    await snimi('lok-1-popis');
    const ikona = s.locator('[data-akcija="lokacija"], .lokacija-gumb, [aria-label*="okacij"]');
    console.log('  ikona lokacije na glavnom zaslonu: ' + (await ikona.count()));
    // Trenutačni put: kartica Karta -> 5 km
    t = t0();
    await s.click('nav [data-idi="karta"]');
    await snimi('lok-2-karta');
    const gumb5 = s.locator('[data-akcija="radijus"][data-r="5"]').first();
    if (await gumb5.count()) {
      await gumb5.click();
      let zaglavljeno = false;
      try { await s.waitForFunction(() => /u krugu 5 km/i.test((document.querySelector('.naslov-zaslona') || {}).innerText || ''), null, { timeout: 30000 }); } catch { zaglavljeno = true; }
      console.log(`  5 km: ${((Date.now() - t) / 1000).toFixed(1)} s${zaglavljeno ? ' – NIJE ZAVRŠILO u 30 s' : ''}`);
      await snimi('lok-3-nakon-5km');
      console.log('  tekst zaslona: ' + (await s.locator('body').innerText()).slice(0, 600).replace(/\n+/g, ' | '));
    }
  }

  provjeri(greske.length === 0, 'nema JavaScript grešaka' + (greske.length ? ': ' + greske.slice(0, 3).join(' ; ') : ''));
  await preglednik.close();
  srv.close();
  console.log(neuspjeha ? `NEUSPJELO: ${neuspjeha}` : 'SVE PROVJERE SU PROŠLE');
  process.exit(neuspjeha ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
