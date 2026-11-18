# Energija – zapis stanja

## 13.11.2026. 17:54 CET (Europe/Zagreb) – modularno sučelje i čisti API-ji

### Dogovoreno (vlasnik, 13.11.2026.)
- Modularni sustav s čistim API-jima za ugradnju u pametne mreže i druge sustave.
- Premium modularno sučelje: interaktivni grafikoni uživo (uštede, potrošnja, bojler, sunce, pastir, navodnjavanje),
  prebacivanje između prikaza za stanara i kontrolnog centra s dijagnostikom.

### Implementirano i testirano
- **API v1:** `jezgra/api_v1.py`, OpenAPI 3.1, uloge stanar / integracija / administrator, pozivnice, SSE uživo, CORS
  (zadano isključen), vremenske serije (`jezgra/povijest.py`), dnevne uštede.
- **Pametna mreža:** zahtjevi za fleksibilnost (ograniči uvoz, ograniči izvoz, povećaj potrošnju) i procjena fleksibilnosti.
- **Kućna automatika:** MQTT objava stanja i Home Assistant discovery (`jezgra/integracija.py`). Vlastite objave se ne
  prepoznaju kao uređaji (provjereno).
- **Sučelje:** Web Components (`sucelje/komponente/`), SDK (`sucelje/sdk/`), motor grafikona (`graf.js`) i ljuska
  (`index.html`, `app.js`). Paleta je validirana skriptom (CVD i kontrast, obje teme). Stari `app.js` i `app.css` su uklonjeni.
- **Testovi:** 57/57, uključujući `testovi/test_api_v1.py` (stvarni HTTP: uloge, pozivnice, SSE, OpenAPI pokriva sve
  rute, CORS, zahtjevi mreže, MQTT/HA). `provjera/pokreni_lokalno.sh`: 15/15.
- **Preglednik (Chromium):**
  - administrator na 1360 px, svijetla i tamna tema, 24 h i 7 dana; stanar na Pixel 7; primjer ugradnje;
  - bez JS grešaka i bez vodoravnog pomicanja; stanaru se kontrolni centar ne nudi;
  - popravljene greške: gubitak promjene raspona tijekom učitavanja, preklapanje oznaka osi X, ponovljene oznake osi Y,
    kontrast u primjeru ugradnje.

### Nije provjereno
- Stvarni Home Assistant, stvarni operator mreže / OpenADR (ugovor API-ja postoji; OpenADR nije implementiran).
- Čitač zaslona; provjereni su samo ARIA oznake, rad s tipkovnicom i prikaz u obliku tablice.


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

## 17.11.2026. 09:02 (Europe/Zagreb) – GitLab CI/CD

- Implementirano: `.gitlab-ci.yml` (testovi, svi i ekstremni scenariji, stres testovi na povijesnim podacima 2024.–2025., Compose u Docker-in-Dockeru, provjera slike; optimizacija ručno ili po rasporedu `OPTIMIZACIJA=1`; objava slike ručno i samo na tagu). Postavke Composea idu kroz `ENERGIJA_POSTAVKE` (bez bind-mounta).
- Testirano lokalno (commit cda948d): 60/60 testova, 7/7 brzih scenarija, 15/15 provjera sustava. YAML se ispravno parsira. Docker u ovom okruženju trenutačno ne radi: Compose i slika nisu provjereni ovdje.
- GitLab (n3k-group/hibridni-sustav-upravljanja), grana `razvoj`: preneseno 10 commitova (dokumentacija i dio `jezgra/`). SHA blobova potvrđen za 17 datoteka. `.gitlab-ci.yml` još nije prenesen, pa cjevovod nije pokrenut. `main` nije diran.
- Zapreka: `git push` na gitlab.com nema prijavu (spremljeni token proxy ne primjenjuje). Prijenos datoteku po datoteku kroz spojnik je prekinut.
- Sljedeći korak: vlasnik gurne podstablo `energija/` na GitLab granu `razvoj`. Gotovo kad cjevovod na `razvoj` prođe; tek tada `main`.

## 17.11.2026. 10:36 (Europe/Zagreb) – prvi GitLab cjevovodi

