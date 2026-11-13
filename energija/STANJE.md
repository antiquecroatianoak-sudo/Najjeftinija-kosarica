# Energija – zapis stanja

## 13.11.2026. (Europe/Zagreb) – značajnost prema konkurenciji: unaprijed zadani kriterij i dvije neovisne ocjene

- **Kriterij:** zadan prije analize (`KRITERIJ_ZNACAJNOSTI.md`, commit `c049e77`) i dopunjen K1‑R prije 2. ocjene (`9dee073`).
- **Razvojni katalog:** DJELOMIČNO. K2 ispunjen; K1 medijan +17 p.b., ali p = 0,0625 (samo 9 scenarija).
- **1. neovisna ocjena (2027., 26 tjedana, `e5ae978`):** DJELOMIČNO.
  - K1 nije ispunjen: medijan −3,3 p.b., p = 0,75. VT/NT tjedni: velika prednost (+45 do +100 p.b.); obična dinamička tarifa: pravilo cjenovnog praga bolje u 11 od 13 tjedana.
  - K2 ispunjen.
- **Pokus isključivanja (razvojni tjedni 2026.):** konkurentova prednost u trošku dolazi od lošije usluge tople vode (oko 17 h tjedno bez nje). Uz jednako pravilo za bojler naše upravljanje je 8 % jeftinije.
- **2. neovisna ocjena (2028., 26 tjedana, `rezultati/evaluacija2/`):** DJELOMIČNO.
  - K1 (konkurenti kakvi jesu): nije ispunjen, medijan −12,6 p.b., p = 0,87.
  - K1‑R (jednaka usluga tople vode): trošak značajno bolji, medijan +16,5 p.b., 19 bolje / 4 lošije, p = 0,0013.
  - K2 u K1‑R načinu nije ispunjen: 154 i 284 min bez tople vode u dva dinamička tjedna (svibanj, lipanj), dok konkurenti s našim pravilom za bojler imaju 0.
- **Zaključak:** optimizacija **nije** proglašena uspješnom ni nakon druge ocjene. Upravljanje energijom uz jednaku uslugu značajno nadmašuje referentne strategije, ali je otkriven propust u udobnosti tople vode. Skup 2028. je sada iskorišten; za iduću ocjenu treba novi neovisni skup, zadan prije popravka.
- **Otvoreno:** zašto naše upravljanje baterijom ili izvozom ometa toplu vodu u dijelu dinamičkih tjedana. Istražuje se samo na razvojnim tjednima.


## 13.11.2026. 09:27 CET (Europe/Zagreb) – usporedba s tržišnim pristupima, ekstremni scenariji, optimizacija

### Dogovoreno (vlasnik, 12.–13.11.2026.)
- Automatizirani scenariji na simulatorima (Modbus, mrežni pozivi) uz ekstremne vremenske i cjenovne uvjete.
- Usporedba s vodećim pristupima na tržištu i optimizacija dok sustav ne bude vrhunski.

### Važno ograničenje usporedbe
Rezultati zatvorenih komercijalnih aplikacija pod jednakim uvjetima nisu dostupni. Zato se uspoređuje s **referentnim strategijama** (tipično ponašanje tržišnih sustava) i s **procjenom teorijske granice**, a ne s imenovanim proizvodima. Metodologija je opisana u `USPOREDBA.md`.

### Rezultat (commit `b37f749`, `rezultati/usporedba.md`)
- Višekriterijska ocjena (trošak, topla voda, stres biljaka, ograda, neisporučeno): **nenadmašena u 17 od 18 scenarija, od toga dominira u 14**.
- Jedini scenarij gdje je nadmašena, `nenajavljena_naoblaka`: pravilo cjenovnog praga je 0,04 € jeftinije. Razlika dolazi iz vrednovanja energije koja ostane u bateriji na kraju razdoblja; tijekom tjedna smo bolji noću, a pravilo praga danju. Popravak kratkoročnom korekcijom prognoze isproban je i odbačen jer je pogoršao rezultate.
- Kompromisi:
  - zima s dinamičkom tarifom: 0,24 € skuplje od pravila praga, ali s više tople vode i pouzdanijom ogradom; još 42 min bez tople vode prema 0 kod NT tajmera;
  - tjedan bez sunca: 0,11 € skuplje od vlastite potrošnje, ali 0 prema 202 min bez tople vode.
