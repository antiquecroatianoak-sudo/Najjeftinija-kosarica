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
  const precaci = await s.locator('.plocice.precaci .plocica').allInnerTexts();
  provjeri(precaci.length === 4 && /Akcije/.test(precaci[0]) && /Karta/i.test(precaci[1]), 'prazan popis: 4 šarene pločice (akcije, karta, favoriti, obitelj)');
  const izbornik = await s.locator('nav.izbornik button').allInnerTexts();
  provjeri(izbornik.join('|') === 'Popis|Usporedba|Akcije|Skeniraj|Više', 'donji izbornik: ' + izbornik.join(' · '));
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
  provjeri(await s.locator('.stavka .ukloni-stavku').count() === 6, '× za uklanjanje uz svaku stavku');
  const imeX = (await s.locator('.stavka-naziv >> nth=1').innerText()).trim();
  await s.click('.stavka .ukloni-stavku >> nth=1');
  provjeri(await s.locator('.stavka').count() === 5 && /Uklonjeno/.test(await s.locator('#poruka').innerText()), `× uklanja stavku („${imeX}”) i nudi „Vrati”`);
  await s.click('#poruka button');
  await s.waitForTimeout(200);
  provjeri(await s.locator('.stavka').count() === 6 && (await s.locator('.stavka-naziv >> nth=1').innerText()).trim() === imeX, '„Vrati” vraća stavku na isto mjesto');
  const trgovineNaPopisu = await s.locator('.stavka .stavka-trgovina').allInnerTexts();
  const naziviTrgovina = await s.locator('.stavka .stavka-trgovina b').evaluateAll((b) => b.map((x) => ({ t: x.textContent, ok: x.scrollWidth <= x.clientWidth + 1 && x.clientWidth > 0 })));
  provjeri(naziviTrgovina.length === 6 && naziviTrgovina.every((x) => x.ok), 'naziv trgovine uz stavku vidljiv i neskraćen: ' + naziviTrgovina.map((x) => x.t).join(', '));
  provjeri(trgovineNaPopisu.length === 6 && trgovineNaPopisu.every((x) => /€/.test(x)),
    'uz svaku stavku popisa najjeftinija trgovina i cijena: ' + trgovineNaPopisu.slice(0, 2).map((x) => x.replace(/\s+/g, ' ')).join(' | '));
  provjeri(await s.locator('.plocice.precaci').count() === 0, 's popisom: umjesto prečaca pločice za slanje');
  await s.fill('#upisPolje', 'sol'); await s.press('#upisPolje', 'Enter');
  await s.waitForSelector('#poruka:not([hidden])');
  const porukaOkvir = await s.locator('#poruka').boundingBox();
  const trakaOkvir = await s.locator('.donja-traka').boundingBox();
  provjeri(porukaOkvir.y + porukaOkvir.height <= trakaOkvir.y + 1, 'poruka „Dodano…” iznad donje trake, ne prekriva gumbe');
  await s.click('.stavka .ukloni-stavku >> nth=-1');
  await s.waitForTimeout(200);
  provjeri(await s.locator('.donja-traka [data-akcija="zakljucaj"]').isVisible() && await s.locator('.donja-traka [data-akcija="dijeli-ploca"]').isVisible(),
    'donja zona (jedna ruka): „Pošalji” i „Zaključaj i usporedi” uvijek vidljivi iznad izbornika');
  const traka = await s.locator('.donja-traka').boundingBox();
  provjeri(traka && traka.y > (await s.evaluate(() => innerHeight)) * 0.75, 'traka s radnjama je u donjoj četvrtini zaslona');
  await s.click('.donja-traka [data-akcija="dijeli-ploca"]');
  await s.waitForSelector('.ploca-sadrzaj .dijeli-kartica');
  const waHref = await s.locator('.dijeli-kartica a.plocica.wa').getAttribute('href');
  const waTekst = decodeURIComponent(waHref.split('text=')[1]);
  provjeri(/^https:\/\/wa\.me\/\?text=/.test(waHref) && /^🛒 Najjeftinija košarica\n📅 \d+\.\d+\.\d{4}\.\n📍 Trgovina: .+\n🗺️ https:\/\/www\.google\.com\/maps\/search\/\?api=1&query=.+\nPopis za kupnju:\n/.test(waTekst)
    && (waTekst.match(/^• .+ – \d+,\d\d €$/gm) || []).length === 6 && /\n💰 Ukupno: \d+,\d\d €$/.test(waTekst),
    'WhatsApp poruka u formatu vlasnika: datum, trgovina, karta, 6 artikala s cijenom, ukupno');
  const zbrojArtikala = (waTekst.match(/– (\d+,\d\d) €$/gm) || []).reduce((s, x) => s + Math.round(Number(x.match(/(\d+),(\d\d)/).slice(1).join('.')) * 100), 0);
  const ukupnoPoruke = Math.round(Number(waTekst.match(/💰 Ukupno: (\d+),(\d\d)/).slice(1).join('.')) * 100);
  provjeri(zbrojArtikala === ukupnoPoruke, `ukupno u poruci = zbroj artikala (${ukupnoPoruke / 100} €)`);
  provjeri(/^viber:\/\/forward\?text=/.test(await s.locator('.dijeli-kartica a.plocica.viber').getAttribute('href')), 'pločica Viber');
  // imenik: Contact Picker (Chrome na Androidu) – ovdje simuliran
  await s.evaluate(() => Object.defineProperty(navigator, 'contacts', { configurable: true, value: { select: async () => [{ name: ['Mama'], tel: ['091 234 5678'] }] } }));
  await s.click('.dijeli-kartica [data-akcija="imenik"]');
  await s.waitForSelector('.ploca-sadrzaj a.plocica.wa');
  const waOsoba = await s.locator('.ploca-sadrzaj a.plocica.wa').getAttribute('href');
  provjeri(/^https:\/\/wa\.me\/385912345678\?text=/.test(waOsoba) && /Mama/.test(await s.locator('.ploca-sadrzaj').innerText()),
    'iz imenika: odabrana osoba (Mama, 091 234 5678) → WhatsApp izravno na +385 91 234 5678');
  provjeri(/^sms:/.test(await s.locator('.ploca-sadrzaj a.plocica.ostalo').getAttribute('href')), 'iz imenika: i SMS toj osobi');
  await snimi('2b-imenik');
  await s.evaluate(() => { delete navigator.contacts; document.querySelector('#ploca').hidden = true; });

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
    // mikrofon u donjoj traci (jedna ruka): isti glasovni unos, oblačić pokazuje što je čuto
    provjeri(await sg.locator('.donja-traka #mikrofonDolje').isVisible(), 'mikrofon je i u donjoj traci (jedna ruka)');
    await sg.click('#mikrofonDolje');
    await sg.waitForSelector('#glasOblacic:not([hidden])', { timeout: 3000 });
    provjeri(true, 'dok sluša, oblačić iznad donje trake pokazuje stanje');
    await sg.waitForFunction(() => document.querySelectorAll('.stavka').length >= 3 && !document.querySelector('#mikrofonDolje.slusa'), null, { timeout: 5000 });
    provjeri(/10 kom|20 kom/.test(await sg.locator('.stavke').innerText()) && await sg.locator('#glasOblacic').isHidden(),
      'donji mikrofon dodaje na popis (ponovljene stavke zbrojene), oblačić se skrije');
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

  console.log('Zaključan popis po odjelima trgovine');
  {
    await s.click('[data-akcija="zakljucaj"]');
    await s.waitForSelector('.sazetak, #karuselB, #matrica');
    await s.click('nav [data-idi="popis"]');
    await s.waitForSelector('.stavke');
    const odjeli = await s.locator('.stavke .odjel').allInnerTexts();
    const red = odjeli.map((x) => x.toLowerCase());
    provjeri(odjeli.length >= 3 && red.indexOf('voće i povrće') < red.indexOf('kruh i peciva') && red.indexOf('kruh i peciva') < red.indexOf('mliječno i jaja'),
      'zaključan popis po odjelima: ' + odjeli.join(' → '));
    await s.click('[data-akcija="otkljucaj"]');
    await s.waitForSelector('#upisPolje');
    provjeri(await s.locator('.stavke .odjel').count() === 0, 'otključan popis: bez odjela (redoslijed kako je upisano)');
  }

  console.log('Rezultati');
  await s.click('[data-akcija="zakljucaj"]');
  await s.waitForSelector('#matrica');
  // matrica trgovina: zadani prikaz usporedbe
  const brojStupaca = await s.locator('#matrica .m-glava').count();
  provjeri(brojStupaca >= 3 && await s.locator('#matrica .m-stavka').count() === 6, `matrica: 6 redaka (stavke) × ${brojStupaca} trgovina`);
  provjeri(await s.locator('#matrica .m-celija.r0').count() >= 6, 'matrica: u svakom retku istaknuta najjeftinija cijena (zeleno)');
  const ukupniMatrica = await s.locator('#matrica .m-ukupno').allInnerTexts();
  const centi = (x) => Math.round(Number(x.replace(/[^\d,]/g, '').replace(',', '.')) * 100);
  provjeri(ukupniMatrica.every((x, k) => k === 0 || centi(x) >= centi(ukupniMatrica[k - 1])), 'matrica: trgovine poredane od najjeftinije (ukupno)');
  const prviStupac = await s.locator('#matrica .m-glava >> nth=0').getAttribute('data-id');
  const prviZbroj = await s.locator(`#matrica .m-celija[data-id="${prviStupac}"]`).evaluateAll((c) => c.reduce((z, x) => z + (/€/.test(x.textContent) ? Math.round(Number(x.textContent.replace(/[^\d,]/g, '').replace(',', '.')) * 100) : 0), 0));
  provjeri(prviZbroj === centi(ukupniMatrica[0]), 'matrica: zbroj ćelija stupca = ukupno trgovine');
  await s.click('#matrica .m-glava >> nth=2');
  await s.waitForTimeout(400);
  const odabranaMatrica = (await s.locator('#matrica .m-glava >> nth=2 >> .m-lanac').innerText()).trim();
  provjeri(await s.locator('#matrica .m-glava >> nth=2').getAttribute('aria-pressed') === 'true'
    && (await s.locator('#detaljiB h3').innerText()).includes(odabranaMatrica)
    && (await s.locator('.donja-traka [data-akcija="kupljeno"]').getAttribute('data-opis')).includes(odabranaMatrica),
    `matrica: dodir trgovine (${odabranaMatrica}) prikaže njen popis, Kupio/la sam vrijedi za nju`);
  const sirinaStupca = await s.locator('#matrica .m-glava >> nth=0').evaluate((x) => x.getBoundingClientRect().width);
  provjeri(sirinaStupca < 120, `matrica: stupci stalne širine (${Math.round(sirinaStupca)} px), više trgovina vidljivo odjednom`);
  await snimi('3a-matrica');
  await s.click('[data-tab="B"]');
  await s.waitForSelector('#karuselB');
  await s.locator('#karuselB').evaluate((k) => k.scrollTo({ left: 0 }));
  await s.click('#karuselB .trgovina-kartica >> nth=0');
  await s.waitForTimeout(500);
  provjeri(/€/.test(await s.locator('#karuselB .u-fokusu .tk-cijena').innerText()), 'B: ukupna cijena za jednu trgovinu');
  const cijenaB = await s.locator('#karuselB .u-fokusu .tk-cijena').boundingBox();
  const trakaB = await s.locator('.donja-traka').boundingBox();
  provjeri(cijenaB.y + cijenaB.height < trakaB.y, 'B: cijena trgovine u fokusu vidljiva iznad donje trake (nije prekrivena)');
  provjeri(await s.locator('.sazetak').count() === 0, 'B: najbolja trgovina nije prikazana dvaput');
  provjeri(await s.locator('#karuselB .trgovina-kartica').count() >= 3, 'B: karusel trgovina po ukupnoj cijeni');
  provjeri(await s.locator('#karuselB .trgovina-kartica.u-fokusu').count() === 1
    && await s.locator('#karuselB .trgovina-kartica >> nth=0').getAttribute('aria-pressed') === 'true', 'B: prva (najjeftinija) trgovina u fokusu');
  const lanacPrije = (await s.locator('#detaljiB h3').innerText()).trim();
  await s.locator('#karuselB .trgovina-kartica >> nth=2').click();
  await s.waitForTimeout(700);
  const lanacPoslije = (await s.locator('#detaljiB h3').innerText()).trim();
  const opisKupnje = await s.locator('.donja-traka [data-akcija="kupljeno"]').getAttribute('data-opis');
  provjeri(opisKupnje.includes(lanacPoslije.replace('Popis u ', '')), `„Kupio/la sam” bilježi trgovinu u fokusu (${opisKupnje})`);
  provjeri(await s.locator('#karuselB .trgovina-kartica >> nth=2').getAttribute('aria-pressed') === 'true' && lanacPrije !== lanacPoslije,
    `B: dodir/klizanje mijenja trgovinu u fokusu i njen popis („${lanacPrije}” → „${lanacPoslije}”)`);
  await s.locator('#karuselB').evaluate((k) => k.scrollTo({ left: 0 }));
  await s.waitForTimeout(500);
  provjeri(await s.locator('#karuselB .trgovina-kartica >> nth=0').getAttribute('aria-pressed') === 'true', 'B: klizanje natrag vraća fokus na prvu');
  provjeri(await s.locator('.oglas .oglas-oznaka').count() === 1, 'oglas: zaobljeni banner s oznakom „Oglas”');
  await snimi('3-rezultat-b');
  await s.click('[data-tab="A"]');
  await s.waitForSelector('.sazetak, #karuselB, #matrica');
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
  await s.waitForSelector('.sazetak, #karuselB, #matrica');
  provjeri(/\+/.test(await s.locator('.sazetak .gdje').innerText()), 'C: dvije trgovine');
  await snimi('5-rezultat-c');
  await s.click('.donja-traka [data-akcija="podijeli-rezultat"]');
  await s.waitForSelector('.ploca-sadrzaj .pregled-poruke');
  const porukaC = await s.locator('.ploca-sadrzaj .pregled-poruke').inputValue();
  provjeri(/📍 Trgovina 1: /.test(porukaC) && /📍 Trgovina 2: /.test(porukaC) && (porukaC.match(/🗺️ https:\/\/www\.google\.com\/maps/g) || []).length === 2
    && (porukaC.match(/Ukupno u ovoj trgovini: /g) || []).length === 2 && /💰 Ukupno: /.test(porukaC), 'poruka za dvije trgovine: svaka s nazivom, kartom, artiklima i iznosom, na kraju ukupno');
  await s.goBack();
  await s.waitForTimeout(200);
  await s.click('[data-akcija="kupljeno"]');
  await s.waitForSelector('.slavlje .slavlje-kvacica');
  provjeri(await s.locator('.slavlje > i').count() > 20, 'Kupio/la sam: konfeti i kvačica koja se iscrta');
  await snimi('5b-slavlje');
  await s.waitForTimeout(2800);
  provjeri(await s.locator('.slavlje').count() === 0 && await s.locator('#ustedaIznos').innerText() !== '0,00 €', 'slavlje nestane samo; ušteda u zaglavlju odbrojana do novog iznosa');
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
  await s.click('nav [data-idi="vise"]');
  await s.click('.zaslon [data-idi="karta"]');
  await s.waitForSelector('#karta');
  provjeri(/u krugu 10 km/i.test(await s.locator('.naslov-zaslona').innerText()), 'karta prikazuje isti krug');
  await snimi('7-karta');
  await s.click('nav [data-idi="rezultati"]');
  await s.waitForSelector('.sazetak, #karuselB, #matrica, .prazno', { timeout: 20000 });
  const rezKrug = await s.locator('.zaslon').innerText();
  const brojPoslovnica = Number((rezKrug.match(/U krugu 10 km: (\d+) poslovnic/) || [])[1] || 0);
  provjeri(brojPoslovnica > 0 && brojPoslovnica === brojUKrugu, `rezultati koriste iste poslovnice u krugu (${brojPoslovnica})`);
  await s.click('[data-tab="B"]');
  await s.waitForSelector('.sazetak, #karuselB, #matrica');
  const karticeKrug = await s.locator('#karuselB .trgovina-kartica').evaluateAll((k) => k.map((x) => x.querySelector('.tk-lanac').firstChild.textContent.trim() + '|' + x.querySelector('.tk-cijena').textContent));
  provjeri(new Set(karticeKrug).size === karticeKrug.length, `B u krugu: isti lanac s istom cijenom samo jednom (${karticeKrug.length} unosa)`);
  const dmKartica = await s.locator('#karuselB .trgovina-kartica', { hasText: 'dm' }).allInnerTexts();
  provjeri(dmKartica.some((x) => /ista cijena u svim poslovnicama/.test(x)), 'uz lokaciju i dm (jedan cjenik, bez lokacija poslovnica) je u usporedbi');
  const upute = s.locator('#detaljiB a.upute');
  provjeri(await upute.count() === 1 && /google\.com\/maps\/dir\/\?api=1&destination=4\d\.\d+,1\d\.\d+/.test(await upute.getAttribute('href')), 'B u krugu: „Upute do trgovine” vodi na Google Karte do te poslovnice');
  await snimi('8-rezultat-krug');
  await s.click('.donja-traka [data-akcija="podijeli-rezultat"]');
  await s.waitForSelector('.ploca-sadrzaj .pregled-poruke');
  const porukaKrug = await s.locator('.ploca-sadrzaj .pregled-poruke').inputValue();
  provjeri(/📍 Trgovina: [^\n]+, [^\n]+\n🗺️ https:\/\/www\.google\.com\/maps\/search\/\?api=1&query=4\d\.\d+,1\d\.\d+\n/.test(porukaKrug), 'u krugu: poruka sadrži adresu i točnu lokaciju poslovnice na karti');
  await s.goBack();
  await s.waitForTimeout(200);

  console.log('Akcije i Više');
  await s.click('nav [data-idi="akcije"]');
  await s.waitForSelector('.akcija, .prazno');
  provjeri(await s.locator('.akcija').count() > 0, 'akcije se prikazuju');
  const akcijeTekst = await s.locator('.zaslon').innerText();
  provjeri(/najniža cijena u 30 dana/.test(akcijeTekst) && /u 30 dana bilo i/.test(akcijeTekst), 'akcije: „✓ najniža cijena u 30 dana” i „u 30 dana bilo i …”');
  const sveAkcije = await s.locator('.zaslon > section .akcija').count();
  await s.check('#praveAkcije');
  await s.waitForTimeout(200);
  const prave = await s.locator('.zaslon > section .akcija').count();
  provjeri(prave > 0 && prave < sveAkcije && !/u 30 dana bilo i/.test(await s.locator('.zaslon').innerText()), `„Samo prave akcije”: ${prave} od ${sveAkcije}`);
  await s.uncheck('#praveAkcije');
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

  console.log('Navigacija: tipka Natrag na mobitelu, gumb natrag, označena kartica');
  provjeri(await s.locator('nav [data-idi="vise"].aktivno').count() === 1, 'na podzaslonu (Status) označena je kartica Više');
  provjeri(/Više/.test(await s.locator('.natrag').innerText()), 'gumb natrag piše kamo vodi: „' + (await s.locator('.natrag').innerText()).trim() + '”');
  await s.goBack();                                                   // tipka Natrag na Androidu
  await s.waitForSelector('.izbor');
  provjeri(await s.locator('.izbor [data-idi="status"]').count() === 1, 'Natrag sa Statusa → Više (aplikacija se ne zatvara)');
  await s.goBack();
  await s.waitForSelector('.lokacija-gumb');
  provjeri(await s.evaluate(() => history.state && history.state.kosarica) === 'baza', 'Natrag s Više → Popis; tek sljedeći Natrag izlazi iz aplikacije');
  await s.click('.lokacija-gumb');
  await s.waitForSelector('#ploca:not([hidden])');
  await s.goBack();
  await s.waitForTimeout(200);
  provjeri(await s.locator('#ploca').isHidden() && await s.locator('.lokacija-gumb').count() === 1, 'otvorena ploča: Natrag zatvara ploču, zaslon ostaje');
  await s.click('nav [data-idi="akcije"]');
  await s.click('.zaglavlje .usteda-zna');
  await s.waitForSelector('.velika-usteda');
  await s.click('.natrag');
  await s.waitForSelector('#praveAkcije');
  provjeri(true, 'gumb natrag vraća točno odakle se došlo (Ušteda → Akcije)');
  await s.goBack();
  await s.waitForSelector('.lokacija-gumb');
  provjeri(await s.locator('nav [data-idi="popis"].aktivno').count() === 1, 'Natrag s druge kartice → Popis');
  await s.click('nav [data-idi="vise"]');
  await s.click('[data-idi="status"]');
  await s.waitForSelector('.tablica');
  await s.click('[data-idi="vise"]');
  await s.click('[data-idi="greska"]');
  provjeri(/Izvješće o grešci/.test(await s.locator('#izvjesceTekst').inputValue()), 'izvješće o grešci za Claude Code');
  await s.click('[data-idi="vise"]');
  await s.click('[data-idi="obitelj"]');
  await s.click('[data-akcija="podijeli-poveznicu"]');
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

  console.log('Sigurnost: zlonamjerna poveznica obiteljskog popisa');
  const napad = await preglednik.newContext({ ...devices['Pixel 7'], locale: 'hr-HR' });
  const s5 = await napad.newPage();
  s5.on('pageerror', (e) => greske.push('pageerror(napad): ' + e.message));
  // HTML oko riječi koja postoji u nazivima proizvoda – tako se prikaže „traži … u nazivima proizvoda” (ranjivi redak)
  const zlo = '<u>barcaffe</u>';
  const kodNapada = Buffer.from(JSON.stringify({ v: 1, s: [{ t: zlo, g: '', p: '', k: 1e12, j: 'pak', b: '' }] })).toString('base64url');
  await s5.goto(url + '#popis=' + kodNapada);
  await s5.waitForSelector('[data-akcija="uvoz-dodaj"]');
  await s5.click('[data-akcija="uvoz-dodaj"]');
  await s5.waitForSelector('.stavka');
  await s5.waitForTimeout(300);
  const stavkaNapada = await s5.locator('.stavka').innerText();
  provjeri(await s5.locator('.stavka u').count() === 0 && stavkaNapada.includes('<u>barcaffe</u>') && /traži/.test(stavkaNapada),
    'tekst iz tuđe poveznice prikazuje se kao tekst, ne izvršava se (XSS)');
  provjeri(/1 pakiranje|1 pak/.test(stavkaNapada), 'apsurdna količina iz poveznice (10^12) zamijenjena s 1');
  await napad.close();

  console.log('Stari spremljeni popis s mobitela (stavka "mljeko" iz starije verzije)');
  const stari = await preglednik.newContext({ ...devices['Pixel 7'], locale: 'hr-HR' });
  await stari.addInitScript(() => {
    if (sessionStorage.getItem('postavljeno')) return;
    sessionStorage.setItem('postavljeno', '1');
    localStorage.setItem('kosarica-stanje-v1', JSON.stringify({ drzava: 'hr', zaslon: 'popis', verzijaPodataka: 'stara',
      stavke: [{ id: 's1', tekst: 'mljeko', g: -1, pg: -1, upit: 'mljeko', filtar: '', kolicina: 1, jedinica: 'pak', zadano: true }] }));
  });
  const s4 = await stari.newPage();
  s4.on('pageerror', (e) => greske.push('pageerror(stari): ' + e.message));
  await s4.goto(url);
  await s4.waitForSelector('.stavka');
  const staraStavka = await s4.locator('.stavka').innerText();
  provjeri(/Mlijeko/.test(staraStavka) && /1 l/.test(staraStavka), 'stara stavka „mljeko” ponovno prepoznata: ' + staraStavka.replace(/\s+/g, ' '));
  await s4.click('[data-akcija="zakljucaj"]');
  await s4.waitForSelector('[data-tab="A"]');
  await s4.click('[data-tab="A"]');
  await s4.waitForSelector('.ponuda');
  const ponudaMlijeko = await s4.locator('.ponuda >> nth=0').innerText();
  provjeri(/mlijeko/i.test(ponudaMlijeko) && !/jogurt/i.test(ponudaMlijeko), 'rezultat za staru stavku je mlijeko, ne jogurt');
  await stari.close();

  console.log('Skener (ručni unos barkoda)');
  await s.goto(url);
  await s.waitForSelector('.izbornik');
  await s.click('nav [data-idi="skener"]');
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
    await s3.waitForSelector('.sazetak, #karuselB, #matrica', { timeout: 25000 });
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
