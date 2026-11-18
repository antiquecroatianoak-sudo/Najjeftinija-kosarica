# Dnevnik promjena

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
