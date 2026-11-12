# Spremnost za produkciju

Ovaj popis odvaja ono što je **automatski dokazano na simulatorima** od onoga što se može dokazati
**samo na stvarnoj lokaciji**. Sustav nije „spreman za produkciju” dok nisu zatvorene i stavke iz
dijela B. Simulator može pokazati da je logika sigurna i robusna. Ne može pokazati da stvarni
hardver radi kako ga model opisuje.

## A. Automatske provjere (svaki push na `energija/**`, radni tok „Energija – izolirana provjera”)

| Vrata | Kako se provjerava | Gdje |
|---|---|---|
| Jedinični testovi | kriptografija, dnevnik i oporavak, kopije, Modbus/MQTT, impulsi, anomalije, pastir, optimizator, AI, tunel, sinkronizacija | `testovi/` |
| Mrežni pozivi | `urlopen` mokiran: uspjeh, pad mreže, istek, HTTP 429/503, neispravan JSON, `null`, predmemorija i rad bez mreže | `test_mokovi_i_pymodbus.py` |
| Interoperabilnost Modbusa | klijent jezgre prema neovisnom pymodbus poslužitelju: otkrivanje SunSpec i SDM, upisi, iznimke, stvarni ispad i ponovno spajanje | `test_mokovi_i_pymodbus.py` |
| Sigurnosne invarijante u svakom koraku | nikad pražnjenje ispod najmanje napunjenosti, nikad punjenje ispod 0 °C, pumpa na suho najviše 2 koraka, ispravne dionice ograde ne ostaju bez napona, bez iznimki | `scenariji/pokretac.py` (`Cuvar`) |
| Scenariji kvarova | ograda (kratki spoj, prekid, više kvara, vegetacija), suhi bunar, ispad izmjenjivača i senzora, ispadi Open‑Meteo, rad bez mreže ljeti i zimi, mraz, starenje baterije | `scenariji/katalog.py` |
| Cjeloviti sustav | jezgra + pymodbus + MQTT + lažni Open‑Meteo, stroga provjera TLS‑a, uparivanje, ručno premošćivanje do izmjenjivača, potpis izvještaja | `provjera/provjera_sustava.py` |
| Izolacija i ograničenja kontejnera | Compose s `internal: true` (dokazano: bez interneta), jezgra ograničena na 160 MB i 1 CPU, slika samo za čitanje, bez Linux sposobnosti (capabilities) | `kontejneri/compose.provjera.yaml` |
| Politika upravljanja | naučena na skupu za učenje, prihvaćena samo ako je bolja na odvojenim tjednima i bez ijednog sigurnosnog kršenja | `scenariji/ucenje_politike.py` |

## B. Samo na terenu (otvoreno)

| Vrata | Kriterij prolaza |
|---|---|
| Stvarni izmjenjivač/BMS | Registri i semantika SunSpec 124 (StorCtl_Mod, InWRte/OutWRte) odgovaraju modelu. Ograničenje „ne puni” i „ne prazni” provjereno mjerenjem struje. |
| Konvencija predznaka struje BMS‑a | Procjena unutarnjeg otpora koristi apsolutnu vrijednost, ali potrebna je potvrda na stvarnim podacima. |
| Mjerači napona ograde i sekcijske sklopke | Ubačeni kratki spoj (npr. žica na zemlju) izoliran je u manje od 20 min. Povratni vod napaja ostatak ograde. |
| Optički adapter na stvarnom brojilu | Konstanta je kalibrirana unutar ±2 % od natpisne pločice. Broj impulsa odstupa najviše ±1 % na 24 h. |
| Senzori vlage tla | Kalibracija prema gravimetrijskom uzorku. Prag zalijevanja potvrđen za tip tla. |
| Potrošnja i resursi jezgre na uređaju | Izmjereno u W, MB i % CPU kroz 72 h. Bez ponovnog pokretanja, dnevnik i snimka bez gubitaka. |
| Nestanak napajanja usred pisanja | 20 ponavljanja izvlačenja napajanja. Oporavak bez gubitka potvrđenih zapisa. |
| Stvarni Open‑Meteo i izvor tarife | Tjedan rada. Prognoza i tarifa stižu, a zamjenski rad je provjeren isključivanjem mreže. |
| Relej tunela na javnom poslužitelju | TLS releja i pristup tehničara uz vlasnikovo odobrenje. |
| Ušteda na stvarnoj lokaciji | Izvještaj prema osnovici kroz najmanje 4 tjedna, uz obrazloženje odstupanja od simulacije. |
| Pravni i sigurnosni zahtjevi | Električni pastir prema normi za aparate (npr. HRN EN 60335‑2‑76), instalacija od strane ovlaštene osobe, priključak na mrežu prema uvjetima operatora. |

Mjerila uspjeha i njihov ishod upisuju se u `STANJE.md`, uz datum i commit.
