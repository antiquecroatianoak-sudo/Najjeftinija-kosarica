# Ulazi i izlazi – referenca za instalatere i integratore

Ovaj dokument opisuje sve što ulazi u sustav i sve što iz njega izlazi. Gornji dio je ručno napisan. Donji dio generira se iz koda (`python3 -m jezgra.referenca --upisi`), a test pada ako zaostaje za kodom.

## Instalacija u četiri naredbe

```bash
python3 -m jezgra --dijagnoza                       # što nedostaje, s točnom naredbom za svaku stavku
python3 -m jezgra --skeniraj                        # pronađi izmjenjivač, bateriju i brojilo u lokalnoj mreži
python3 -m jezgra --postavi lokacija=45.33,14.44 baterija.kapacitet_kwh=10 fotonapon.kwp=6.5
python3 -m jezgra                                   # pokreni; u pregledniku upiši kod za uparivanje
```

- `--postavi` provjerava svaku vrijednost prije upisa: tip, raspon, odnose (npr. `soc_min < soc_max`) i nepoznate ključeve, uz prijedlog ispravka. Upisuje atomski, pa se `postavke.json` ne uređuje ručno.
- Decimalni zarez je dopušten (`12,5`), kao i `da`/`ne`.
- `--postavke` ispisuje što je promijenjeno i sve važne postavke s jedinicom i rasponom.
- **Nazivni podaci:** najveća snaga punjenja i pražnjenja čita se iz izmjenjivača (SunSpec WChaMax), ali samo ako je instalater nije sam upisao. Izvor se vidi u dijagnostici (`nazivni_podaci`).

## Tok podataka u jednom koraku upravljanja (`Jezgra.korak`, svakih ~10 s)

| Korak | Ulaz | Obrada | Izlaz |
|---|---|---|---|
| Očitanje | svi uređaji (`Uredaj.citaj`) | provjera vjerodostojnosti (`ulazi.ocisti`); nedostupan uređaj ne ruši korak | očitanja; `odbacena_ocitanja`, događaj „uredaj” |
| 1. Anomalije | očitanja, stanje releja | `anomalije.Detektor`: skokovi, zaglavljeni senzori, granice baterije, pumpa | preventivno gašenje trošila (`zastita_do`), događaj „anomalija” |
| 2. Plan | SoC, prognoza (Open-Meteo ili offline model), tarifa | `optimizator.planiraj_bateriju` (DP, 36 h) i `spremnik.planiraj` (MPC) | plan po satima, raspored fleksibilnih trošila |
| 3. Otočni rad | SoC, potrošnja, sunce | kaskada niske baterije po prioritetu, zaštita vršne snage | gašenje trošila |
| 4. Pastir | naponi dionica | `pastir.Pastir`: traženje i izolacija kvara | sklopke dionica, snaga aparata |
| 5. Navodnjavanje | vlaga tla, prognoza kiše | `navodnjavanje.Navodnjavanje` | ventili zona, pumpa |
| 6. Spremnik | temperatura vode, plan, zahtjevi mreže | MPC, legionela, prednost dizalici topline | `rele_bojler`, `rele_dizalica` |
| 7. Baterija | plan, način rada, zaštite | prag šuma (najmanje 15 min), ručni način, ograničenja | `baterija_snaga_w` / `baterija_auto` / `baterija_ogranicenje` |
| 8. Zapis | sve gore | šifrirani dnevnik, satni zbroj, učenje navika | arhiva, izvještaji, API |

Svaka odluka ima zapisan razlog (`GET /api/v1/odluke`). Zaštita uvijek ima prednost pred ručnom naredbom i planom. Pastir se nikad ne gasi ručno.

## Ulazi i izlazi glavnih modula

