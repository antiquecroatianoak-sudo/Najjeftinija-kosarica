# API i integracije

Svi pozivi: HTTPS, `Authorization: Basic …` (korisnik) ; promjene dodatno `X-Requested-With: LicensePulse`
i `Content-Type: application/json`. Pogreške: `{"error": {"code", "message", "fields"?}}`; svaki odgovor ima `X-Request-Id`.

## Licence
| | |
|---|---|
| `GET /api/licenses?status=&category=&q=&expiring=30&tracked=1` | popis (s korištenjem, sljedećom obnovom, iznosom u referentnoj valuti) |
| `POST /api/licenses` · `GET/PUT/PATCH/DELETE /api/licenses/{id}` | CRUD |
| `GET /api/dashboard?days=30` · `GET /api/analytics` | pregled, ROI, prognoza, pregovori |
| `GET /api/export.csv?…` | izvoz (iste filtre) |
| `POST /api/import/preview` · `POST /api/import/commit` | `{filename, content_base64, mapping, defaults, skip_invalid, skip_duplicates}` |

Polja licence: `name, category, cost` (po ciklusu), `currency` (ISO 4217), `billing_cycle` (`monthly|quarterly|yearly`),
`start_date` (GGGG-MM-DD), `status` (`active|inactive|cancelled`), `usage_key` (neobavezno), `auto_status` (bool).

## Praćenje korištenja (SSO / sustavi prijava)

Administrator izradi token (Postavke → API tokeni ili `create-token`). Zatim:

```bash
curl -X POST https://licence.tvrtka.hr/api/usage \
  -H "Authorization: Bearer lp_…" -H "Content-Type: application/json" \
  -d '{"events":[{"license":"slack","user":"ana@tvrtka.hr","at":"2026-11-12T08:30:00Z"}]}'
```

`license` = `usage_key` licence (ili njen id); do 1000 događaja po pozivu; `at` neobavezno (zadano sada).
Odgovor `202`: `{accepted, unknown, errors, reactivated}`. Token vrijedi samo za ovaj endpoint.

Tipični izvori: dnevnik prijava SSO-a (Okta System Log, Microsoft Entra sign-in logs, Google Workspace login audit)
putem njihovih event hookova ili periodične skripte koja prosljeđuje događaj „korisnik X prijavio se u aplikaciju Y”.
Mapiranje aplikacije SSO-a na `usage_key` radi skripta. Bez integracije status se može mijenjati i ručno.

## Webhookovi

Događaji: `license.created|updated|deleted|expiring|auto_inactive|reactivated`, `bank.matched`, `bank.unmatched_recurring`, `ping`.

```
POST <vaš URL>
X-LicensePulse-Event: license.expiring
X-LicensePulse-Delivery: 42
X-LicensePulse-Timestamp: 1762934400
X-LicensePulse-Signature: sha256=<hex HMAC-SHA256(secret, timestamp + "." + body)>

{"event": "license.expiring", "organization_id": "...", "occurred_at": "...", "data": {...}}
```

Provjera (Python):
```python
expected = "sha256=" + hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
ok = hmac.compare_digest(expected, signature) and abs(time.time() - int(ts)) < 300
```

Odgovor 2xx = isporučeno. Inače ponovni pokušaji nakon 1 min, 5 min, 30 min, 2 h, 6 h, zatim `failed` (vidljivo u Postavkama → Isporuke).

## Ostalo
`GET /api/me` · `PATCH /api/organization` · `POST /api/me/password` · `GET/POST/DELETE /api/users` · `GET/POST/DELETE /api/tokens` ·
`GET/POST/DELETE /api/webhooks`, `…/{id}/deliveries`, `…/{id}/test` · `GET /api/rates`, `PUT/DELETE /api/rates/{CUR}`, `POST /api/rates/refresh` ·
`GET /api/notifications`, `POST /api/notifications/read` · `POST /api/bank/import`, `GET /api/bank/transactions?status=`,
`POST /api/bank/transactions/{id}` (`{action: match|ignore|reset, license_id}`), `GET /api/bank/insights` · `GET /api/audit` · `GET /api/system` · `GET /api/health`.
