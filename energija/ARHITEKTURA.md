# Arhitektura

## 1. Slojevi

```
 senzori / uređaji ──(Modbus TCP·RTU, MQTT, impulsni adapter, GPIO)──┐
                                                                     ▼
 ┌──────────────────────── LOKALNA JEZGRA (radi bez interneta) ────────────────────────┐
 │ otkrivanje → očitanja → ZAŠTITA (anomalije, granice) → pastir → navodnjavanje →      │
 │ plan (tarife + prognoza + navike + rubni AI) → naredbe → šifrirani dnevnik/snimka    │
 │ nadzornik (watchdog, sigurno stanje) · lokalni CA · HTTPS sučelje · LAN P2P tunel    │
 └───────────────┬───────────────────────────────┬──────────────────────────────────────┘
                 │ šifrirane kopije (USB/NAS)     │ samo izlazne veze, kraj-do-kraja šifrirano
                 ▼                                ▼
          sekundarni medij              oblak: sinkronizacija (vidi samo šifrirani tekst),
                                        relej tunela, izvještaji
```

Zaštita uvijek ima prednost pred optimizacijom. Ručna naredba ne nadjačava zaštitu. Pastir se ne
isključuje radi štednje niti ručno.

## 2. Hardver: lokalna obrada uz minimalan utjecaj na bateriju

| Komponenta | Preporuka | Tipična potrošnja | Zašto |
|---|---|---|---|
| Računalo jezgre | Raspberry Pi Zero 2 W ili CM4 (2 GB) / ekvivalentan ARM SBC | 0,6–2,5 W | jezgra zauzima ~40 MB RSS; dovoljno je 512 MB RAM-a |
| Pohrana | industrijska microSD (pSLC) ili eMMC + USB stick za kopije | – | dnevnik grupira fsync (manje trošenja); kopije su odvojene |
| Hardverski watchdog | ugrađeni BCM watchdog + systemd `WatchdogSec` | – | `nadzor.sd_notify` šalje `WATCHDOG=1` samo dok kritični zadaci rade |
| RS-485 | izolirani USB/HAT pretvarač | 0,1 W | Modbus RTU za izmjenjivače i BMS (isti PDU kao TCP) |
| Senzori tla, napona ograde, releji | ESP32-C3 s MQTT (deep sleep), ili LoRa → MQTT pristupnik | 10–50 µA u snu | baterijski senzori rade godinama; samo najave i promjene |
| Mjerač napona ograde | visokonaponski djelitelj + vršni detektor na mikrokontroleru | < 1 mA | šalje kV po dionici svakih 10–60 s |
| Sklopke ograde | releji za visoki napon impulsa (sekcijski prekidači) | 0 W u mirovanju (bistabilni) | izolacija dionica i povratni vod |
| Impulsni adapter | fototranzistor + MCU s komparatorom (prekid) | ~1 mA | detekcija na MCU-u; jezgri šalje samo zbroj impulsa |
| Radio | Wi-Fi samo prema potrebi; LTE modem uključuje jezgra | 0,5–2 W kad radi | u KRITIČNOM načinu radio radi minimalno |

**Energetski proračun (procjena, nije izmjereno):** jezgra na Pi Zero 2 W uz Wi‑Fi troši oko 1 W, odnosno ~24 Wh dnevno. Kod baterije od 10 kWh to je 0,24 % kapaciteta na dan. Aparat pastira (8 W) ima vlastitu malu bateriju, koju jezgra puni iz glavne samo iz viška sunca ili kad joj prijeti pražnjenje.

**Pragovi rada** (`resursi.py`):

| Način | Uvjet | Što se mijenja |
|---|---|---|
| KRITIČNO | SoC ≤ naučena rezerva | samo zaštita i pastir; rijetko uzorkovanje |
| ŠTEDNO | SoC < rezerva + 10 %, zauzet CPU ili temperatura CPU‑a > 75 °C | rjeđi intervali |
| PRILIKA | višak sunca | teški poslovi (učenje, kopije, izvještaji) |

## 3. Privatnost

- Glavni ključ nastaje na uređaju i nikad ga ne napušta.
- Oblak prima samo šifrirane pakete potpisane ključem jezgre.
- Postavke iz oblaka prihvaćaju se samo s potpisom vlasnika, a zaštićene granice (baterija, pastir) iz oblaka se uopće ne mogu mijenjati.
- Tunel ne otvara ljusku, nego samo API jezgre.

## 4. Kontejneri

`kontejneri/compose.yaml`: jezgra s ograničenjima (160 MB, 1 CPU, 128 procesa), datotečni sustav samo za čitanje, bez Linux sposobnosti (capabilities), `restart: always`. Relej za tunel je zasebna slika za VPS. Za veće instalacije predviđen je Mosquitto umjesto ugrađenog brokera, uz isti protokol.

## 5. Poznata ograničenja prototipa

- Izravni P2P preko interneta (UDP hole punching) nije implementiran; izvan LAN‑a promet ide preko releja, i dalje kraj‑do‑kraja šifriran.
- Ugrađeni MQTT broker podržava samo QoS 0/1, bez trajnih sesija.
- Modbus RTU (serijski) nije implementiran; PDU je isti kao kod TCP‑a.
- Relej nema vlastiti TLS u zadanoj slici. Promet je ipak šifriran kraj‑do‑kraja, a TLS se dodaje parametrom `ssl_kontekst`.
- Ušteda u izvještaju je modelska procjena u odnosu na osnovicu „isti uređaji bez upravljanja”.