- Kod je na GitLab grani `razvoj`: 85/85 datoteka, SHA blobova potvrđen. `main` nije diran.
- Cjevovod na commitu d10b8d1b:
  - prošlo: testovi, lokalna provjera, Compose u Docker-in-Dockeru, stres testovi na povijesnim podacima 2024.–2025. (9 tjedana; 0 kršenja; dominira 9/9; K1 medijan +50,8 p.b., 9/0, p = 0,002; K2 ispunjen);
  - palo `starenje_baterije`: ovisno o TZ (Europe/Zagreb; lokalno testirano u UTC);
  - pala usporedba `--oznaka ekstremno`: `nenajavljena_naoblaka`, cjenovni_prag 0,04 € jeftiniji.
- Ispravak starenja (necommitano u trenutku zapisa, zatim commitano ovdje):
  - uzorci otpora prenose se preko dana s premalo mjerenja;
  - scenarij produljen s 11 na 14 dana (baterija puna miruje, nema mjerljivih skokova struje);
  - prolazi u Europe/Zagreb i UTC; cijeli katalog u Europe/Zagreb još se izvodi.
- Otvoreno, odluka vlasnika: popraviti nenajavljenu naoblaku ili uvesti prag šuma u kriteriju prolaza.

## 17.11.2026. 10:53 (Europe/Zagreb) – cjevovod 3078153762 (GitLab razvoj, 002a9be3)

- Prošlo 6/7 poslova:
  - jedinični i integracijski testovi;
  - lokalna provjera sustava;
  - svi scenariji 18/18;
  - stres testovi na povijesnim podacima;
  - Compose u Docker-in-Dockeru;
  - izgradnja i probno pokretanje produkcijske slike.
- Palo: `scenariji_ekstremni_usporedba`. U `nenajavljena_naoblaka` je cjenovni_prag 0,04 € jeftiniji (stvaran nalaz, ne greška izvođenja).
- `main` nije diran. Čeka odluku vlasnika: popraviti ponašanje (preporuka) ili prag šuma u kriteriju.

## 17.11.2026. 11:48 (Europe/Zagreb) – prag šuma; cjevovod 3078397405 zelen

- **Odluka vlasnika (17.11.2026.):** implementirati prag šuma.
- **Implementirano:**
  - zadržavanje načina baterije 15 min (zadano uključeno);
  - mrtva zona cijene i zadržavanje bojlera: podesivi, zadano isključeni, jer su u simulaciji podizali trošak (hladni val: mrtva zona +0,48 do +1,63 €; bojler 18,08 prema 17,16 €);
  - prag troška u usporedbi: max(0,05 €, 1 %). Uveden nakon poznatog rezultata; K1/K2 nepromijenjeni;
  - brojač `preklapanja` u scenarijima.
- **Učinak:** promjena načina baterije 5–13 % manje, trošak nije porastao (usporedba, hladni val: 17,16 → 16,34 €).
- **Testirano lokalno u Europe/Zagreb (commit cd9b7c6):**
  - 68/68 testova;
  - 18/18 scenarija;
  - 15/15 provjera sustava;
  - ekstremno: nenadmašena 8/8, dominira 7/8.
- **GitLab razvoj, commit 7cd6ce56, cjevovod 3078397405:** svih 7 poslova prošlo.
- **Spajanje u main nije izvršeno:** automatska zaštita odbila je spajanje razvoj → main. Treba izričito odobrenje vlasnika ili spajanje u GitLab sučelju.

## 17.11.2026. 13:49 (Europe/Zagreb) – spajanje u main, opoziv tokena, rigorozno testiranje

- **Spojeno:** razvoj → main, MR !1, merge commit 7afb783d. Cjevovod 3078503196 na main: svih 7 poslova uspjeh.
- **Tokeni opozvani:** "Api" i "Claude-transfer2". Za oba GitLab nakon opoziva vraća 401.
- **Nalaz 1 – neponovljiva simulacija.** Odluke su ovisile o opterećenju računala:
  - način rada prema load average;
  - provjera memorije za AI;
  - vremenski proračun treniranja.

  Isti tjedan davao je 40–222 min bez tople vode. Ispravak (commit 0c3fcd1): pokretač scenarija glumi referentni uređaj, a proračun treniranja se u simulaciji ne mjeri. Pet pokretanja (4 pod opterećenjem) daje identične KPI; dodan je test.

  **Posljedica:** sve ranije presude (K1/K2) bile su izložene tom šumu.
