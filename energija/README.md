# Energija – hibridni sustav upravljanja energijom (prototip)

Zaseban projekt u ovom repozitoriju; **nije dio aplikacije Najjeftinija košarica** i ne spaja se s njom.
Namijenjen je vikendicama i poljoprivrednim zemljištima: solarni paneli, baterija, bojler, pumpa za
navodnjavanje i električni pastir. Lokalna jezgra sve kritične odluke donosi sama, bez interneta.

Stanje: **radni prototip, provjeren u simulaciji.** Na stvarnom hardveru nije pokretan (vidi `STANJE.md`).

## Brzi početak

```bash
cd energija
pip install -r requirements.txt          # jedina ovisnost: cryptography

# 1) brza simulacija 7 dana (bez mreže) -> potpisani izvještaj u <podaci>/izvjestaji/
python3 -m jezgra --sim-dani 7 --podaci /tmp/energija --sezona zima --dinamicka

# 2) živa simulacija preko stvarnih protokola (Modbus TCP + MQTT) i sučelje
python3 -m jezgra --sim --brzina 60 --podaci /tmp/energija-uzivo
#    otvori https://localhost:8443/ i upiši kod za uparivanje ispisan u konzoli

# 3) testovi
python3 -m unittest discover -s testovi -p "test_*.py"
```

Na uređaju (Raspberry Pi ili sličan): `docker compose -f kontejneri/compose.yaml up -d`.

## Izolirana provjera cijelog sustava

Provjera bez stvarnog hardvera i bez interneta obuhvaća:

- simulirane Modbus uređaje na **pymodbusu**: SunSpec izmjenjivač/bateriju (jedinica 1) i Eastron SDM brojilo (jedinica 2),
- MQTT senzore tla i ograde,
- **lažni Open‑Meteo**,
- stvarnu sliku jezgre.

Provjera `provjera/provjera_sustava.py` prolazi 15 koraka (16 u Composeu) i završava izlaznim kodom. Koraci uključuju:

- TLS uz strogu provjeru i uparivanje,
- automatsko prepoznavanje uređaja,
- prognozu iz lažnog Open‑Meteo,
- upis ručne snage baterije koji preko Modbusa stiže do izmjenjivača,
- MQTT naredbu releju,
- odbijanje ručnog gašenja pastira,
- potpis izvještaja,
- mjerenje memorije za AI,
- u Composeu i dokaz da mreža nema izlaz na internet.

```bash
pip install -r requirements-provjera.txt                 # + pymodbus 3.8.6
python3 -m unittest discover -s testovi -p "test_*.py"   # uključuje mokove Open-Meteo i pymodbus interop
bash provjera/pokreni_lokalno.sh                         # ista topologija kao lokalni procesi
docker compose -f kontejneri/compose.provjera.yaml up --build --abort-on-container-exit --exit-code-from provjera
docker compose -f kontejneri/compose.provjera.yaml down -v
```

Na GitHubu to automatski radi `.github/workflows/energija-provjera.yml`, samo kad se mijenja `energija/`.
Simulator i lažni servis mogu se pokrenuti i zasebno:

- `python3 -m simulator.modbus_pymodbus --modbus-port 5020 --mqtt-host <jezgra>`
- `python3 -m simulator.mock_openmeteo --port 8080` (opcija `--kvar N` vraća 503 na prvih N zahtjeva).

## Automatizirani scenariji i učenje politike

Scenariji koriste isti fizikalni simulator s ubačenim kvarovima. Mrežni pozivi idu stvarnim kodom jezgre, uz mokirani `urlopen`. U svakom koraku čuvar provjerava sigurnosne invarijante.

```bash
python3 -m scenariji.pokretac --oznaka brzi            # brzi podskup (CI)
python3 -m scenariji.pokretac --izlaz rezultati/       # svi scenariji -> rezultati.json, rezultati.md
python3 -m scenariji.ucenje_politike --izlaz naucena_politika.json
python3 -m scenariji.pokretac --postavke naucena_politika.json   # svi scenariji s naučenom politikom
```

