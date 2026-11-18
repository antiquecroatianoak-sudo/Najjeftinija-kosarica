# Dnevnik promjena

## 0.3.0 – 18.11.2026.

### Instalacija
- `--postavi kljuc=vrijednost` upisuje provjerene postavke, a `--postavke` ih ispisuje. Ručno uređivanje JSON-a više nije potrebno.
- Postavke se provjeravaju pri svakom učitavanju:
  - nepoznati ključ dobiva prijedlog ispravka (`kapacitet_kw` → `kapacitet_kwh`);
  - provjeravaju se tip i raspon (npr. legionela najmanje 60 °C);
  - provjeravaju se odnosi (`soc_min < soc_max`) i sadržaj popisa (IP mreže, Modbus hostovi).
  - Neispravno se odbacuje, vrijedi zadana vrijednost, a upozorenje se vidi u dijagnozi, dnevniku i kontrolnom centru.
- `--dijagnoza` predlaže točnu naredbu za svaku stavku i upozorava na osnovne podatke koji su još zadani.
- Najveća snaga punjenja i pražnjenja čita se iz izmjenjivača (SunSpec WChaMax) ako je instalater nije upisao.
- `ULAZI_IZLAZI.md`: referenca svih ulaza i izlaza. Dio je generiran iz koda, a test pada ako zaostane.

### Pouzdanost ulaza
- SunSpec oznake „nije dostupno” više ne postaju nemogući brojevi (npr. 6553 % napunjenosti).
- Očitanja koja nisu broj, NaN, beskonačno ili su izvan fizikalnog raspona odbacuju se. Odbačena se vide u dijagnostici.
- API vraća 400 s porukom za svaki neispravan ulaz, nikad 500. Ispravljene opasne greške:
  - `rucna_snaga_w = NaN` značio je punu snagu punjenja;
  - `"ukljuci": "false"` značio je uključi;
  - neispravno tijelo zahtjeva rušilo je uparivanje.

## 0.2.1 – 18.11.2026.
- Dizalica topline gasi se u svim zaštitnim stanjima, kao i grijač: sigurno stanje, prevelika snaga u otočnom radu, pregrijavanje i podnapon baterije.
- „Potraži uređaje” i prvo automatsko traženje odmah pretražuju lokalnu mrežu, i odmah nakon pokretanja uređaja.
- Izolirana provjera sustava više ne pada povremeno (čeka plan nakon prognoze).
- Cjelovita provjera radi i na GitHub Actions (`.github/workflows/energija-cjelovito.yml`).

## 0.2.0 – 18.11.2026.

### Upravljanje
- **Spremnik tople vode s prediktivnim upravljanjem:**
  - toplinski model, a gubici se uče iz mjerenja;
  - planiranje 36 h unaprijed po dinamičkoj tarifi i višku sunca;
  - prednost dizalici topline, predgrijavanje u jeftinim satima.
- **Zaštita od legionele:** voda se svakih 7 dana drži iznad 60 °C barem 30 min. Kad potrošnja prekine ciklus, to nije greška: gubitak se izmjeri i nadoknadi u sljedećem ciklusu.
- **Brzo ponovno planiranje** kad stvarno sunce trajno odstupa od prognoze.
- **Ispravak sustavne pogreške prognoze sunca**, samo uz mrežu.
- **Prag šuma:** način rada baterije zadržava se najmanje 15 min.
- **Ušteda na razvojnom katalogu:** −7 % troška naspram 0.1.x, bez ijednog lošijeg scenarija.

### Instalacija i rad
- Automatsko traženje Modbus uređaja u lokalnoj mreži:
  - samo privatne mreže, oko 3 s, paralelno;
  - već poznati uređaji se preskaču.
- `python -m jezgra --dijagnoza`: provjera spremnosti, s uputom za svaku grešku.
- `python -m jezgra --skeniraj`: popis pronađenih uređaja.
- U kontrolnom centru postoji gumb „Potraži uređaje”; API `POST /api/v1/otkrivanje`.
- Planeri su oko 2× brži (isti planovi), a upravljački korak 1,7× brži.
- Izvještaji više ne usporavaju kako povijest raste.

### Provjera kvalitete
- Simulacija je ponovljiva: rezultati više ne ovise o opterećenju računala.
- Testovi rade u zoni simulirane lokacije.
- Teoretska granica poštuje zabranu punjenja na mrazu.
- GitLab CI:
  - testovi, svi i ekstremni scenariji;
  - stres testovi na stvarnim podacima 2024.–2025.;
  - ocjena na neovisnim stvarnim podacima 2023.;
  - izolirana Compose provjera i provjera produkcijske slike.

### Poznata ograničenja
- Na stvarnom hardveru nije pokretano; terenske provjere su u `SPREMNOST.md`, dio B.
- Usporedba s EMHASS-om nije napravljena: instalacija u ovom okruženju nije dopuštena.

## 0.1.0 – 13.11.2026.
- Prvi radni prototip: lokalna jezgra, Modbus/MQTT, baterija, pastir, navodnjavanje, API v1, sučelje.
