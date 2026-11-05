// Provjera cijele aplikacije u pregledniku (Chromium, veličina mobitela).
//   node tests/preglednik.cjs [mapa-aplikacije] [mapa-za-snimke]
// Mapa aplikacije mora imati podatke u data/hr (npr. iz: python uvoz/uvoz.py --arhiva ... --izlaz app/data/hr).
const { chromium, devices } = require('playwright');
const http = require('http');
const fs = require('fs');
const path = require('path');

const KORIJEN = path.resolve(process.argv[2] || path.join(__dirname, '..', 'app'));
const SNIMKE = process.argv[3] ? path.resolve(process.argv[3]) : null;
const VRSTE = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.webmanifest': 'application/manifest+json' };

let bezMreze = false;   // simulira prekid veze: poslužitelj ne odgovara (vrijedi i za service worker)
function posluzitelj() {
  return new Promise((ok) => {
    const s = http.createServer((req, res) => {
      if (bezMreze) { req.socket.destroy(); return; }
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

const provjeri = (uvjet, poruka) => { if (!uvjet) throw new Error('NIJE PROŠLO: ' + poruka); console.log('  ✓ ' + poruka); };

(async () => {
  const srv = await posluzitelj();
  const url = `http://127.0.0.1:${srv.address().port}/`;
  const preglednik = await chromium.launch();
  const kontekst = await preglednik.newContext({ ...devices['Pixel 7'], locale: 'hr-HR', geolocation: { latitude: 45.8130, longitude: 15.9770 }, permissions: ['geolocation'] });
  await kontekst.route(/tile\.openstreetmap\.org/, (r) => r.abort());
  const s = await kontekst.newPage();
  const greske = [];
  s.on('pageerror', (e) => greske.push('pageerror: ' + e.message));
  s.on('console', (m) => { if (m.type() === 'error' && !/tile\.openstreetmap|ERR_FAILED|net::/.test(m.text())) greske.push('console: ' + m.text()); });
  const snimi = async (ime) => { if (SNIMKE) { fs.mkdirSync(SNIMKE, { recursive: true }); await s.screenshot({ path: path.join(SNIMKE, ime + '.png'), fullPage: false }); } };

  console.log('Popis');
  await s.goto(url);
  await s.waitForSelector('#upisPolje');
  provjeri(await s.locator('.mikrofon').count() === 1, 'gumb za glasovni unos postoji');
  await snimi('1-pocetna');
  await s.fill('#upisPolje', 'kruh, dvije litre mlijeka, jaja, pola kile krumpira, kava, banane');
  await s.press('#upisPolje', 'Enter');
  await s.waitForSelector('.stavka');
  provjeri(await s.locator('.stavka').count() === 6, '6 stavki iz jedne rečenice');
  const tekst = await s.locator('.stavke').innerText();
  provjeri(/2 l/.test(tekst) && /500 g/.test(tekst) && /0,5 kg/.test(tekst), 'količine: 2 l, kruh zadano 500 g, krumpir 0,5 kg');
  provjeri(/zadano/.test(tekst), 'zadana količina je označena');
  await s.click('.stavka [data-akcija="vise"] >> nth=0');
  provjeri(/1 kg|1000 g|600 g/.test(await s.locator('.stavka >> nth=0').innerText()), 'gumb + povećava količinu');
  await snimi('2-popis');

  console.log('Glasovni unos (simulirano prepoznavanje govora)');
  {
    const kg = await preglednik.newContext({ ...devices['Pixel 7'], locale: 'hr-HR' });
    const sg = await kg.newPage();
    sg.on('pageerror', (e) => greske.push('pageerror (glas): ' + e.message));
    await sg.addInitScript(() => {
      // lažni SpeechRecognition: "čuje" rečenicu s greškom prepoznavanja ("mljeko") kao Chrome na Androidu
      window.SpeechRecognition = class {
        start() {
          setTimeout(() => this.onresult && this.onresult({ resultIndex: 0, results: [Object.assign([{ transcript: 'kruh, mljeko i deset jaja' }], { isFinal: true })] }), 150);
          setTimeout(() => this.onend && this.onend(), 300);
        }
        stop() { this.onend && this.onend(); }
        abort() {}
      };
    });
    await sg.goto(url);
    await sg.waitForSelector('#mikrofon');
    await sg.click('#mikrofon');
    await sg.waitForSelector('.stavka', { timeout: 5000 });
    const glasStavke = await sg.locator('.stavka').allInnerTexts();
    provjeri(glasStavke.length === 3 && /Mlijeko/.test(glasStavke[1]) && /1 l/.test(glasStavke[1]) && /10 kom/.test(glasStavke[2]),
      'glas: „kruh, mljeko i deset jaja” → Kruh, Mlijeko 1 l, Jaja 10 kom');
    provjeri(/Razumio sam/.test(await sg.locator('#stanjeGlasa').innerText()), 'glas: prikazano što je aplikacija čula');
    await kg.close();
  }

  console.log('Novo: prijedlozi, često kupuješ, kvačica u košarici');
  await s.fill('#upisPolje', 'mli');
  await s.dispatchEvent('#upisPolje', 'input');
  await s.waitForSelector('.prijedlog', { timeout: 3000 });
  const prijedlozi = await s.locator('.prijedlog').allInnerTexts();
  provjeri(prijedlozi.some((x) => /Mlijeko/.test(x)), 'prijedlozi dok tipkaš: „mli” → ' + prijedlozi.slice(0, 3).map((x) => x.replace(/\n/g, ' ')).join(' | '));
  const prije = await s.locator('.stavka').count();
  await s.click('.prijedlog >> nth=0');
  await s.waitForTimeout(200);
  provjeri(await s.locator('.stavka').count() >= prije, 'dodir na prijedlog dodaje stavku');
  provjeri(/Često kupuješ/i.test(await s.locator('.brze-naslov').innerText()), 'naslov „Često kupuješ” nakon prvih stavki');
  const prvaBrza = await s.locator('.cipovi.vodoravno .cip >> nth=0').innerText();
  await s.click('[data-akcija="u-kosaru"] >> nth=0');
  await s.waitForTimeout(200);
  const nakonKvacice = await s.locator('.zaslon').innerText();
  const zadnja = await s.locator('.stavka').last().getAttribute('class');
  provjeri(/1 od \d+ u košarici/i.test(nakonKvacice) && /u-kosari/.test(zadnja), 'kvačica: „1 od N u košarici”, stavka ide na dno');
  await s.click('.u-kosari [data-akcija="u-kosaru"]');
  await s.waitForTimeout(200);
  provjeri(!/od \d+ u košarici/i.test(await s.locator('.zaslon').innerText()), 'kvačica se može maknuti (' + prvaBrza.replace(/\n/g, ' ') + ')');
  await snimi('2b-popis-novo');

  console.log('Rezultati');
  await s.click('[data-akcija="zakljucaj"]');
  await s.waitForSelector('.sazetak');
  provjeri(/€/.test(await s.locator('.sazetak .iznos').innerText()), 'B: ukupna cijena za jednu trgovinu');
  provjeri(await s.locator('.trgovina-red').count() >= 3, 'B: poredak trgovina');
  await snimi('3-rezultat-b');
  await s.click('[data-tab="A"]');
  await s.waitForSelector('.sazetak');
  provjeri(await s.locator('.ponuda').count() === 6, 'A: ponuda za svaku stavku');
  const prvaPrije = await s.locator('.ponuda-naziv >> nth=0').innerText();
  const detalji = await s.locator('.ponuda >> nth=0').innerText();
  provjeri(/€\/(kg|l|kom)/.test(detalji) || /količina nije objavljena/.test(detalji), 'A: prikazana jedinična cijena ili napomena o količini');
  await snimi('4-rezultat-a');
  await s.click('.ponuda-gumb >> nth=0');
  await s.waitForTimeout(300);
  const prvaPoslije = await s.locator('.ponuda-naziv >> nth=0').innerText();
  provjeri(prvaPrije !== prvaPoslije, `zamjena: „${prvaPrije}” → „${prvaPoslije}”`);
  await s.click('#poruka button');
  await s.waitForTimeout(300);
  provjeri(await s.locator('.ponuda-naziv >> nth=0').innerText() === prvaPrije, 'zamjena se može vratiti');
  await s.click('[data-tab="C"]');
  await s.waitForSelector('.sazetak');
  provjeri(/\+/.test(await s.locator('.sazetak .gdje').innerText()), 'C: dvije trgovine');
  await snimi('5-rezultat-c');
  await s.click('[data-akcija="kupljeno"]');
  await s.waitForTimeout(200);
  provjeri(await s.locator('#ustedaIznos').innerText() !== '', 'ušteda je zabilježena u zaglavlju');
  await s.click('.ikona-gumb[data-akcija="proizvod"] >> nth=0');
  await s.waitForSelector('.ploca-sadrzaj .tablica');
  provjeri(await s.locator('.ploca-sadrzaj [data-akcija="prijavi"]').count() === 1, 'detalji proizvoda i gumb „Prijavi pogrešnu cijenu”');
  await snimi('6-proizvod');
  await s.click('.ploca-sadrzaj [data-akcija="favorit"]');
  await s.waitForTimeout(150);
  provjeri(/U favoritima/.test(await s.locator('.ploca-sadrzaj [data-akcija="favorit"]').innerText()), 'favorit: „☆ Prati cijenu” → „★ U favoritima”');
  await s.click('.ploca-pozadina', { position: { x: 10, y: 10 } });

  console.log('Lokacija: jedan gumb na glavnom zaslonu');
  await s.click('nav [data-idi="popis"]');
  await s.waitForSelector('.lokacija-gumb');
  provjeri(/Cijela Hrvatska/.test(await s.locator('.lokacija-gumb').innerText()), 'gumb lokacije na glavnom zaslonu (bez lokacije: cijela HR)');
  await s.click('.lokacija-gumb');
  await s.waitForSelector('.lok-ploca');
  await s.waitForSelector('.lok-krug:not([disabled])', { timeout: 25000 });
  const krugovi = await s.locator('.lok-krug').allInnerTexts();
  provjeri(krugovi.length === 4 && krugovi.every((x) => /km/.test(x) && /trgovin/.test(x)), 'jedan dodir: lokacija pronađena, krugovi 2/5/10/20 km s brojem trgovina');
  await snimi('7a-lokacija-ploca');
  await s.click('.lok-krug[data-r="10"]');
  await s.waitForTimeout(300);
  provjeri(await s.locator('#ploca').isHidden(), 'nakon odabira kruga ploča se zatvara');
  const gumbTekst = await s.locator('.lokacija-gumb').innerText();
  const brojUKrugu = Number((gumbTekst.match(/U krugu 10 km · (\d+) trgovin/) || [])[1] || 0);
  provjeri(brojUKrugu > 0 && await s.locator('.stavke').count() === 1, `odmah natrag na popis; gumb pokazuje krug i broj trgovina (${brojUKrugu})`);
  await snimi('7b-popis-krug');
  await s.click('nav [data-idi="karta"]');
  await s.waitForSelector('#karta');
  provjeri(/u krugu 10 km/i.test(await s.locator('.naslov-zaslona').innerText()), 'karta prikazuje isti krug');
  await snimi('7-karta');
  await s.click('nav [data-idi="rezultati"]');
  await s.waitForSelector('.sazetak, .prazno', { timeout: 20000 });
  const rezKrug = await s.locator('.zaslon').innerText();
  const brojPoslovnica = Number((rezKrug.match(/U krugu 10 km: (\d+) poslovnic/) || [])[1] || 0);
  provjeri(brojPoslovnica > 0 && brojPoslovnica === brojUKrugu, `rezultati koriste iste poslovnice u krugu (${brojPoslovnica})`);
  await snimi('8-rezultat-krug');

  console.log('Akcije i Više');
  await s.click('nav [data-idi="akcije"]');
  await s.waitForSelector('.akcija, .prazno');
  provjeri(await s.locator('.akcija').count() > 0, 'akcije se prikazuju');
  await snimi('9-akcije');
  await s.click('nav [data-idi="vise"]');
  await s.click('[data-idi="favoriti"]');
  await s.waitForSelector('.naslov-zaslona');
  provjeri(await s.locator('.zaslon .akcija').count() === 1, 'Više → Moji favoriti: 1 proizvod s cijenom');
  await s.click('nav [data-idi="vise"]');
  await s.click('[data-idi="status"]');
  await s.waitForSelector('.tablica');
  provjeri(await s.locator('.tablica >> nth=1').locator('tr').count() > 3, 'status podataka po trgovini');
  await snimi('10-status');
  await s.click('[data-idi="vise"]');
  await s.click('[data-idi="greska"]');
  provjeri(/Izvješće o grešci/.test(await s.locator('#izvjesceTekst').inputValue()), 'izvješće o grešci za Claude Code');
  await s.click('[data-idi="vise"]');
  await s.click('[data-idi="obitelj"]');
  await s.click('[data-akcija="podijeli-popis"]');
  const poveznica = await s.locator('.ploca-sadrzaj textarea').inputValue();
  provjeri(/#popis=/.test(poveznica), 'poveznica obiteljskog popisa');
  provjeri(await s.locator('.ploca-sadrzaj a[href^="https://wa.me"]').count() === 1 && await s.locator('.ploca-sadrzaj a[href^="viber://"]').count() === 1, 'slanje preko WhatsAppa i Vibera');

  console.log('Obiteljski popis na drugom mobitelu');
  const drugi = await preglednik.newContext({ ...devices['Pixel 7'], locale: 'hr-HR' });
  const s2 = await drugi.newPage();
  s2.on('pageerror', (e) => greske.push('pageerror(2): ' + e.message));
  await s2.goto(url + '#popis=' + poveznica.split('#popis=')[1].trim());
  await s2.waitForSelector('[data-akcija="uvoz-dodaj"]');
  await s2.click('[data-akcija="uvoz-dodaj"]');
  await s2.waitForSelector('.stavka');
  provjeri(await s2.locator('.stavka').count() === 6, 'primljeni popis ima 6 stavki');

  console.log('Skener (ručni unos barkoda)');
  await s.goto(url);
  await s.waitForSelector('.izbornik');
  await s.click('nav [data-idi="vise"]');
  await s.click('[data-idi="skener"]');
  const barkod = await s.evaluate(async () => { const r = await fetch('data/hr/proizvodi.json'); const d = await r.json(); return d.p.find((p) => p[6])[6]; });
  await s.fill('#barkodPolje', barkod);
  await s.click('#barkodForma button');
  await s.waitForSelector('.ploca-sadrzaj .tablica');
  provjeri(true, `barkod ${barkod} pronađen`);

  console.log('Bez interneta (zadnji dobri podaci)');
  // offline radi nakon što je aplikacija jednom otvorena s aktivnim service workerom i spremila cijene
  const spremljeno = () => s.evaluate(async () => {
    const c = await caches.open('kosarica-podaci');
    return !!(await c.match(new URL('data/hr/meta.json', location.href).href)) && !!(await c.match(new URL('data/hr/proizvodi.json', location.href).href));
  });
  for (let i = 0; i < 20 && !(await spremljeno()); i++) {
    await s.waitForTimeout(500);
    if (i === 6) { await s.reload(); await s.waitForSelector('.izbornik'); }
  }
  provjeri(await spremljeno(), 'cijene su spremljene za rad bez interneta');
  bezMreze = true;
  await s.reload();
  await s.waitForSelector('.izbornik');
  await s.waitForSelector('#obavijest:not([hidden]), .sadrzaj .zaslon', { timeout: 30000 });
  await s.waitForTimeout(300);
  const ob = await s.locator('#obavijest').innerText().catch(() => '');
  provjeri(/spremljene cijene/.test(ob), 'bez interneta prikazuju se spremljene cijene' + (/spremljene/.test(ob) ? '' : ` (obavijest: "${ob}", sadržaj: "${(await s.locator('#sadrzaj').innerText()).slice(0, 200)}")`));
  bezMreze = false;

  console.log('Širine zaslona');
  for (const w of [320, 768]) {
    await s.setViewportSize({ width: w, height: 800 });
    const siroko = await s.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
    provjeri(!siroko, `bez vodoravnog pomicanja na ${w}px`);
  }

  console.log('Lokacija: odbijeno dopuštenje i spora veza (zaslon se ne smije zaglaviti)');
  {
    const k2 = await preglednik.newContext({ ...devices['Pixel 7'], locale: 'hr-HR' });
    await k2.route(/tile\.openstreetmap\.org/, (r) => r.abort());
    const s2 = await k2.newPage();
    s2.on('pageerror', (e) => greske.push('pageerror (odbijeno): ' + e.message));
    await s2.addInitScript(() => {
      navigator.geolocation.getCurrentPosition = (ok, ne) => setTimeout(() => ne({ code: 1, message: 'denied' }), 200);
    });
    await s2.goto(url);
    await s2.waitForSelector('.lokacija-gumb');
    await s2.click('.lokacija-gumb');
    await s2.waitForSelector('.lok-stanje.upozorenje', { timeout: 5000 });
    provjeri(/nije dopuštena/.test(await s2.locator('.lok-stanje').innerText()), 'odbijena lokacija: jasna poruka kako je dopustiti');
    await s2.click('[data-akcija="lok-iskljuci"]');
    await s2.waitForTimeout(200);
    provjeri(await s2.locator('#ploca').isHidden() && /Cijela Hrvatska/.test(await s2.locator('.lokacija-gumb').innerText()), 'bez lokacije aplikacija radi dalje (cijela HR)');
    await k2.close();

    // serviceWorkers: 'block' – inače service worker sam dohvaća datoteke i zaobilazi simulaciju spore veze
    const k3 = await preglednik.newContext({ ...devices['Pixel 7'], locale: 'hr-HR', serviceWorkers: 'block', geolocation: { latitude: 45.8130, longitude: 15.9770 }, permissions: ['geolocation'] });
    await k3.route(/tile\.openstreetmap\.org/, (r) => r.abort());
    await k3.route(/\/data\/hr\/s\//, async (r) => { await new Promise((z) => setTimeout(z, 60000)); try { await r.continue(); } catch { /* prekinuto */ } });
    const s3 = await k3.newPage();
    s3.on('pageerror', (e) => greske.push('pageerror (spora veza): ' + e.message));
    await s3.goto(url);
    await s3.waitForSelector('#upisPolje');
    await s3.fill('#upisPolje', 'kruh, mlijeko');
    await s3.press('#upisPolje', 'Enter');
    await s3.click('.lokacija-gumb');
    await s3.waitForSelector('.lok-krug:not([disabled])', { timeout: 25000 });
    await s3.click('.lok-krug[data-r="20"]');
    await s3.click('[data-akcija="zakljucaj"]');
    const t0 = Date.now();
    await s3.waitForSelector('.sazetak', { timeout: 25000 });
    const sek = (Date.now() - t0) / 1000;
    provjeri(sek > 10 && sek < 20, `spora veza: rezultati za ${sek.toFixed(1)} s (rok 15 s), zaslon se ne zaglavi`);
    provjeri(/nisu se učitale na vrijeme/.test(await s3.locator('.zaslon').innerText()) && await s3.locator('[data-akcija="ponovno-poslovnice"]').count() === 1, 'spora veza: umjesto praznog zaslona cijene lanaca, jasno objašnjenje i „Pokušaj ponovno”');
    await k3.close();
  }

  provjeri(greske.length === 0, 'nema JavaScript grešaka' + (greske.length ? ':\n' + greske.join('\n') : ''));
  await preglednik.close();
  srv.close();
  console.log('SVE PROVJERE SU PROŠLE');
})().catch((e) => { console.error(e); process.exit(1); });
