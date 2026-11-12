# Energija – zapis stanja

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