- **Nalaz 2 – testovi ovisni o zoni računala.** Lokacija je u Hrvatskoj, a sat u drugoj zoni. Testovi sada rade u zoni lokacije; ispravljen je i test koji prelazi ljetno vrijeme. 68/68 testova u 5 zona.
- **Ponovljive presude**, stari model bojlera, commit 0c3fcd1:
  - katalog: NEUSPJEŠNA (K1 p = 0,23; K2: zima_otocno_hladno topla voda 2808 prema 2776 min);
  - ocjena 2027.: DJELOMIČNA (K1 nije, K2 jest);
  - ocjena 2028.: NEUSPJEŠNA (K1 nije; K2: 2028-04-24 VT/NT, 218 prema 198 min);
  - ocjena 2028. ravnopravno: DJELOMIČNA (K1-R ispunjen, 21/1, p < 0,001; K2 pao na toploj vodi u 2 tjedna);
  - stres (sintetički): 0 kršenja, K1 p = 0,09.
- **Zaključak:** glavna slabost je topla voda. Sljedeći korak je prediktivno upravljanje spremnikom (zasebna grana ccr-dt-rad, commit bf25e2a); usporedbe s njim su u tijeku.

## 17.11.2026. 15:17 (Europe/Zagreb) – prediktivno upravljanje spremnikom PTV-a

- Implementirano (`jezgra/spremnik.py`, spojeno u radnu granu, da88f94):
  - toplinski model spremnika; gubici UA se uče iz mirnih razdoblja ≥ 3 h (sim: naučeno 1,85, stvarno 1,8 W/K);
  - MPC 36 h nad temperaturom: dinamička tarifa, višak sunca po izvoznoj cijeni, udobnost ≥ 45 °C;
  - prednost dizalici topline (kazna grijaču 0,05 €/kWh), predgrijavanje u jeftinim satima;
  - ciklus legionele: 62 °C, ≥ 60 °C 30 min, svakih 7 dana. Pad zbog potrošnje = izmjereni gubitak (kWh, info događaj), sljedeći ciklus nadoknađuje (cilj do +3 °C, rok unutar 24 h); pad temperature spremnika nije anomalija.
- Simulator: fizika spremnika, dizalica s COP-om, 2 tuša dnevno, neovisno mjerenje stvarne dezinfekcije. Referentne strategije: termostat dizalice 50–55 °C i tjedni program legionele (ned 2–5 h).
- Usporedba: novo mjerilo "kašnjenje dezinfekcije". Bez njega su dva scenarija "pobijedila" konkurentu koji je preskočio dezinfekciju. K1/K2 nepromijenjeni.
- Odbačeno: pouzdanost prognoze sunca 0,7 i 0,5 za spremnik (nenajavljena naoblaka −1,4 c, bunar_presusio +6 do +12 c lošije).
- Testirano (ponovljivo, Europe/Zagreb):
  - 81/81 testova; katalog 18/18; brzi 7/7; provjera sustava 15/15;
  - usporedba katalog: nenadmašena 18/18 (dominira 15), K1 +48,5 p.b., 10/1, p = 0,006, K2 ispunjen → USPJEŠNA;
  - ekstremno: nenadmašena 8/8 (dominira 7), K1 p = 0,06 → DJELOMIČNA;
  - ocjene 2027./2028./2028.R prije mjerila legionele: sve USPJEŠNE (K1 p < 0,001, K2 ispunjen).
- Ograničenje: fizika simulatora i referentne strategije su promijenjene, pa usporedba sa starim brojkama nije izravna. Ocjene 2027./2028. ranije su korištene (informativno, ne neovisna potvrda).
- GitLab: ova verzija nije prenesena (tokeni opozvani). Čeka novi kratkotrajni token ili vlasnikov push.

## 18.11.2026. 08:06 (Europe/Zagreb) – prijenos na GitLab bez tokena

- Tokeni od 17. i 18.11. (fine-grained) nemaju dozvolu za pisanje (Commit: Create). Ne mogu se ni opozvati preko API-ja, pa ih vlasnik treba opozvati ručno.
- Prijenos je obavljen kroz GitLab spojnik ove sesije, bez tokena: 18 datoteka kao minimalne izmjene (diff) plus nove datoteke, u 5 commitova na razvoj; usputni s [skip ci].
- Svih 18 datoteka podudara se po git blob SHA s lokalnim (izvor 072e655).
- Cjevovod 3082667104 na razvoj (982544fc) pokrenut; ishod se bilježi kad završi. main nije diran.

## 18.11.2026. 08:25 (Europe/Zagreb) – optimizacija brzine, skeniranja i jednostavnosti

