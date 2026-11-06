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

  if (korak('popis')) {
    console.log('Popis i rezultati (cijela Hrvatska)');
    await s.click('nav [data-idi="popis"]');
    if (await s.locator('[data-akcija="otkljucaj"]').count()) await s.click('[data-akcija="otkljucaj"]');
    if (await s.locator('[data-akcija="isprazni"]').count()) { s.once('dialog', (d) => d.accept()); await s.click('[data-akcija="isprazni"]'); await s.waitForTimeout(200); }
    await s.waitForSelector('#upisPolje');
    const POPIS = 'kruh, mlijeko, deset jaja, kilu krumpira, banane, kava, šećer, ulje, sir, jogurt, piletina, toaletni papir, riža, špageti, voda';
    await s.fill('#upisPolje', POPIS);
    await s.press('#upisPolje', 'Enter');
    await s.waitForSelector('.stavka');
    const stavke = await s.locator('.stavka').allInnerTexts();
    provjeri(stavke.length === 15, `15 stavki iz jedne rečenice (${stavke.length})`);
    console.log('  ' + stavke.map((x) => x.replace(/\n+/g, ' ')).join('\n  '));
    await snimi('popis-1');
    await s.click('[data-akcija="zakljucaj"]');
    await s.waitForSelector('.sazetak, #karuselB', { timeout: 30000 });
    await s.click('[data-tab="A"]');
    await s.waitForSelector('.ponuda');
    const ponude = await s.locator('.ponuda').allInnerTexts();
    console.log('  A – najjeftinije po stavci:');
    for (const p of ponude) console.log('   • ' + p.replace(/\n+/g, ' | ').slice(0, 170));
    await snimi('popis-2-a');
    await s.click('[data-tab="B"]');
    await s.waitForSelector('.sazetak, #karuselB');
    console.log('  B: ' + (await s.locator('#karuselB .u-fokusu').innerText()).replace(/\n+/g, ' | ').slice(0, 200));
    await s.click('[data-tab="C"]');
    await s.waitForSelector('.sazetak, #karuselB');
    console.log('  C: ' + (await s.locator('.sazetak').innerText()).replace(/\n+/g, ' | ').slice(0, 200));
  }

  if (korak('trgovine')) {
    console.log('Odabir trgovina (samo Konzum i Lidl)');
    await s.click('nav [data-idi="vise"]');
    await s.click('[data-idi="trgovine"]');
    await s.click('[data-akcija="lanci-nijedan"]');
    await s.check('input[data-lanac="konzum"]');
    await s.check('input[data-lanac="lidl"]');
    await s.click('nav [data-idi="rezultati"]');
    await s.waitForSelector('.sazetak, #karuselB', { timeout: 30000 });
    for (const tab of ['A', 'B', 'C']) {
      await s.click(`[data-tab="${tab}"]`);
      await s.waitForSelector('.sazetak, #karuselB');
      const tekst = await s.locator('.zaslon').innerText();
      const drugi = ['Plodine', 'Kaufland', 'Spar', 'Tommy', 'Studenac', 'Eurospin', 'Žabac', 'Trgovina Krk', 'Interspar', 'NTL', 'KTC', 'dm']
        .filter((n) => new RegExp(`(^|\\n)${n}(\\n| |$)`).test(tekst));
      provjeri(/Konzum|Lidl/.test(tekst) && drugi.length === 0, `${tab}: samo Konzum i Lidl${drugi.length ? ' – pojavljuje se i: ' + drugi.join(', ') : ''}`);
    }
    provjeri(/2 od \d+ lanaca/.test(await s.locator('.zaslon').innerText()), 'rezultati pokazuju „2 od N lanaca”');
    await snimi('trgovine-c');
    await s.click('nav [data-idi="vise"]');
    await s.click('[data-idi="trgovine"]');
    await s.click('[data-akcija="lanci-svi"]');
  }

  if (korak('dodatno')) {
    console.log('Dodatni zasloni');
    // ušteda
    await s.click('nav [data-idi="rezultati"]');
    await s.waitForSelector('.sazetak, #karuselB', { timeout: 30000 });
    const prije = await s.locator('#ustedaIznos').innerText();
    if (await s.locator('[data-akcija="kupljeno"]').count()) await s.click('[data-akcija="kupljeno"]');
    await s.waitForTimeout(300);
    provjeri(await s.locator('#ustedaIznos').innerText() !== prije, `ušteda: ${prije} → ${await s.locator('#ustedaIznos').innerText()}`);
    // akcije
    t = t0();
    await s.click('nav [data-idi="akcije"]');
    await s.waitForSelector('.akcija, .prazno', { timeout: 30000 });
    const n = await s.locator('.akcija').count();
    provjeri(n > 0, `akcije: ${n} prikazano za ${((Date.now() - t) / 1000).toFixed(1)} s`);
    await snimi('akcije');
    // skener: stvarni barkod
    await s.click('nav [data-idi="vise"]');
    await s.click('[data-idi="skener"]');
    await s.waitForSelector('#barkodPolje, input[inputmode="numeric"]');
    await s.fill('#barkodPolje, input[inputmode="numeric"]', '5449000000286');
    await s.keyboard.press('Enter');
    await s.waitForSelector('.ploca-sadrzaj .tablica', { timeout: 5000 }).catch(() => {});
    const skener = await s.locator('body').innerText();
    provjeri(/Coca/i.test(skener), 'skener: barkod 5449000000286 → ' + ((skener.match(/Coca[^\n]*/i) || ['-'])[0]));
    provjeri(await s.locator('.ploca-sadrzaj [data-akcija="prijavi"]').count() === 1, 'gumb „Prijavi pogrešnu cijenu” u detaljima proizvoda');
    await snimi('skener');
    await s.click('.ploca-pozadina', { position: { x: 10, y: 10 } });
    // obiteljski popis i dijeljenje
    await s.click('nav [data-idi="vise"]');
    await s.click('[data-idi="obitelj"]');
    await s.waitForTimeout(300);
    const obitelj = await s.locator('.zaslon').innerText();
    provjeri(/#popis=|poveznic/i.test(obitelj) || await s.locator('[data-akcija*="dijeli"], [data-akcija*="posalji"]').count() > 0, 'obiteljski popis: poveznica za dijeljenje');
    await snimi('obitelj');
  }

  if (korak('lokacija')) {
    console.log('Lokacija (jedan gumb na glavnom zaslonu)');
    await s.click('nav [data-idi="popis"]');
    if (await s.locator('[data-akcija="otkljucaj"]').count()) await s.click('[data-akcija="otkljucaj"]');
    if (await s.locator('[data-akcija="isprazni"]').count()) { s.once('dialog', (d) => d.accept()); await s.click('[data-akcija="isprazni"]'); await s.waitForTimeout(200); }
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
    await s.waitForSelector('.sazetak, #karuselB', { timeout: 30000 });
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
