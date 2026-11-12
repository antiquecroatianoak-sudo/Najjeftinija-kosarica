# Licence tima — praćenje softverskih licenci

Zaseban projekt (nije dio aplikacije „Najjeftinija košarica”). Mala SaaS aplikacija za manje timove:
evidencija pretplata, ukupni trošak, otkrivanje neaktivnih (plaćenih, a nekorištenih) pretplata.

Bez vanjskih paketa: Python 3.11+ (stdlib + SQLite) i web sučelje u čistom JS-u, bez build koraka.

## Pokretanje

```bash
cd licence
python3 -m licence_app --demo            # http://127.0.0.1:8000, baza licence.db
python3 -m licence_app --db :memory:     # privremeno, bez spremanja
python3 -m unittest discover -s tests    # testovi
```

## Struktura

```
licence_app/
  models.py      entitet License, enumi, validacija, izvedene vrijednosti (mjesečni trošak, sljedeća obnova)
  repository.py  LicenseRepository (protokol) + SQLite i in-memory implementacija
  service.py     slučajevi upotrebe: CRUD, filtriranje, nadzorna ploča
  api.py         REST API (http.server) + posluživanje web/
  seed.py        primjer podataka (--demo, izmišljeni)
  __main__.py    pokretanje
web/
  index.html, css/app.css
  js/api.js        klijent za API
  js/dashboard.js  pregled troškova, neaktivne pretplate, obnove, kategorije
  js/licenses.js   tablica licenci (na mobitelu kartice)
  js/form.js       dijalog za dodavanje/uređivanje s greškama po polju
  js/main.js       povezivanje i osvježavanje
tests/           model, servis (obje implementacije repozitorija), API preko stvarnog HTTP-a
```

Ovisnosti idu samo prema unutra: `api → service → repository → models`. Model nema I/O.

## Podatkovni model — `License`

| Polje | Tip | Napomena |
|---|---|---|
| `id` | string (32 hex) | UUID4, dodjeljuje poslužitelj |
| `name` | string ≤120 | |
| `category` | string ≤60 | slobodan unos, nudi postojeće |
| `cost` | decimal, ≥0, 2 decimale | iznos **po ciklusu**; čuva se kao tekst (bez float zaokruživanja) |
| `currency` | ISO 4217 | npr. `EUR` |
| `billing_cycle` | `monthly` \| `quarterly` \| `yearly` | |
| `start_date` | datum `GGGG-MM-DD` | |
| `status` | `active` \| `inactive` \| `cancelled` | zadano `active` |

Izvedeno (samo za čitanje): `monthly_cost`.

Status znači: **active** — plaća se i koristi; **inactive** — plaća se, ali se ne koristi (kandidat za uštedu);
**cancelled** — više se ne plaća.

## Pravila nadzorne ploče

- Trošak = licence koje se plaćaju (`active` + `inactive`) i čiji je početak već prošao.
- Iznosi se **nikad ne preračunavaju između valuta** (tečaj nije poznat) — svaki zbroj je po valuti.
- Godišnje = mjesečno × 12 (procjena).
- Neaktivne pretplate: sve `inactive` koje se plaćaju, poredane po mjesečnom trošku; zbroj je „moguća ušteda”.
- Obnove: sljedeći datum naplate unutar 30 dana (31. 1. + 1 mj. = 28./29. 2., bez pomaka kasnije).

## API

| Metoda | Putanja | |
|---|---|---|
| GET | `/api/licenses?status=&category=&q=` | popis s filtrima |
| POST | `/api/licenses` | stvaranje (201) |
| GET | `/api/licenses/{id}` | |
| PUT | `/api/licenses/{id}` | puna zamjena (sva obavezna polja) |
| PATCH | `/api/licenses/{id}` | djelomična izmjena |
| DELETE | `/api/licenses/{id}` | 204 |
| GET | `/api/dashboard` | pregled |
| GET | `/api/meta` | ciklusi, statusi, postojeće kategorije |

Greške: `{"error": {"code", "message", "fields"?}}` — 400 neispravan JSON, 404, 405, 413 (>64 KB),
415 (nije JSON), 422 validacija s porukama po polju.

## Mjesta za proširenje (nije implementirano)

- **Timovi / više korisnika (SaaS):** dodati `team_id` u model i tablicu te repozitorij ograničen na tim
  (npr. `TeamScopedRepository(repo, team_id)`); servis se ne mijenja.
- **Prijava:** middleware u `api.make_handler` prije `router.resolve`.
- **Druga baza:** nova klasa koja zadovoljava `LicenseRepository` (npr. Postgres).
- **Automatska detekcija nekorištenja:** polje `last_used_at` (iz SSO/integracija) i pravilo u servisu
  koje predlaže prelazak `active → inactive`.
- **Preračun valuta:** samo uz izričit izvor tečaja; danas namjerno nema.
- **Migracije sheme:** trenutačno `CREATE TABLE IF NOT EXISTS`; pri prvoj promjeni sheme uvesti verziju (`PRAGMA user_version`).
