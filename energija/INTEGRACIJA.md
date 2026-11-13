# Integracija: API v1, komponente sučelja, pametna mreža i kućna automatika

Sustav je modularan. Isti, verzionirani API koriste vlastito sučelje, komponente ugrađene u tuđe stranice,
kućna automatika i operatori mreže. Specifikacija se generira iz koda i ne može odstupati od njega:
`GET /api/v1/openapi.json` (OpenAPI 3.1).

## 1. Pristup i uloge

| Uloga | Opsezi | Za koga |
|---|---|---|
| `stanar` | čitanje, naredbe (npr. „zagrij vodu odmah”) | mobitel ukućana |
| `integracija` | čitanje, mreža (fleksibilnost, zahtjevi) | operator mreže, agregator, kućna automatika |
| `administrator` | sve, uključujući dijagnostiku i upravljanje | vlasnik, serviser |

- **Prvo uparivanje:** kod s kućišta ili konzole daje ulogu administratora (vrijedi 15 min, jednokratan je).
- **Ostali pristupi:** administrator izdaje jednokratne pozivnice za druge uloge. Kod vrijedi 1 h:
  `POST /api/v1/pristup/pozivnice {"uloga": "stanar"}` → `{"kod": "12345678"}`.
- **Uparivanje:** `POST /api/v1/upari {"kod": "…", "ime": "…"}` → `{"token", "uloga"}`.
- **Token** se šalje u zaglavlju `Authorization: Bearer …` ili kao kolačić `energija`. U bazi se čuva samo njegov SHA‑256.
- **Pristup s drugih domena (CORS)** je zadano isključen. Uključuje se u `postavke.json`:
  `{"api": {"cors_izvori": ["https://portal.primjer"]}}`.

## 2. Resursi (svi `GET`, osim gdje piše drukčije)

| Put | Sadržaj |
|---|---|
| `/api/v1/sustav` | identitet, verzija API‑ja, uloga pozivatelja, mogućnosti, popis vremenskih serija |
| `/api/v1/pregled` | sve za jednostavni zaslon stanara u jednom pozivu |
| `/api/v1/tok` | trenutni tokovi energije (W) |
| `/api/v1/povijest?serije=pv_w,potrosnja_w&raspon=24h` | vremenske serije (`1h`, `6h`, `24h`, `48h`, `7d`, `30d`) |
| `/api/v1/usteda?dana=30` | ušteda po razdobljima i po danima (procjena prema osnovici) |
| `/api/v1/bojler`, `/solar`, `/baterija`, `/pastir`, `/navodnjavanje` | detalji podsustava |
| `/api/v1/odluke` | pokazatelji automatike: što radi, zašto i na temelju čega |
| `/api/v1/izvjestaj?dana=7` | potpisani izvještaj (Ed25519) |
| `POST /api/v1/naredbe` | `{"akcija": "topla_voda_sada"}` (stanar) · `{"akcija": "trosilo", "trosilo": "bojler", "ukljuci": true, "minuta": 30}` (administrator) |
| `/api/v1/dijagnostika`, `/api/v1/dogadjaji?sati=24` | kontrolni centar (administrator) |
| `GET`/`POST /api/v1/postavke` | napredne postavke i ručno premošćivanje (administrator) |
| `/api/v1/uzivo` | Server‑Sent Events, događaj `stanje` svake 2 s (token u kolačiću ili kao `?token=`) |

**Vremenske serije:**
- dostupne: `pv_w`, `pv_prognoza_w`, `potrosnja_w`, `mreza_w`, `baterija_w`, `baterija_soc`, `cijena_eur_kwh`, `bojler_w`, `bojler_temp_c`, `okolina_temp_c`, `pumpa_w`, `pastir_v<k>_kv`, `tlo_<zona>_vlaga`;
- zadnjih 48 h u minutnoj razlučivosti, a dulje samo serije iz satnih zapisa.

**Konvencije:**
- vremena u UNIX sekundama, snage u W, energija u kWh, novac u EUR;
- nepoznata polja klijent smije zanemariti, pa nova polja ne kvare postojeće klijente;
- greške se vraćaju kao `{"greska": "…"}` sa statusom 400, 401, 403, 404 ili 405.

## 3. Pametna mreža (uloga `integracija` ili `administrator`)

