# Postavljanje u produkciju

## 1. Docker (preporučeno)

```bash
cp .env.example .env
python3 -c "import secrets; print(secrets.token_hex(32))"   # upišite u LICENCE_SECRET_KEY
# upišite LICENCE_ADMIN_PASSWORD (12+ znakova) i naziv tvrtke
docker compose up -d --build
docker compose ps        # STATUS: healthy
```

Kontejner: korisnik bez root prava (uid 10001), datotečni sustav samo za čitanje, bez Linux capabilityja,
`no-new-privileges`, ograničena memorija i procesi. Jedino zapisivo mjesto je volumen `/data`
(baza `licence.db`, WAL datoteke i `backups/`). Port je objavljen samo na `127.0.0.1` – ispred stavite TLS proxy.

Provjereno u ovoj okolini (12. 11. 2026.): izgradnja slike, odbijanje pokretanja bez `LICENCE_SECRET_KEY`
(izlazni kod 2), `healthy`, uid 10001, read-only `/app`, 401 bez prijave, CRUD, podaci nakon `docker restart`,
`check` i `backup` naredbe, JSON zapisi. Bazna slika `python:3.13-slim-bookworm` – za ponovljive izgradnje
zamijenite oznaku digestom (`python:3.13-slim-bookworm@sha256:…`) i ažurirajte je redovito.

### TLS reverse proxy (primjer: Caddy)

```
licence.tvrtka.hr {
    reverse_proxy 127.0.0.1:8000
}
```

U `.env` tada: `LICENCE_TRUST_PROXY=1` (ispravna IP adresa klijenta za ograničenje prijava i zapise) i `LICENCE_HSTS=1`.
Basic autentifikacija smije ići **samo preko HTTPS-a**.

## 2. Bez Dockera (systemd)

```ini
# /etc/systemd/system/license-pulse.service
[Service]
User=licence
WorkingDirectory=/opt/license-pulse
EnvironmentFile=/etc/license-pulse.env
ExecStart=/usr/bin/python3 -m licence_app serve
Restart=on-failure
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=/var/lib/license-pulse
PrivateTmp=true
```

## Varijable okruženja

| Varijabla | Zadano | Opis |
|---|---|---|
| `LICENCE_ENV` | `development` | `production` uključuje obavezne provjere |
| `LICENCE_SECRET_KEY` | – | **obavezno u produkciji**, 32+ znaka; ključ za tokenizaciju (IBAN, korisnici). Promjena ključa prekida deduplikaciju izvoda i povezivanje korištenja – čuvajte ga kao lozinku |
| `LICENCE_HOST` / `LICENCE_PORT` | `127.0.0.1` (prod `0.0.0.0`) / `8000` | adresa poslužitelja |
| `LICENCE_DB` | `licence.db` | SQLite datoteka |
| `LICENCE_ADMIN_ORG` / `_USER` / `_PASSWORD` | – | prvo pokretanje: organizacija i administrator (idempotentno) |
| `LICENCE_TRUST_PROXY` | `0` | vjeruj `X-Forwarded-For` (samo iza vlastitog proxyja) |
| `LICENCE_HSTS` | `0` | šalji `Strict-Transport-Security` |
| `LICENCE_BACKUP_DIR` / `_KEEP` | – / `7` | dnevne kopije baze i broj zadržanih |
| `LICENCE_RATES_AUTO` | `1` | ECB tečajevi svakih 6 h (izlazni promet prema `www.ecb.europa.eu`) |
| `LICENCE_MAINTENANCE` | `1` | pozadinski planer |
| `LICENCE_LOG_FORMAT` / `_LEVEL` / `LICENCE_ACCESS_LOG` | `json` / `INFO` / `1` | zapisi na stdout |
| `LICENCE_WEBHOOK_ALLOW_PRIVATE` | `0` | samo razvoj; u produkciji zabranjeno |

## Administracija

```bash
docker compose exec licence python3 -m licence_app create-org "Druga tvrtka" druga
docker compose exec licence python3 -m licence_app create-user druga ivana --admin   # lozinka iz upita
docker compose exec licence python3 -m licence_app create-token druga "Okta"         # token za /api/usage
docker compose exec licence python3 -m licence_app check                             # integritet baze
docker compose exec licence python3 -m licence_app backup /data/backups
```

## Sigurnosne kopije i oporavak

- Planer svaki dan radi `quick_check`, `PRAGMA optimize`, WAL checkpoint i kopiju u `LICENCE_BACKUP_DIR`
  (online backup API – dosljedna kopija dok aplikacija radi), zadržava zadnjih `LICENCE_BACKUP_KEEP`.
- Kopije **izvan poslužitelja**: volumen ili `backups/` kopirajte šifrirano (npr. `restic`, `borg`) na drugu lokaciju.
- Oporavak: zaustavite kontejner, zamijenite `/data/licence.db` kopijom, obrišite `licence.db-wal` i `-shm`, pokrenite.
- Migracije sheme izvode se automatski pri pokretanju, svaka u svojoj transakciji uz provjeru stranih ključeva;
  aplikacija odbija bazu novije sheme (zaštita od vraćanja na stariju verziju). Prije nadogradnje napravite kopiju.

## Nadzor

- `GET /api/health` (bez prijave) za load balancer / Docker healthcheck.
- `GET /api/system` (administrator): verzija sheme i stanje pozadinskih zadataka.
- Zapisi: jedan JSON objekt po retku (`request` s `request_id`, trajanjem, korisnikom i organizacijom;
  `login_failed`, `task_failed`, `webhook_failed`, `db_integrity_problem`). Upozorenje postavite na `level=error`.

## Kapacitet

Jedan proces, SQLite u WAL načinu, niti po zahtjevu. Namijenjeno manjim timovima (desetci istodobnih korisnika,
tisuće licenci po organizaciji). Za mnogo organizacija ili visoku dostupnost: zamijenite `db.py`/repozitorije
PostgreSQL implementacijom (servisni sloj ostaje isti) i pokrenite više instanci iza load balancera
(planer tada samo na jednoj instanci).