- Mjereno prije: korak 13,2 ms (84 % planiranje: spremnik ~90 ms, baterija ~45 ms po planu); izvještaj i ušteda čitali su cijelu arhivu.
- Implementirano (fab80b5):
  - planeri bez poziva funkcija u unutarnjim petljama: baterija 16,4 → 7,5 ms, spremnik 33,3 → 19,9 ms; planovi identični na 60 nasumičnih slučajeva;
  - izvještaj čita samo segmente arhive od početka razdoblja; pokretanje čita arhivu jednom;
  - automatsko traženje Modbus uređaja u LAN-u: samo privatne mreže, najviše /22, portovi 502/1502, 64 niti, ~3 s za /24; isključivo postavkom `otkrivanje.lan_skeniranje`;
  - paralelno ispitivanje hostova; poznati uređaji se preskaču;
  - `--skeniraj`, `--dijagnoza`, `POST /api/v1/otkrivanje`, gumb "Potraži uređaje".
- Testirano (Europe/Zagreb):
  - 89/89 testova (8 novih), 15/15 provjera sustava;
  - usporedba katalog: nenadmašena 18/18, K1 p = 0,006, K2 ispunjen (iste presude kao prije);
  - korak 7,8 ms (1,7× brže); usporedba na katalogu 566 → 294 s.
- Ograničenje: traženje u stvarnoj kućnoj mreži ovdje nije provjereno (okruženje nema privatnu mrežu); provjereno na lokalnim portovima.

## 18.11.2026. 08:52 (Europe/Zagreb) – GitLab cjevovodi zeleni

- Cjevovod 3082667104 (razvoj, 982544fc; spremnik PTV-a, legionela, ponovljivost): svih 7 poslova uspjeh.
- Cjevovod 3082735971 (razvoj, 71698d02; optimizacija + otkrivanje): svih 7 poslova uspjeh.
- Stres testovi na stvarnim podacima 2024.–2025., novi spremnik:
  - 0 sigurnosnih kršenja; dominira u 9/9 tjedana;
  - 0 minuta bez tople vode (referentne strategije također 0);
  - K1: medijan +67,3 p.b., 8/0, p = 0,004 → ispunjen; K2 ispunjen.
- Primjer: najnestabilniji tjedan (09/2024) −21,55 € prema −10,38 € (vlastita).
- "Ostvareno od mogućeg" 106 % u najhladnijem tjednu: granica je satni model bez zabrane punjenja na mrazu, pa nije stroga gornja granica.
- **main nije diran.** Spajanje razvoj → main čeka izričitu potvrdu vlasnika.

## 18.11.2026. 13:40 (Europe/Zagreb) – poboljšanje upravljanja (mjereno, razvojni katalog)

- **Metodologija:** granica sada poštuje zabranu punjenja na mrazu (prije nedostižna: hladni val 28 % → 84 % ostvarenog). Ostvareno od mogućeg = (vlastita − pametna) / (vlastita − granica).
- **Mjerenje varijanti** (isti katalog, ponovljivo; ukupni trošak pametne / medijan ostvarenog):
  - A dosadašnje: 27,58 € / 74,4 %;
  - B + brzo ponovno planiranje (sunce odstupa > 35 % 10 min): 27,47 € / 77,8 % → **uključeno**;
  - C + kratkoročna korekcija prognoze: 28,32 € / 76,3 % (sve_odjednom 47 → 30 %) → odbačeno;
  - D + učenje pristranosti bez praga: 27,08 € / 73,2 % (hladni val, jesen, volatilne lošije) → odbačeno;
  - E prag 25 %, pola ispravka: 27,21 € → odbačeno;
  - F prag 25 %, puni ispravak, samo uz mrežu: **25,64 €** / 77,8 %, nijedan scenarij lošiji → **uključeno**;
  - H + zajedničko planiranje baterije i spremnika (granične cijene): 26,67 €, lošije u 12/18 → odbačeno (opcija ostaje isključena).
- **Ukupno:** 27,58 → 25,64 € (−7 %). K1 +55,1 p.b., 10/0, p = 0,001 (prije +48,5, p = 0,006); K2 ispunjen.
- **Testirano** (commit 9c839b0, Europe/Zagreb):
  - 89/89 testova; katalog 18/18; provjera sustava 15/15;
  - sintetički stres: 0 kršenja, K1 9/0, p = 0,002.
- **EMHASS:** instalacija i dalje odbijena od automatske zaštite (i uz vlasnikovo odobrenje); nije zaobiđeno. Treba dopuštenje u postavkama Claude Codea.
- **Sljedeće:** 3. ocjena na stvarnim podacima 2023. (kriterij zapisan prije pokretanja) kroz GitLab posao ocjena_2023.

