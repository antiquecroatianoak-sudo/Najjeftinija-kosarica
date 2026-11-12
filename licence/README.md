# License Pulse

Pregled troškova softverskih licenci za manje timove: koliko plaćate, što se ne koristi,
što se uskoro naplaćuje i koliko možete uštedjeti – na prvom zaslonu.

Zaseban projekt u mapi `licence/` (nije dio aplikacije „Najjeftinija košarica” u ovom repozitoriju).
Python 3.11+ samo sa standardnom bibliotekom (SQLite), web sučelje u čistom HTML/CSS/JS-u, bez build koraka i bez AI modela.

## Brzi početak

```bash
cd licence
LICENCE_ADMIN_USER=admin LICENCE_ADMIN_PASSWORD='lozinka-od-12+' \
  python3 -m licence_app serve --demo          # http://127.0.0.1:8000 (primjer podataka)
python3 -m unittest discover -s tests          # 72 testa (model, baza, servisi, API, integracija)
node tests/e2e.cjs                             # cijeli tok u pregledniku (Playwright + Chromium)
```

Produkcija (Docker, TLS, sigurnosne kopije): [docs/DEPLOY.md](docs/DEPLOY.md).

## Što radi

| Područje | Opis |
|---|---|
| Nadzorna ploča | Na vrhu **trenutačni gubitak** (neaktivne licence / mj.), udio otpada, sljedeća naplata koju možete izbjeći i **kalkulator povrata ulaganja** (projicirana ušteda 12 mj. prema stvarnim datumima naplate, neto dobit, ROI %). Zatim ukupni trošak u referentnoj valuti, ističe uskoro (7/30/90 d), plan plaćanja za 12 mjeseci, kandidati za pregovore, trošak po kategoriji. |
| Licence | Puni CRUD, brzi filtri (aktivne, neaktivne, otkazane, ističe ≤ 30 d, praćeno korištenje), pretraga, sortiranje, uvoz CSV/Excel s mapiranjem stupaca, izvoz CSV. |
| Praćenje korištenja | Sustav prijava (SSO) ili skripta šalje `POST /api/usage` s API tokenom; licenca bez korištenja N dana automatski postaje neaktivna, a nova prijava je vraća u aktivne. Identiteti korisnika se tokeniziraju. |
| Valute | ECB referentni tečajevi (automatski svakih 6 h) i ručni tečajevi; svi zbrojevi u referentnoj valuti organizacije. Iznos bez tečaja se nikad ne nagađa – prikazuje se kao nepreračunat. |
| Obavijesti i automatizacija | Pametne obavijesti prije obnove (posebno za neaktivne: „otkažite prije naplate”), webhookovi s HMAC potpisom i ponovnim pokušajima. |
| Banka | Uvoz izvoda (ISO 20022 camt.053 ili CSV), automatsko sparivanje plaćanja s licencama, prijedlozi, otkrivanje nepraćenih ponavljajućih pretplata i razlika u cijeni. IBAN se ne sprema. |
| Više organizacija | Svaka organizacija (tvrtka) ima svoje licence, korisnike, boju i naziv u sučelju, referentnu valutu i pravila. Podaci su strogo odvojeni. |
| Brzina | Lokalna predmemorija za trenutačni prikaz, optimistična ažuriranja s povratom pri grešci, pozadinska sinkronizacija, rad bez mreže (prikaz spremljenih podataka). |

Prečaci: `N` nova licenca, `/` pretraga, `1`–`6` brzi filtri, `G P/L/B/S` navigacija, `I` uvoz, `E` izvoz, `O` obavijesti, `R` osvježi, `?` pomoć.

## Arhitektura

```
licence_app/
  config.py        postavke iz LICENCE_* varijabli; produkcija odbija nesigurnu konfiguraciju
  db.py            SQLite (WAL), transakcije, verzionirane migracije (v0.1.0 -> v1 -> v2)
  models.py        License, Organization, validacija (bez I/O)
  repository.py    licence po organizaciji, filtri u SQL-u na indeksima
  stores.py        organizacije, korisnici, tokeni, korištenje, cijene, tečajevi, obavijesti, webhookovi, revizija
  service.py       CRUD, izračuni, detekcija, ROI, analitika, pregovori
  usage.py         prijem korištenja, automatski status, obavijesti o isteku
  rates.py         ECB tečajevi i preračun
  webhooks.py      potpis, isporuka, ponovni pokušaji, SSRF zaštita
  transfer.py      uvoz CSV/XLSX s mapiranjem, izvoz CSV
  banking/         izvodi (camt.053, CSV), protokol za žive konektore, sparivanje, servis
  security.py      lozinke, ograničenje prijava, tokeni, tokenizacija, maskiranje
  app.py           sastavljanje slojeva, autentifikacija, radni prostor po organizaciji
  maintenance.py   planer: webhookovi, statusi, tečajevi, optimize, backup, retencija
  api.py           REST API + statičko sučelje, sigurnosna zaglavlja, CSRF, zapisi
  __main__.py      serve, create-org, create-user, create-token, backup, check, migrate
web/               index.html, css/app.css, js/ (api, store, shell, dashboard, licenses, form, importer, bank, settings)
tests/             unittest + e2e.cjs (Playwright)
```

Ovisnosti idu prema unutra: `api → app → service/usage/banking → repository/stores → db/models`.

Dokumentacija: [DEPLOY](docs/DEPLOY.md) · [SECURITY (sigurnost, usklađenost, lokacija podataka)](docs/SECURITY.md) · [BANKING](docs/BANKING.md) · [API i integracije](docs/API.md) · [Pozicioniranje](docs/POSITIONING.md)

## Ograničenja (namjerna ili još neriješena)

- Prijava je HTTP Basic (preglednik pamti podatke do zatvaranja; nema gumba „Odjava”). SSO/OIDC za korisnike nije implementiran.
- Živa veza s bankom (PSD2) nije implementirana – zahtijeva reguliranog pružatelja; postoji protokol i uvoz izvoda.
- Poredak po nazivu je po Unicode kodu nakon `casefold`, ne hrvatska abecedna kolacija.
- Jedan proces sa SQLite bazom: namijenjeno manjim timovima (desetci korisnika, tisuće licenci po organizaciji).