- **Katalog:** `scenariji/katalog.py` – vrijeme, tarifa, rad s mrežom ili bez nje, kvarovi, ispadi uređaja i mreže, očekivanja.
- **Učenje:** `cuvanje_faktor`, `rezerva_dodatak` i `trosak_ciklusa_plan` uče se na skupu za učenje. Naučena politika predlaže se samo ako je bolja na odvojenim tjednima i bez ijednog sigurnosnog kršenja. Primjenjuje se dodavanjem odjeljka `"politika"` u `postavke.json` na uređaju.
- **Spremnost:** što je automatski dokazano, a što se mora provjeriti na terenu, opisano je u `SPREMNOST.md`.

## Što radi

| Područje | Gdje | Ukratko |
|---|---|---|
| Nulta konfiguracija, plug-and-play | `otkrivanje.py`, `uredjaji.py` | UDP multicast najava, MQTT najave (vlastite i Home Assistant), Modbus skeniranje s prepoznavanjem SunSpec izmjenjivača/baterija i Eastron brojila |
| Lokalni certifikati | `certifikati.py` | vlastiti CA, automatsko izdavanje i obnova, HTTPS bez podešavanja; korisnik jednom potvrdi otisak |
| Enkripcija | `sifra.py` | AES-256-GCM za podatke, X25519 + Ed25519 za dvosmjerne sesije, potpisi izvještaja |
| Redundancija i oporavak | `pohrana.py`, `kopije.py`, `nadzor.py` | šifrirani dnevnik s odrezivanjem oštećenog repa, snimke u dvije generacije, kopije na USB/NAS uz provjeru, sigurno stanje i ponovno pokretanje |
| Sigurni tunel | `tunel.py` | kraj-do-kraja šifriran; izravno u LAN-u ili preko releja bez otvaranja portova |
| Univerzalni adapter brojila | `impulsi.py` | optičko čitanje LED impulsa sa samoniveliranjem; konstanta brojila se kalibrira sama |
| Prognoza i tarife | `prognoza.py`, `tarife.py` | Open-Meteo ili offline model vedrog neba; dinamička tarifa ili VT/NT |
| Optimizacija | `optimizator.py`, `ucenje.py`, `rubni_ai.py` | plan baterije (dinamičko programiranje), fleksibilna trošila u najjeftinije sate, učenje navika, kvantizirani rubni AI |
| Anomalije i prediktivno održavanje | `anomalije.py` | skokovi, zaglavljeni senzori, granice baterije, rad pumpe na suho, trendovi do praga |
| Električni pastir | `pastir.py` | prepoznavanje kratkog spoja, prekida i vegetacije; binarno traženje kvara, izolacija i napajanje kroz povratni vod |
| Navodnjavanje | `navodnjavanje.py` | vlaga tla po zonama, preskakanje zbog kiše, višak sunca, sigurni raspored kad senzor zakaže |
| Izvještaji | `izvjestaji.py` | HTML/JSON/CSV, potpisani i provjerljivi, s uštedom u odnosu na osnovicu |
| Sučelje | `sucelje/` | ušteda, tok energije, baterija, ograda, zone, plan za 36 h, „Zašto sustav ovo radi”, napredne postavke |

## Rubni AI ukratko

- Kvantizirani linearni model (int8, 11 B težina, 10 množenja) ispravlja naučeni profil navika.
- Prije uključivanja, i zatim svaki sat, mjeri slobodnu memoriju (sustav i cgroup) i opterećenje CPU‑a. Ako uvjeti nisu ispunjeni, ne uključuje se, a razlog se vidi u sučelju.
- Koristi se tek kad je na zadnjih 168 h barem 5 % točniji od profila navika.
- Bateriju i dalje vodi optimizator, uz sve sigurnosne granice.
- Ručno premošćivanje je u naprednim postavkama: AI se može uključiti ili isključiti, a za bateriju se može odabrati automatski način, samo vlastita potrošnja, zabrana punjenja iz mreže ili ručna snaga s istekom. Granice napona, temperature i napunjenosti te zaštita pastira ne mogu se isključiti.
