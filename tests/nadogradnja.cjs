// Nova verzija aplikacije mora stići na mobitel bez zatvaranja kartice – i kad su DVIJE nadogradnje u istoj kartici
// (prije: nakon prve nadogradnje druga je čekala zatvaranje kartice; vlasnik je 6.11.2026. vidio staru verziju).
//   node tests/nadogradnja.cjs [mapa-aplikacije]
// Radi na privremenoj kopiji aplikacije: mijenja verziju u sw.js i greske.js kao da je objavljena nova verzija.
const { chromium, devices } = require('playwright');
const http = require('http');
const fs = require('fs');
const os = require('os');
const path = require('path');

const IZVOR = path.resolve(process.argv[2] || path.join(__dirname, '..', 'app'));
const KORIJEN = fs.mkdtempSync(path.join(os.tmpdir(), 'kosarica-nadogradnja-'));
fs.cpSync(IZVOR, KORIJEN, { recursive: true });
const VRSTE = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.webmanifest': 'application/manifest+json' };

let greska = 0;
const provjeri = (uvjet, opis) => { console.log(`  ${uvjet ? '✓' : '✗'} ${opis}`); if (!uvjet) greska = 1; };

function objaviVerziju(v) {
  for (const [f, re] of [['sw.js', /const VERZIJA = '[^']+'/], ['js/greske.js', /VERZIJA_APLIKACIJE = '[^']+'/]]) {
    const p = path.join(KORIJEN, f);
    fs.writeFileSync(p, fs.readFileSync(p, 'utf8').replace(re, (m) => m.replace(/'[^']+'/, `'${v}'`)));
  }
}

const srv = http.createServer((req, res) => {
  let p = decodeURIComponent(new URL(req.url, 'http://x').pathname);
  if (p.endsWith('/')) p += 'index.html';
  const f = path.join(KORIJEN, p);
  if (!f.startsWith(KORIJEN) || !fs.existsSync(f)) { res.writeHead(404); res.end(); return; }
  res.writeHead(200, { 'content-type': VRSTE[path.extname(f)] || 'application/octet-stream', 'cache-control': 'max-age=600' });
  fs.createReadStream(f).pipe(res);
});

srv.listen(0, '127.0.0.1', async () => {
  const url = `http://127.0.0.1:${srv.address().port}/`;
  const preglednik = await chromium.launch();
  try {
    const k = await preglednik.newContext({ ...devices['Pixel 7'], locale: 'hr-HR' });
    const s = await k.newPage();
    const verzija = () => s.evaluate(() => import('./js/greske.js').then((m) => m.VERZIJA_APLIKACIJE));
    const procitaj = async () => { await s.click('nav [data-idi="vise"]'); await s.waitForSelector('.izbor'); return (await s.locator('.zaslon').innerText()).match(/Verzija aplikacije ([\d.]+)/)[1]; };

    console.log('Nadogradnja aplikacije na mobitelu');
    objaviVerziju('9.0.0');
    await s.goto(url);
    await s.waitForSelector('#upisPolje');
    await s.waitForFunction(() => navigator.serviceWorker.controller, null, { timeout: 20000 });
    provjeri(await procitaj() === '9.0.0', 'početna verzija 9.0.0 radi preko service workera');

    for (const nova of ['9.0.1', '9.0.2']) {
      objaviVerziju(nova);
      const ucitano = s.waitForEvent('load', { timeout: 30000 });
      await s.evaluate(() => navigator.serviceWorker.getRegistration().then((r) => r.update()));
      await ucitano;                                            // aplikacija se sama osvježi
      await s.waitForSelector('nav [data-idi="vise"]');
      provjeri(await procitaj() === nova, `nova verzija ${nova} stigla u istu otvorenu karticu bez zatvaranja`);
    }
    provjeri(await verzija() === '9.0.2', 'učitani kod je najnoviji');
  } catch (e) {
    console.error(e);
    greska = 1;
  } finally {
    await preglednik.close();
    srv.close();
    fs.rmSync(KORIJEN, { recursive: true, force: true });
  }
  console.log(greska ? 'NADOGRADNJA NIJE PROŠLA' : 'NADOGRADNJA RADI');
  process.exit(greska);
});