- `GET /api/v1/fleksibilnost`: koliko sustav sada može smanjiti uvoz ili povećati potrošnju (W) i koliko dugo (h), po izvorima (baterija, bojler, trenutna fleksibilna trošila).
- `POST /api/v1/mreza/zahtjevi`: zahtjev operatora ili agregatora. Tijelo je `{"vrsta": "ogranici_uvoz" | "ogranici_izvoz" | "povecaj_potrosnju", "snaga_w": 500, "od": t, "do": t, "izvor": "DSO"}`, a trajanje je najviše 24 h. Jezgra:
  - kod ograničenja uvoza prazni bateriju i odgađa bojler i pumpu;
  - kod ograničenja izvoza puni bateriju, a kod granice 0 W ograničava panele;
  - kod povećanja potrošnje puni bateriju i grije bojler.
- `DELETE /api/v1/mreza/zahtjevi?id=…`: opoziv zahtjeva.
- **Prioriteti:** sigurnosne granice (napunjenost, temperatura i napon baterije) i zaštita pastira uvijek imaju prednost pred zahtjevom mreže. Zahtjev ima prednost pred optimizacijom troška. Svaki zahtjev vidi se u odlukama i događajima.
- Model je blizak OpenADR‑u: posrednik ili pristupnik prevodi signale operatora u ove pozive. Sam OpenADR nije implementiran.

## 4. Kućna automatika (MQTT, Home Assistant)

- Jezgra na svoj broker objavljuje zadržane poruke `energija/stanje/<ključ>` svakih 30 s: `pv_w`, `potrosnja_w`, `mreza_w`, `baterija_w`, `baterija_soc`, `bojler_temp_c`, `cijena_eur_kwh`, `usteda_mjesec_eur`, `pastir`.
- **Home Assistant MQTT discovery:** HA sam prepozna senzore s jedinicama i klasama uređaja, kao i gumb „Zagrij vodu odmah” (`energija/naredbe/topla_voda` = `ON`).

## 5. Komponente sučelja (Web Components)

```html
<script type="module" src="https://<jezgra>/komponente/komponente.js"></script>
<e-usteda api="https://<jezgra>" token="…" prikaz="jednostavno"></e-usteda>
<e-bojler api="https://<jezgra>" token="…" raspon="24h"></e-bojler>
```

**Popis komponenti:**

| Komponenta | Što prikazuje |
|---|---|
| `e-usteda` | ušteda; u naprednom prikazu i stupci po danima |
| `e-tok` | tok energije uživo |
| `e-energija` | potrošnja, sunce i mreža kroz vrijeme |
| `e-baterija` | napunjenost i noćna rezerva |
| `e-bojler` | temperatura i grijač kao dva grafikona s istom vremenskom osi; gumb „Zagrij vodu odmah” |
| `e-solar` | proizvodnja prema prognozi |
| `e-pastir` | dionice ograde, napon i prag |
| `e-navodnjavanje` | zone, vlaga i prag |
| `e-status` | pokazatelji automatike |
| `e-odluke` | što automatika radi i zašto |
| `e-dijagnostika` | dijagnostika (administrator) |
| `e-upravljanje` | upravljanje (administrator) |

**Atributi:**
- `api`, `token`;
- `prikaz="jednostavno|napredno"`;
- `raspon="1h|6h|24h|48h|7d|30d"`;
- `tema="svijetla|tamna"` (bez atributa tema prati sustav).

**Izgled:**
- CSS varijable `--e-povrsina`, `--e-pozadina`, `--e-tekst`, `--e-tekst-2`, `--e-tekst-3`, `--e-rub`, `--e-naglasak`, `--e-serija-1…4`, `--e-radijus`, `--e-font` prolaze kroz shadow DOM.
- Tko mijenja podlogu, neka promijeni i boje teksta ili postavi `tema`, inače kontrast nije zajamčen.

**Događaji:** `e-greska` (`detail: {status, poruka}`); npr. kod statusa 401 domaćin prikaže uparivanje.

**SDK bez komponenti:**
- `import { EnergijaKlijent } from ".../sdk/energija-sdk.js"`;
- metode `pregled()`, `povijest()`, `uzivo(fn)` …;
- komponente na istoj stranici dijele jednu SSE vezu i jednu predmemoriju.

**Grafikoni** (`komponente/graf.js`):
- jedna os Y; dvije veličine uvijek kao dva grafikona;
- validirana paleta za CVD i obje teme;
- izravne oznake, pratilica s oblačićem, upravljanje tipkovnicom;
- svaki grafikon ima i prikaz u obliku tablice.

Primjer ugradnje: `sucelje/primjer-ugradnje.html`.