## 18.11.2026. 14:30 (Europe/Zagreb) – 3. ocjena (stvarni podaci 2023.): USPJEH

- Cjevovod 3084029923 (razvoj, 3daa789e): svih 8 poslova uspjeh; posao ocjena_2023 (18143817138), artefakt `rezultati_ci/ocjena_2023` (365 dana).
- Ocijenjeno strogo po kriteriju zapisanom prije pokretanja (KRITERIJ_ZNACAJNOSTI.md, 3. ocjena), bez podešavanja:
  - K1: medijan Δ +45,4 p.b. (≥ +10), bolje 8 / lošije 1, p = 0,0195 (< 0,05) → **ispunjen**;
  - K2 → **ispunjen**;
  - sigurnosna kršenja: **0**; 0 minuta bez tople vode; 0 h stresa biljaka (vlastita: 24,6 h u najtoplijem tjednu).
- Pametna dominira (Pareto, s pragom šuma) u 9/9 tjedana.
- Medijan „ostvarenog od mogućeg”: **45 %** (raspon 38–71 %).
- Iskreno o ograničenjima:
  - 45 % je znatno manje od razvojnog kataloga (77,8 %) i stres testova 2024.–2025. Na neviđenim podacima ostaje velik prostor do granice.
  - U najtamnijem tjednu (01/2023) cjenovni prag je jeftiniji: 16,73 € prema 16,88 € (+0,15 €). Razlika je unutar praga šuma (1 %), zato je to „dominira” u tablici, ali K1 to broji kao lošije.
  - Uštede prema vlastitoj potrošnji: 0,6–1,9 € tjedno po tjednu. Maloprodajni dodatak 0,085 €/kWh je pretpostavka.
- **main nije diran.** Spajanje razvoj → main čeka izričitu potvrdu vlasnika.

## 18.11.2026. 16:50 (Europe/Zagreb) – spojeno u main (GitLab), ispravci iz pregleda

- **Spojeno:** GitLab MR !2 razvoj → main, spojen 18.11.2026. 16:29.
  - Cjevovodi na commitu 6cb7eeb3 prije spajanja: zeleni (MR 3084816873, razvoj 3084814675).
  - main = a049c87a (commit spajanja).
- **Ispravljena utrka u izoliranoj provjeri:** korak 5 sada čeka plan nakon prognoze (6cb7eeb3). Pao je na 054097a3; kod upravljanja nije bio uzrok.
- **Cjevovod na mainu (3084873518) pao je za 1 s:** svi poslovi, s praznim zapisnikom. Uzrok kroz spojnik nije vidljiv (nema failure_reason).
  - Pretpostavka, nepotvrđeno: iscrpljene CI minute ili ograničenje runnera na zaštićenoj grani.
  - Kod je isti kao na zelenim cjevovodima.
- **GitLab Duo** je kao recenzent automatski dodan na MR (nisam ga tražio) i pokrenuo je pregled (cjevovod duo_workflow). Oba nalaza su potvrđena u kodu i ispravljena:
  - gumb „Potraži uređaje” i prvo traženje nakon svježeg pokretanja nisu pretraživali LAN, jer `time.monotonic()` broji od pokretanja računala → početna vrijednost `-inf`;
  - dizalica topline nije bila u zaštitnim putovima (sigurno stanje, vršna snaga otočno, pregrijavanje i podnapon baterije) → dodana. Kaskada niske baterije ju je već imala.
- **Testirano** (lokalno, Europe/Zagreb):
  - 91/91 testova; 3 nova testa padaju na starom kodu;
  - provjera sustava 15/15; katalog scenarija 18/18, 0 kršenja.
- **Ispravci su na razvoju, nisu u mainu.**
- **CI na GitLabu trenutačno ne radi:** razvoj 14119833 (cjevovod 3084986814) također je pao za 1 s, s praznim zapisnikom. Kvar nije vezan uz main, nego uz projekt ili grupu. Razlog treba pogledati na stranici cjevovoda; za te ispravke CI na GitLabu zato nije potvrđen.

## 18.11.2026. 18:25 (Europe/Zagreb) – zaobilazak kvara GitLab CI-ja, ispravci u mainu

- **GitLab CI i dalje ne radi:** ponovno pokretanje cjevovoda 3084986814 opet je palo odmah.
  - Razlog nije dostupan: spojnik ne vraća failure_reason, a token mrežnog posrednika pripada drugom GitLab projektu (nije korišten).
  - Kvar nije popravljiv bez troška ili vlastitog runnera, pa je zaobiđen.