| Modul | Ulaz | Izlaz | Napomena |
|---|---|---|---|
| `konfig.ucitaj(mapa)` | `postavke.json`, `ENERGIJA_POSTAVKE` | provjerene postavke + `_upozorenja_postavki` | neispravno se odbacuje, jezgra radi sa zadanim |
| `konfig.postavi(mapa, ["k=v"])` | dodjele s naredbenog retka | (nove postavke, upozorenja) | nedosljedan skup se ne upisuje |
| `otkrivanje.skeniraj_modbus` | hostovi, jedinice | prepoznati uređaji (SunSpec, Eastron SDM) | paralelno; poznati se preskaču |
| `SunSpecUredaj.citaj` | Modbus registri | `pv_snaga_w`, `baterija_soc`, `baterija_napon_v` | oznake „nije dostupno” → kanal se ne javlja |
| `ulazi.ocisti(o)` | sirova očitanja | (vjerodostojna, odbačena s razlogom) | granice su fizikalne, ne radne |
| `ulazi.broj(v, ime, mn, mx)` | broj iz zahtjeva | broj ili ValueError s porukom | NaN i beskonačno nikad ne prolaze |
| `optimizator.planiraj_bateriju` | SoC, cijene, sunce, potrošnja (36 h) | snaga po satima | zabrana punjenja na mrazu po satu |
| `spremnik.planiraj` | model spremnika, cijene, višak sunca, temperatura zraka | akcije po satu (dizalica/grijač) | legionela ≥ 60 °C kao ograničenje |
| `Jezgra.izvjestaj(od, do)` | arhiva | ušteda, izmjereno, pouzdanost, voda | potpisan Ed25519 (`izvjestaji.potpisi`) |
| `api_v1.obradi` | uloga, metoda, put, upit, tijelo | (status, JSON) | 400 za neispravan ulaz, nikad 500 zbog ulaza |

## Generirano iz koda

<!-- generirano: python3 -m jezgra.referenca --upisi (ne uređivati ručno ispod) -->

### Naredbeni redak (`python3 -m jezgra …`)

| Opcija | Vrijednost | Značenje |
|---|---|---|
| `--podaci` | VRIJEDNOST | podatkovna mapa (zadano ENERGIJA_PODACI ili ~/.energija) |
| `--sim` |  | simulirana farma preko Modbus/MQTT, sučelje uživo |
| `--sim-dani` | VRIJEDNOST | brza simulacija N dana i izvještaj |
| `--brzina` | VRIJEDNOST | ubrzanje vremena u --sim načinu |
| `--sezona` | jesen|ljeto|proljece|zima | godišnje doba simulacije |
| `--dinamicka` |  | dinamička satna tarifa u simulaciji |
| `--otocno` |  | bez mreže (otočni rad) |
| `--port` | VRIJEDNOST | port HTTPS sučelja (zadano api.port = 8443) |
| `--bez-tls` |  | HTTP umjesto HTTPS (samo za lokalni razvoj) |
| `--skeniraj` |  | jednom potraži uređaje u lokalnoj mreži i ispiši ih |
| `--dijagnoza` |  | provjeri je li uređaj spreman za rad (s uputama) |
| `--postavi` | KLJUC=VRIJEDNOST | provjereno upiši postavke, npr. lokacija=45.33,14.44 baterija.kapacitet_kwh=10 |
| `--postavke` |  | ispiši izmjene i važne postavke s rasponima |

### Važne postavke (`--postavi kljuc=vrijednost`)

Vrijednost izvan raspona, krivog tipa ili nepoznat ključ odbacuje se uz upozorenje (`--dijagnoza`, događaj „postavke”, `GET /api/v1/dijagnostika`); vrijedi zadana.

