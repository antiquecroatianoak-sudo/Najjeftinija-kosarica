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
    console.log('Lokacija (jedan gumb na glavnom zaslonu)');
    await s.click('nav [data-idi="popis"]');
    await s.waitForSelector('#upisPolje');
    await s.fill('#upisPolje', 'mlijeko, kruh, jaja, banane, kava');
    await s.press('#upisPolje', 'Enter');
    await s.waitForSelector('.stavka');
    provjeri(await s.locator('.lokacija-gumb').count() === 1, 'gumb lokacije na glavnom zaslonu');
    t = t0();
    await s.click('.lokacija-gumb');
    await s.waitForSelector('.lok-krug:not([disabled])', { timeout: 25000 });
    const krugovi = await s.locator('.lok-krug').allInnerTexts();
    console.log('  krugovi: ' + krugovi.map((x) => x.replace(/\n/g, ' ')).join(' | '));
    await s.waitForTimeout(400);
    await snimi('lok-1-ploca');
    await s.click('.lok-krug[data-r="5"]');
    await s.waitForTimeout(300);
    const gumb = await s.locator('.lokacija-gumb').innerText();
    provjeri(await s.locator('#ploca').isHidden() && /U krugu 5 km · \d+/.test(gumb) && await s.locator('#upisPolje').count() === 1,
      `natrag na popis za ${((Date.now() - t) / 1000).toFixed(1)} s: ${gumb.split('\n')[0]}`);
    await snimi('lok-2-popis');
    await s.click('[data-akcija="zakljucaj"]');
    t = t0();
    await s.waitForSelector('.sazetak', { timeout: 30000 });
    const rez = await s.locator('.zaslon').innerText();
    provjeri(/U krugu 5 km: \d+ poslovnic/.test(rez), `rezultati za ${((Date.now() - t) / 1000).toFixed(1)} s: ${(rez.match(/U krugu 5 km: [^\n]*/) || [''])[0]}`);
    await snimi('lok-3-rezultati');
    await s.click('nav [data-idi="karta"]');
    await s.waitForSelector('#karta');
    provjeri(/u krugu 5 km/.test(await s.locator('.naslov-zaslona').innerText()), 'karta: ' + (await s.locator('.naslov-zaslona').innerText()).replace(/\n/g, ' '));
    await snimi('lok-4-karta');
  }

  provjeri(greske.length === 0, 'nema JavaScript grešaka' + (greske.length ? ': ' + greske.slice(0, 3).join(' ; ') : ''));
  await preglednik.close();
  srv.close();
  console.log(neuspjeha ? `NEUSPJELO: ${neuspjeha}` : 'SVE PROVJERE SU PROŠLE');
  process.exit(neuspjeha ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