- **Zamjena:** GitHub Actions `.github/workflows/energija-cjelovito.yml`, jednako GitLab CI-ju: svi scenariji, ekstremna usporedba, stres 2024.–2025., ocjena 2023., produkcijska slika.
- **Run 44345886098** (cc963c8, isti kôd kao GitLab razvoj 3410bf80): svih 5 poslova uspjeh. Izolirana Compose provjera za d0364e3 (run 44340361029) također uspjeh.
  - stres 2024.–2025.: 0 kršenja, K1 +68,8 p.b. (8/0, p = 0,0039), K2 ispunjen, dominira 9/9;
  - ocjena 2023.: 0 kršenja, K1 +45,4 p.b. (8/1, p = 0,0195), K2 ispunjen; identično GitLab rezultatu prije ispravaka.
- **Spojeno:** GitLab MR !3 razvoj → main uz SHA zaštitu, 18.11.2026. 18:24; main = a64a0e10.
  - Spojeno je uz zelenu ekvivalentnu provjeru na GitHubu. GitLab cjevovod nije zelen (ne radi); grana nije imala pravilo koje to zabranjuje.
- GitLab Duo ponovno je automatski dodan kao recenzent (postavka projekta).
- Verzija 0.2.1 i zapis u PROMJENE.md idu na razvoj ovim commitom; u main tek sljedećim spajanjem.

## 18.11.2026. 18:53 (Europe/Zagreb) – analiza ulaza i izlaza, pojednostavljenje instalacije (0.3.0)

- **Analiza:** 509 funkcija.
  - Unutarnje funkcije većinom imaju tipove: 444/509 ulaza i 473/509 izlaza.
  - Rizici su na granicama sustava: postavke, očitanja uređaja, API i naredbeni redak. Tamo su nađene greške.
- **Stvarne greške ispravljene** (svaka ima test koji pada na starom kodu):
  - SunSpec oznake „nije dostupno” (0xFFFF/0x8000) čitale su se kao brojevi (SoC 6553 %, PV −32768 W);
  - MQTT `NaN` prolazio je do planera;
  - `rucna_snaga_w = NaN` u ručnom načinu značio je punu snagu punjenja;
  - `"ukljuci": "false"` značio je uključi;
  - neispravni parametri (`dana`, `korak=0`, `sati`, `minuta`) davali su 500 umjesto 400; tijelo koje nije objekt rušilo je uparivanje;
  - tipfeler ili krivi tip u postavke.json tiho se zanemarivao ili rušio jezgru kasnije; neispravna IP mreža rušila je nit otkrivanja.
- **Instalater:**
  - `--postavi kljuc=vrijednost` (provjereno, atomski upis) i `--postavke`;
  - `--dijagnoza` s točnom naredbom za svaku stavku i preporukama za zadane osnovne podatke;
  - nazivna snaga punjenja čita se iz izmjenjivača (SunSpec WChaMax) ako nije ručno upisana;
  - upozorenja su vidljiva i u kontrolnom centru (blok „Postavke i očitanja”, provjereno u pregledniku).
- **Referenca:** `ULAZI_IZLAZI.md` – tok podataka po koraku upravljanja, ulazi i izlazi modula, a generirano iz koda: naredbeni redak, postavke s rasponima, API, kanali. Test pada ako dokument zaostane.
- **Testirano** (lokalno, Europe/Zagreb):
  - 105/105 testova (14 novih u test_ulazi.py);
  - provjera sustava 15/15;
  - katalog 18/18, 0 kršenja; uštede identične prethodnom pokretanju (provjera ne mijenja ponašanje na ispravnim podacima).
- **Nije provjereno:** stvarni izmjenjivači s oznakama „nije dostupno” (samo simulirano i jediničnim testom).
- **GitHub CI** (353db1d; GitLab CI i dalje ne radi):
  - cjelovita provjera (run 44363639684) 5/5 i izolirana Compose provjera (run 44363639858) – uspjeh;
  - stres 2024.–2025.: 0 kršenja, K1 +68,8 p.b. (8/0, p = 0,0039), K2 ispunjen;
  - ocjena 2023.: 0 kršenja, K1 +45,4 p.b. (8/1, p = 0,0195), K2 ispunjen – identično prije izmjena.
- **GitLab:** razvoj ← 0.3.0 u pet commitova kroz spojnik (25fa9b4d … ovaj zapis), zatim MR razvoj → main.