| Ključ | Zadano | Jedinica | Raspon | Značenje |
|---|---|---|---|---|
| `lokacija.sirina` | `45.81` | ° | -90–90 | geografska širina (prognoza sunca) |
| `lokacija.duzina` | `15.98` | ° | -180–180 | geografska dužina |
| `baterija.kapacitet_kwh` | `10.0` | kWh | 0.5–500 | korisni kapacitet baterije |
| `baterija.celija_serija` | `16` |  | 1–64 | broj ćelija u seriji (16 = 51,2 V LiFePO4) |
| `baterija.soc_min` | `0.15` | 0–1 | 0.02–0.9 | ispod ove razine samo kritična trošila |
| `baterija.soc_kriticno` | `0.07` | 0–1 | 0–0.5 | otočno: najniža razina za kritična trošila |
| `baterija.soc_max` | `0.9` | 0–1 | 0.3–1 | gornja razina punjenja |
| `baterija.max_punjenje_kw` | `3.0` | kW | 0.1–100 | najveća snaga punjenja |
| `baterija.max_praznjenje_kw` | `3.0` | kW | 0.1–100 | najveća snaga pražnjenja |
| `baterija.temp_punjenje_min_c` | `0.0` | °C | -20–15 | ispod ove temperature nema punjenja |
| `baterija.temp_max_c` | `50.0` | °C | 30–70 | iznad: preventivno smanjenje opterećenja |
| `baterija.trosak_ciklusa_eur_kwh` | `0.03` | €/kWh | 0–0.5 | procjena trošenja po kWh protoka |
| `fotonapon.kwp` | `5.0` | kWp | 0–200 | vršna snaga panela |
| `fotonapon.faktor_ucinka` | `0.8` | 0–1 | 0.3–1 | gubici sustava (kabeli, prljavština, izmjenjivač) |
| `mreza.dostupna` | `true` | da/ne | – | postoji li priključak na mrežu |
| `mreza.max_uvoz_kw` | `6.9` | kW | 0.5–200 | priključna snaga |
| `tarifa.vt_eur_kwh` | `0.16` | €/kWh | 0–2 | viša tarifa |
| `tarifa.nt_eur_kwh` | `0.08` | €/kWh | 0–2 | niža tarifa |
| `tarifa.izvoz_eur_kwh` | `0.05` | €/kWh | -1–2 | otkupna cijena |
| `tarifa.izvor_url` | `""` | URL | – | dinamička satna tarifa (prazno = VT/NT) |
| `pastir.min_kv` | `4.0` | kV | 0.5–15 | ispod: slaba ograda |
| `pastir.kvar_kv` | `1.0` | kV | 0.1–10 | ispod: kratki spoj ili prekid |
| `navodnjavanje.kisa_preskoci_mm` | `3.0` | mm | 0–50 | prognozirana kiša koja preskače zalijevanje |
| `navodnjavanje.max_minuta` | `45` | min | 1–240 | najdulje zalijevanje jedne zone |
| `navodnjavanje.pumpa_kw` | `0.75` | kW | 0.05–20 | snaga pumpe |
| `api.port` | `8443` |  | 1–65535 | port HTTPS sučelja |
| `mqtt.port` | `1883` |  | 1–65535 | port lokalnog MQTT brokera |
| `spremnik.volumen_l` | `150.0` | l | 10–2000 | volumen spremnika tople vode |
| `spremnik.t_min_c` | `45.0` | °C | 35–55 | najniža temperatura tople vode |
| `spremnik.dizalica_kw` | `0.5` | kW | 0–10 | električna snaga dizalice topline (0 = nema je) |
| `spremnik.dt_max_c` | `55.0` | °C | 40–65 | najviša temperatura koju postiže dizalica |
| `spremnik.grijac_kw` | `2.0` | kW | 0.3–12 | snaga električnog grijača |
| `spremnik.grijac_max_c` | `65.0` | °C | 60–80 | najviša temperatura grijača |
| `spremnik.legionela.period_dana` | `7.0` | dana | 1–14 | razmak ciklusa protiv legionele |
| `spremnik.legionela.cilj_c` | `62.0` | °C | 60–75 | temperatura ciklusa (najmanje 60 °C) |
| `otkrivanje.lan_skeniranje` | `true` | da/ne | – | sam traži Modbus uređaje u lokalnoj mreži |
| `politika.izvoz_iz_baterije` | `true` | da/ne | – | smije li baterija prodavati u mrežu |

