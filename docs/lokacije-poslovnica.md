# Lokacije poslovnica i krug oko korisnika

## Izvor i licenca
- **Koordinate poslovnica i popis naselja** dolaze iz OpenStreetMapa (© OpenStreetMap suradnici, licenca ODbL,
  https://www.openstreetmap.org/copyright).
  - Dohvaćaju se preko javnog Overpass API-ja: jedan upit za trgovine lanaca i jedan za naselja dnevno, uz
    User-Agent s poveznicom na ovaj repozitorij.
  - Atribucija je prikazana u aplikaciji (karta i redak ispod nje).
- **Podloga karte:** pločice `tile.openstreetmap.org` uz atribuciju, prema pravilima korištenja OSM pločica.
  - Namijenjeno je malom prometu.
  - Ako promet naraste, treba zamijeniti URL pločica u `site/aplikacija.js` (`L.tileLayer`).
- **Pretraga adrese:** jedan upit javnom Nominatimu, samo na izričit pritisak „Traži”, najviše jedan u sekundi.
  - Nema dovršavanja dok se tipka (pravila Nominatima to ne dopuštaju).
  - Prijedlozi pri tipkanju su samo naselja iz lokalnog popisa (`data/mjesta.json`), ne ulice ni kućni brojevi.
- **Leaflet 1.9.4** je u `site/leaflet/` (BSD-2, `site/leaflet/LICENSE`).

## Postupak (`scripts/lokacije_poslovnica.py`, svaki dan nakon uvoza cijena)
1. Poslovnice se čitaju iz `proizvodi.json`: stabilan identitet `lanac|store_id` i adresa iz službenog cjenika.
   Dnevni numerički indeks se ne koristi.
2. OSM trgovine lanca prepoznaju se po `brand`/`name`/`operator`.
   - Odbacuju se elementi bez valjanih koordinata unutar okvira Hrvatske.
3. Poslovnica dobiva koordinate OSM trgovine **istog lanca** samo kada se poklapaju:
   - ulica (sve značajne riječi; inicijali i padeži dopušteni),
   - **kućni broj**,
   - i naselje: poštanski broj, `addr:city`, ili naselje iz adrese unutar 10 km kada OSM nema mjesto.
4. Sam naziv lanca, samo naselje ili središte grada **nisu** dovoljni.
   - Poslovnica bez para ostaje bez koordinata i nikad nije u krugu.
5. **Višeznačno se odbija:**
   - više udaljenih OSM trgovina iste adrese;
   - jedna OSM trgovina uparena s poslovnicama različitih adresa.
   Ista adresa pod dva store_id smije dijeliti koordinate.
6. **Izlaz:**
   - `data/lokacije.json` (`[lanac, store_id, lat, lon, osm_id, kvaliteta]`, status, `osm_datum`);
   - `data/mjesta.json`;
   - `data/lokacije-izvjesce.json`: po lancu ukupno, s koordinatama, bez i višeznačno, te trag svakog para
     (adresa iz cjenika, OSM adresa, OSM id, kvaliteta).
7. **Kvar Overpassa:** zadržavaju se posljednji objavljeni valjani parovi s **nepromijenjenom adresom** i objavljeni
   popis naselja, uz njihov `osm_datum`, a status to navodi.
   - Nova ili promijenjena poslovnica ostaje bez koordinata.

## Izdanje cjenika
`proizvodi.json` i svaka `data/poslovnice/<n>.json` nose isti `izdanje` (otisak datuma te redoslijeda proizvoda i
poslovnica). Datoteka poslovnice nosi i svoj `lanac|store_id`. Aplikacija ne prihvaća datoteku drugog izdanja ili druge
poslovnice, pa ponovni uvoz istog dana s drugim redoslijedom ne može pridružiti tuđe cijene.

## Krug u aplikaciji
- **Prihvatljive poslovnice** su: pouzdane koordinate + odabrani krug (5/10/20/30/50 km, zadano 20, zračna
  udaljenost, uključivo, tolerancija 1e-6 km) + dopušteni lanci.
  - Sve kartice, alternative, filtar marke, kombinacije, ušteda i „Sve u jednom dućanu” koriste samo njihove cijene.
- **Učitavanje cjenika:**
  - najviše 6 istodobnih preuzimanja, s brojem učitanih;
  - dok se učitava, nema djelomičnog minimuma;
  - neuspjele datoteke ponavlja gumb „Ponovi”, a rezultat je tada izričito „među učitanim poslovnicama”.
- **Vidljiva ograničenja prikaza:**
  - „Sve u jednom dućanu” prikazuje 8 najpovoljnijih potpunih poslovnica (i to piše);
  - popis „Poslovnice u krugu” prikazuje sve.
- **Kombinacija** je točan optimum za najviše 2, najviše 3 i neograničen broj dućana (iscrpna pretraga nakon
  uklanjanja istih i posvuda skupljih poslovnica). Trošak puta nije uračunat.