- Ograda pod naponom (s izolacijom kvara) prema referentnim strategijama: 97,9–99,1 % prema 92,5–97,5 % u scenarijima s kvarovima.
- Toplinski val: 0 sati stresa biljaka prema 90 h kod tajmera.
- Katalog: **18/18 scenarija prošlo**, 0 sigurnosnih kršenja (`rezultati/rezultati.md`).
- Učenje politike (`rezultati/ucenje_politike.json`): nijedna promjena parametara nije bolja od zadane iznad praga šuma, pa ostaje zadana. Na odvojenim tjednima ušteda je u prosjeku 13,1 %.

### CI
- `b37f749`: radni tok „Energija – izolirana provjera” **uspješan**: jedinični testovi, brzi scenariji, lokalna cjelovita provjera i Docker Compose.
- `e5168e4`: **pao**. CI je uhvatio regresiju (neisporučena energija u otočnom ljetu), popravljenu u `b37f749`.

### Otvoreno
- Granica je satni model i ne poznaje mraz ni vršnu snagu, pa je u hladnom valu napuhana (11 % ostvarenog).
- Prodaja iz baterije ovisi o uvjetima priključka (`politika.izvoz_iz_baterije`).
- Teren: vidi `SPREMNOST.md`, dio B.


## 12.11.2026. 20:48 CET (Europe/Zagreb) – pymodbus, mokovi Open-Meteo, izolirana provjera

### Dogovoreno (vlasnik, 12.11.2026.)
- Simulacija Modbus uređaja pomoću pymodbusa.
- Mokovi za mrežne pozive prema Open‑Meteo.
- Docker Compose za izoliranu provjeru cijelog sustava.

### Implementirano
- `simulator/modbus_pymodbus.py`: SunSpec (modeli 1, 103, 124) na jedinici 1, Eastron SDM na jedinici 2, MQTT senzori, HTTP `/stanje`.
- `simulator/mock_openmeteo.py`: lažni Open‑Meteo s provjerom parametara, zapisom zahtjeva i opcijom kvara (503).
- `testovi/test_mokovi_i_pymodbus.py`:
  - mokovi `urlopen`: uspjeh i parametri upita, URL iz postavki, pad mreže, istek vremena, HTTP 429, neispravan JSON (stara prognoza se zadržava), `null` u nizovima, predmemorija bez ponovnog poziva i učitavanje bez mreže, cijeli tok kiša → bez zalijevanja;
  - interoperabilnost klijenta jezgre s pymodbusom: otkrivanje, upravljanje baterijom, iznimke za nepostojeće jedinice i registre.
- `provjera/provjera_sustava.py` i `provjera/pokreni_lokalno.sh`, `kontejneri/compose.provjera.yaml` (mreža `internal: true`), `kontejneri/provjera.Dockerfile`.
- Radni tok `.github/workflows/energija-provjera.yml`: pokreće se samo na `energija/**`.
- Jezgra: URL prognoze i MQTT port iz postavki, `ENERGIJA_KOD` (samo za provjeru), ime hosta u SAN‑u certifikata, češće otkrivanje dok Modbus uređaj nije pronađen.

### Testirano
- Lokalno na `c563411`: 47/47 jediničnih testova; `pokreni_lokalno.sh` 15/15, izlazni kod 0; testovi košarice OK.
- `docker compose config` za obje Compose datoteke: ispravno.
- U ovoj sesiji nema Docker daemona, pa je Compose pokrenut samo na GitHubu (ishod u sljedećem zapisu ili u Actions).


## 12.11.2026. 20:27 CET (Europe/Zagreb)