Odnosi koji moraju vrijediti (inače se ti ključevi vraćaju na zadano):

- mora vrijediti soc_kriticno < soc_min < soc_max
- mora vrijediti pastir.kvar_kv < pastir.min_kv
- mora vrijediti spremnik.t_min_c < grijac_max_c i legionela.cilj_c ≤ grijac_max_c

Popisi kojima se provjerava i sadržaj: `otkrivanje.lan_mreze`, `otkrivanje.modbus_hostovi`, `otkrivanje.lan_portovi`, `otkrivanje.modbus_jedinice`, `api.cors_izvori`, `kopije.odredista`.

### API v1 (HTTPS, token iz uparivanja; puna shema: `GET /api/v1/openapi.json`)

| Metoda | Put | Opseg | Opis |
|---|---|---|---|
| GET | `/api/v1/sustav` | citanje | Identitet, uloga pozivatelja, mogućnosti i dostupne serije |
| GET | `/api/v1/pregled` | citanje | Sažetak za stanare (jedan zaslon) |
| GET | `/api/v1/tok` | citanje | Trenutni tokovi energije |
| GET | `/api/v1/povijest` | citanje | Vremenske serije: ?serije=pv_w,potrosnja_w&raspon=24h[&korak=s] |
| GET | `/api/v1/usteda` | citanje | Ušteda (procjena prema osnovici) po razdobljima i po danima |
| GET | `/api/v1/bojler` | citanje | Bojler: temperatura, grijanje, plan |
| GET | `/api/v1/solar` | citanje | Sunčani paneli: snaga, dnevna proizvodnja, učinak |
| GET | `/api/v1/baterija` | citanje | Baterija: napunjenost, snaga, zdravlje |
| GET | `/api/v1/pastir` | citanje | Električni pastir po dionicama |
| GET | `/api/v1/navodnjavanje` | citanje | Zone, vlaga, odluke |
| GET | `/api/v1/odluke` | citanje | Pokazatelji automatike: što sustav radi i zašto |
| GET | `/api/v1/izvjestaj` | citanje | Potpisani izvještaj: ?dana=7 |
| POST | `/api/v1/naredbe` | naredbe | Naredbe: {akcija: topla_voda_sada} (stanar) \| {akcija: trosilo, trosilo, ukljuci, minuta} (administrator) |
| GET | `/api/v1/dijagnostika` | dijagnostika | Kontrolni centar: uređaji, zadaci, resursi, AI, dnevnik, kopije |
| GET | `/api/v1/dogadjaji` | dijagnostika | Zadnji događaji: ?sati=24 |
| POST | `/api/v1/otkrivanje` | upravljanje | Potraži uređaje odmah (lokalna mreža i poznati Modbus hostovi) |
| GET | `/api/v1/postavke` | upravljanje | Napredne postavke |
| POST | `/api/v1/postavke` | upravljanje | Ručno premošćivanje (sigurnosne granice ostaju) |
| GET | `/api/v1/fleksibilnost` | mreza | Dostupna fleksibilnost za mrežu (W, h) |
| GET | `/api/v1/mreza/zahtjevi` | mreza | Aktivni zahtjevi mreže |
| POST | `/api/v1/mreza/zahtjevi` | mreza | Novi zahtjev: {vrsta: ogranici_uvoz\|ogranici_izvoz\|povecaj_potrosnju, snaga_w, od, do, izvor} |
| DELETE | `/api/v1/mreza/zahtjevi` | mreza | Opoziv: ?id= |

Uloge i opsezi: **stanar**: citanje, naredbe; **integracija**: citanje, mreza; **administrator**: citanje, dijagnostika, mreza, naredbe, upravljanje.

Neispravan ulaz (tijelo koje nije JSON objekt, broj izvan raspona, NaN) vraća **400** s porukom; nepoznat put 404, kriva metoda 405, nedovoljna uloga 403.

