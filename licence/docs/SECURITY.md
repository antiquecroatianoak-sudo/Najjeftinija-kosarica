# Sigurnost, usklađenost i lokacija podataka

Ovaj dokument opisuje **što aplikacija stvarno radi** i što ostaje odgovornost onoga tko je postavlja.
License Pulse **nema certifikate** (ISO 27001, SOC 2 i sl.) i ne tvrdi usklađenost koja nije provjerena
neovisnom revizijom. Zakonska usklađenost (npr. GDPR) ovisi i o tome kako organizacija koristi i postavlja sustav.

## Lokacija podataka

- Aplikacija se instalira na vašu infrastrukturu (self-hosted). **Svi podaci su u jednoj SQLite datoteci**
  na volumenu koji vi odaberete (`/data`) i u kopijama koje vi konfigurirate. Lokacija podataka = lokacija vašeg poslužitelja.
- Aplikacija sama šalje podatke van samo:
  1. ECB-u (`www.ecb.europa.eu`) – samo dohvat javne tečajne liste, ne šalje nikakve vaše podatke (isključivo `LICENCE_RATES_AUTO=0`);
  2. na webhook adrese koje administrator sam unese (sadržaj događaja: naziv licence, iznos, datumi).
- Nema telemetrije, analitike treće strane, CDN-a ni vanjskih fontova; sučelje učitava samo vlastite datoteke (CSP `default-src 'self'`).

## Koji se podaci obrađuju

| Podatak | Kako se čuva |
|---|---|
| Licence (naziv, kategorija, trošak, datumi, status) | otvoreno u bazi (potrebno za prikaz) |
| Korisnici aplikacije | korisničko ime; lozinka kao PBKDF2-SHA256 (310 000 iteracija, sol po korisniku) |
| API tokeni | samo SHA-256 sažetak; token se prikazuje jednom |
| Korištenje licenci | identitet korisnika (npr. e-mail) **tokeniziran** HMAC-SHA256 s `LICENCE_SECRET_KEY` – e-mail se ne sprema; vrijeme događaja |
| Bankovni izvodi | IBAN računa **tokeniziran** (HMAC) + zadnje 4 znamenke; brojevi kartica i IBAN-i u opisima **maskirani** prije spremanja; naziv primatelja, iznos, datum |
| Webhook tajne | otvoreno (potrebne za potpisivanje), prikazuju se samo pri izradi |
| Revizijski zapis | tko je što promijenio i kada, 730 dana |

Retencija (automatski): događaji korištenja 400 dana, revizija 730 dana, pročitane obavijesti 90 dana, završene isporuke webhookova 30 dana.

### O „end-to-end” enkripciji

Prava end-to-end enkripcija (podatke vidi samo klijent) **nije primjenjiva** na ovu vrstu aplikacije:
poslužitelj mora čitati iznose i datume da bi računao troškove, ROI, isteke i sparivao bankovne transakcije.
Umjesto toga zaštita je slojevita:

1. **U prijenosu:** HTTPS na reverse proxyju (obavezno; Basic autentifikacija bez TLS-a nije dopuštena) + HSTS.
2. **U mirovanju:** šifrirajte disk/volumen (LUKS, šifrirani EBS/Persistent Disk) i kopije (`restic`/`borg` s ključem).
   Aplikacija namjerno ne implementira vlastitu kriptografiju na razini polja – standardna biblioteka nema autentificiranu
   simetričnu enkripciju, a vlastita implementacija bila bi veći rizik od šifriranja diska.
3. **Minimizacija:** najosjetljiviji podaci (IBAN, e-mailovi korisnika, brojevi kartica) uopće se ne spremaju u čitljivom obliku.

## Kontrole u aplikaciji

- **Autentifikacija:** HTTP Basic na svim rutama osim `/api/health` i statičkih datoteka (CSS/JS/slike); predmemorija uspješnih
  provjera 5 min (lozinka se ne drži, samo sažetak); jednako vrijeme odgovora za nepostojeće korisnike.