### Dogovoreno (vlasnik, 12.11.2026.)
- Zaseban projekt u mapi `energija/` na grani `ccr-d43c7c5c-hrcpw9`, odvojen od košarice; ne spaja se u zadanu granu.
- Prva verzija: radni prototip sa simulacijom (Python, jedna ovisnost `cryptography`).
- Dopuna: kvantizirani rubni AI za prognozu opterećenja i bateriju, provjera memorije prije primjene profila, transparentan prikaz odluka, ručno premošćivanje u naprednim postavkama.

### Implementirano i testirano (commit iza `2bff70e`, vidi git log)
- `python3 -m unittest discover -s testovi -p "test_*.py"` (iz `energija/`): **34/34 OK**.
- Testovi košarice nisu dirani: `python3 -m unittest discover -s tests` OK.
- Simulacije od 7 dana (`--sim-dani 7`, s ubačenim kvarovima):

| Scenarij | Osnovica € | S upravljanjem € | Ušteda € | Dostupnost pastira | Izolacije |
|---|---|---|---|---|---|
| proljeće | 6,43 | 6,18 | 0,25 | 97,6 % | 1 |
| zima | 13,41 | 11,21 | 2,20 | 97,7 % | 1 |
| zima, dinamička tarifa | 15,19 | 11,30 | 3,89 | 97,7 % | 1 |
| ljeto, otočno | 0,66 | 0,67 | −0,01 | 97,7 % | 1 |

  - Ušteda je modelska procjena u odnosu na osnovicu.
  - Ljeti, otočno, ušteda je ≈ 0: baterija ionako pokriva potrebe.
  - Ni u jednom scenariju nije bilo neisporučene energije.
- Uživo preko stvarnih protokola (`--sim`):
  - automatsko prepoznavanje SunSpec/Modbus TCP i MQTT uređaja,
  - HTTPS s lokalnim CA‑om, uz strogu provjeru Pythona 3.13,
  - jednokratni kod za uparivanje,
  - ručno premošćivanje baterije i odbijanje ručnog gašenja pastira,
  - šifrirani zahtjev kroz LAN P2P tunel,
  - automatska kalibracija brojila na 2000 imp/kWh (ta je konstanta skrivena od jezgre).
- Sučelje je provjereno u Chromiumu (1280 px i Pixel 7, svijetla i tamna tema): bez JS grešaka i bez vodoravnog pomicanja. Jedine greške u konzoli su očekivani odgovori 401 prije uparivanja.

### Rubni AI – pošten ishod
- Model je int8 ridge (11 B težina, ~0,02 ms po zaključivanju, učenje u zatvorenom obliku). Za usporedbu, jezgra zauzima ~40 MB RSS.
- Na sintetičkom obrascu, koji profil navika ne vidi, AI je više nego dvostruko točniji (test).
- U simulaciji od 28 dana zimi AI **nije** bio točniji od profila navika (MAE ~159 W prema ~142 W), pa ga zaštitna provjera **ne koristi**, a sučelje to pokazuje. Korist na stvarnoj lokaciji nije dokazana.
- Raniji pokušaj s malom neuronskom mrežom (SGD) bio je lošiji od profila, pa je zamijenjen.
- Memorija je izmjerena samo u ovom oblak‑spremniku: 16 GB, ~15,6 GB slobodno. **Na ciljnom uređaju nije izmjerena.** Jezgra provjeru (sustav + cgroup + CPU) pokreće sama prije primjene profila i zatim svaki sat.

### Nije provjereno
- Stvarni hardver: izmjenjivač, BMS, senzori, releji ograde, optički adapter, Raspberry Pi; potrošnja iz tablice u `ARHITEKTURA.md` je procjena.
- Izgradnja Docker slike (u sesiji nema Docker daemona).
- Open-Meteo i stvarni izvor dinamičke tarife (u testovima se koriste lokalni podaci simulacije).
- Relej na javnom poslužitelju i TLS releja.
- Modbus RTU, UDP hole punching.

### Sljedeći korak
- Pokretanje na jednom stvarnom uređaju (Pi + izmjenjivač s Modbusom), uz mjerenje RAM‑a, CPU‑a i W.
- Kriterij dovršenosti: jezgra 72 h radi bez ponovnog pokretanja, a izmjereni podaci su upisani ovdje.