### Ulazi s uređaja (očitanja)

Očitanje izvan fizikalnog raspona, NaN/beskonačno ili SunSpec oznaka „nije dostupno” se odbacuje (kao da kanal nije javljen) i prikazuje u dijagnostici (`odbacena_ocitanja`).

| Kanal | Jedinica | Fizikalni raspon | Značenje |
|---|---|---|---|
| `pv_snaga_w` | W | -200 … 200000 | snaga sunčanih panela |
| `potrosnja_w` | W | konačan broj | ukupna potrošnja |
| `mreza_snaga_w` | W | -200000 … 200000 | snaga na priključku (+ uvoz) |
| `mreza_prisutna` | 0/1 | 0 … 1 | ima li mrežnog napona |
| `mreza_uvoz_kwh` | kWh | 0 … 1e+09 | brojilo: uvoz (ukupno) |
| `mreza_izvoz_kwh` | kWh | 0 … 1e+09 | brojilo: izvoz (ukupno) |
| `baterija_soc` | 0–1 | 0 … 1.05 | napunjenost baterije |
| `baterija_napon_v` | V | 0 … 1500 | napon baterije |
| `baterija_struja_a` | A | -2000 … 2000 | struja baterije (+ punjenje) |
| `baterija_snaga_w` | W | -200000 … 200000 | snaga baterije |
| `baterija_temp_c` | °C | -50 … 130 | temperatura baterije |
| `okolina_temp_c` | °C | -50 … 130 | vanjska temperatura |
| `bojler_temp_c` | °C | -50 … 130 | temperatura vode u spremniku |
| `bojler_snaga_w` | W | -200000 … 200000 | snaga grijača |
| `dizalica_snaga_w` | W | -200000 … 200000 | snaga dizalice topline |
| `pumpa_struja_a` | A | -2000 … 2000 | struja pumpe (rad na suho, blokada) |
| `tlo_<zona>_vlaga` | % | 0 … 100 | vlaga tla po zoni |
| `pastir_v<k>_kv` | kV | 0 … 25 | napon ograde na kraju dionice k (v0 = aparat) |
| `pastir_baterija_soc` | 0–1 | 0 … 1.05 | baterija aparata pastira |
| `brojilo_impulsi` | broj | konačan broj | LED impulsi brojila (optički adapter) |

### Izlazi prema uređajima (naredbe)

| Kanal | Vrijednost | Značenje |
|---|---|---|
| `baterija_snaga_w` | W, + punjenje / − pražnjenje | ručna ili planirana snaga baterije (SunSpec 124 InWRte/OutWRte) |
| `baterija_auto` | 1 | izmjenjivač u vlastitom načinu rada (StorCtl_Mod = 0) |
| `baterija_ogranicenje` | bitovi 1 = bez punjenja, 2 = bez pražnjenja | zabrana punjenja/pražnjenja (mraz, prenapon) |
| `izvoz_zabranjen` | 0/1 | zabrana izvoza u mrežu |
| `rele_bojler` | 0/1 | električni grijač spremnika |
| `rele_dizalica` | 0/1 | dizalica topline (PTV) |
| `rele_pumpa` | 0/1 | pumpa za navodnjavanje |
| `rele_uticnice` | 0/1 | utičnice (nekritično) |
| `rele_hladnjak` | 0/1 | hladnjak |
| `ventil_<zona>` | 0/1 | ventil zone navodnjavanja |
| `pastir_snaga` | 0–1 | udio snage aparata električnog pastira |
| `rele_pastir_k<k>` | 0/1 | sklopka dionice ograde k (izolacija kvara) |
| `rele_pastir_povrat` | 0/1 | povratni vod ograde (prsten) |
| `rele_pastir_punjenje` | 0/1 | punjenje baterije aparata pastira |

<!-- kraj generiranog dijela -->