- **Ograničenje prijava:** od 5. neuspjeha po IP adresi i korisničkom imenu blokada 2 s, zatim udvostručenje do 15 min (HTTP 429 + `Retry-After`).
- **Autorizacija:** uloge admin/član; administratorske rute (korisnici, tokeni, webhookovi, tečajevi, organizacija, revizija) vraćaju 403 članovima.
- **Izolacija tenanata:** svaki SQL upit nad licencama sadrži `organization_id`; ID iz druge organizacije vraća 404 (testirano na razini repozitorija i HTTP-a).
- **CSRF:** promjene zahtijevaju zaglavlje `X-Requested-With: LicensePulse` i `Content-Type: application/json`; strani `Origin` se odbija.
- **Zaglavlja:** CSP bez inline koda, `X-Frame-Options: DENY`, `frame-ancestors 'none'`, `nosniff`, `Referrer-Policy: no-referrer`,
  COOP/CORP, `Permissions-Policy`, opcionalno HSTS; API odgovori `Cache-Control: no-store`.
- **Ulaz:** ograničenje veličine tijela (64 KB, uvoz 14 MB), validacija svakog polja, parametrizirani SQL, zaštita od `../`,
  XML bez DTD/ENTITY (bez XXE i „billion laughs”), ograničenje raspakiranog XLSX-a (zip bomb), zaštita od CSV/formula injekcije u izvozu.
- **Webhookovi (SSRF):** samo HTTPS, sve razriješene adrese moraju biti javne (blokirano: localhost, privatne mreže, link-local/metadata),
  veza vezana uz provjerenu adresu (bez DNS rebindinga), bez preusmjeravanja, HMAC-SHA256 potpis s vremenskom oznakom.
- **Pogreške:** klijent dobiva samo poruku i `request_id`; detalji idu u zapise. Zapisi ne sadrže lozinke, tokene ni tijela zahtjeva.
- **Kontejner:** non-root, read-only, bez capabilityja, `no-new-privileges`.

## Odgovornosti onoga tko postavlja sustav

- TLS i HSTS na reverse proxyju; ne izlagati port 8000 izravno internetu.
- Čuvati `LICENCE_SECRET_KEY` i `.env` izvan repozitorija (u upravitelju tajni).
- Šifrirani disk i šifrirane kopije izvan poslužitelja; povremeno testirati oporavak.
- Redovito ažurirati baznu sliku (sigurnosne zakrpe Pythona/Debiana).
- GDPR: evidencija obrade (podaci zaposlenika o korištenju softvera), informiranje zaposlenika o praćenju korištenja,
  ugovor o obradi s pružateljem hostinga ako postoji. Praćenje korištenja je opcionalno po licenci.

## Plan redovitih provjera i penetracijskog testiranja

| Učestalost | Aktivnost |
|---|---|
| Svaka promjena | Automatski testovi (jedinični, integracijski, e2e u pregledniku, uključujući autentifikaciju, CSRF, izolaciju tenanata, SSRF, XML, CSV injekciju) |
| Mjesečno | Ažuriranje bazne slike i ponovna izgradnja; pregled zapisa `login_failed`, `task_failed`, `webhook_failed`; provjera kopija |
| Tromjesečno | Pregled korisnika i API tokena (opoziv nekorištenih); test oporavka iz kopije; skeniranje slike (npr. Trivy/Grype) |
| Godišnje i prije velikih izdanja | Neovisni penetracijski test (OWASP ASVS razina 2) |

Opseg penetracijskog testa: autentifikacija i ograničenje prijava, autorizacija admin/član, izolacija tenanata (IDOR),
CSRF, XSS (CSP), SSRF kroz webhookove, uvoz datoteka (CSV/XLSX/XML: XXE, zip bomb, formula injekcija),
otkrivanje informacija u pogreškama, konfiguracija TLS-a i zaglavlja na proxyju, kontejner (bijeg, prava).
Nalazi se rješavaju prema ozbiljnosti: kritični odmah, visoki u 14 dana, srednji u sljedećem izdanju.

**Prijava ranjivosti:** pošaljite opis organizaciji koja održava vašu instalaciju (privatno, ne kao javni issue).
