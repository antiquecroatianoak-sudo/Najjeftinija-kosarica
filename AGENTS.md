# Projektne upute — Najjeftinija košarica

## Nastavak rada i kontinuitet — uputa vlasnika 28.10.2026.

- Na početku nastavka pročitaj `PROJECT_STATE.md`, ovaj `AGENTS.md` i dokumente na koje zapis upućuje. Kod korisnikova pozivanja na ranije odluke pretraži dostupne prethodne razgovore; nedostupnu povijest ne rekonstruiraj nagađanjem.
- Potvrdi identitet repozitorija, ciljnu granu i aplikaciju. Provjeri trenutačni remote, otvorene PR-ove, CI na točnom commitu i objavljenu verziju kroz odgovarajući servis. Lokalni checkout, stara poruka i spojeni PR sami ne dokazuju objavu.
- Prije izmjene napiši kratak radni plan s ciljem, ovisnostima, sljedećim korakom i kriterijem dovršenosti. Provjeri posljedice kroz cijeli tijek rada opisan u zapisu. To je operativni plan i provjera, ne zahtjev za zapisivanjem privatnog razmišljanja.
- Razlikuj dogovoreno, planirano, implementirano, testirano, spojeno i objavljeno. Test veži uz commit i rezultat; objavu uz verziju i potvrdu servisa. Nepokrenute, preskočene i nepotpune provjere ostaju vidljive.
- Nakon smislene cjeline i prije završetka razgovora ažuriraj `PROJECT_STATE.md`: nove odluke, dokaze, otvoreno, zapreke, sljedeći konkretni korak i njegov uvjet dovršenosti. U svaki zapis stavi vrijeme provjere Europe/Zagreb. Povijesne zapise ne briši i ne proglašavaj aktualnima.
- Kad se sjećanje, dokument i stvarno stanje razlikuju, sačuvaj trag razlike i potvrdi aktualno stanje iz primarnog sustava. Novija izričita odluka vlasnika nadomješta staru; tehničko stanje potvrđuju repo, testovi i objava.
- Nastavljaj već odobrene, sigurne i reverzibilne korake bez ponavljanja pitanja. Prijašnje odobrenje bilježi samo s potvrđenim opsegom; novu odluku traži samo kad je potrebna. Ne kontaktiraj osobe, ne uključuj troškove ili javni pristup na temelju ove upute.
- Predviđaj sljedeću ovisnost i provjeravaj rubne slučajeve. Pretpostavku označi kao pretpostavku; ne predstavljaj je kao korisnikovu odluku ili potvrđen rezultat.
- Odvajaj projektne podatke, ključeve, baze, repozitorije, objave i zadatke. Zajedničku tehniku prenesi tek nakon zasebne provjere i u opsegu naloga; nikad ne kopiraj poslovne podatke druge aplikacije.
- Ove datoteke su trajne projektne upute i provjerljivi zapisi. Nisu jamstvo automatskog učitavanja u svaki novi ChatGPT razgovor, savršenog pamćenja ili pozadinskog rada. Ako nastavak nema pristup repozitoriju, jasno navedi što ne možeš provjeriti.

## Granice ovog projekta

- Repozitorij: `antiquecroatianoak-sudo/Najjeftinija-kosarica`; zadana grana potvrđena 28.10.2026. i 5.11.2026. je `claude/dreamy-hopper-f6e4u0`. Uvijek je ponovno provjeri prije upisa.
- Odluka vlasnika 5.11.2026.: stara aplikacija je obrisana i napravljena nova od nule (vidi `PROJECT_STATE.md`). Struktura: `app/` (web aplikacija bez build koraka), `uvoz/` (dnevni uvoz, Python bez vanjskih paketa), `tests/`, `.github/workflows/dnevno.yml`.
- Poslovni tijek za provjeru posljedica: uvoz cjenika (`uvoz/uvoz.py`) → količine i jedinice (`uvoz/kolicina.py`) → grupe (`uvoz/grupe.json`) → popis glasom/upisom (`app/js/popis.js`) → rezultati A/B/C i zamjena (`app/js/usporedba.js`) → lokacija/karta, akcije, ušteda, dijeljenje → Pages i offline cache (`app/sw.js`).
- Količina pakiranja i broj pakiranja nisu isto. Ne miješati cijenu pakiranja s cijenom/kg/l/kom. Nedostajuća jedinica nije dozvola za izmišljanje pretvorbe.
- Sačuvaj ručni popis i odabire te zaštitu od starijeg/slabijeg cjenika (`--prethodni`, `ZastitaObjave`).
- Cijeli popis u jednoj stvarnoj poslovnici (lokacija uključena) razlikuj od procjene po lancu (uobičajena cijena lanca) i od kombinacije dviju trgovina.
- Trgovine ne plaćaju položaj; Premium i oglasi nikad ne mijenjaju poredak rezultata.
- Service worker smije upravljati samo svojim opsegom i cache prefiksom `kosarica-`; ne dirati cacheove drugih aplikacija.
- EUnekretnine2 i građevinski materijal nisu ovaj projekt. Ne mijenjati ih u sklopu zadatka za košaricu bez zasebno utvrđenog opsega.
- Prije spajanja/objave pokrenuti: `python3 -m unittest discover -s tests -p "test_*.py"`, `node --test tests/logika.test.mjs`, `node tests/preglednik.cjs app` (s podacima iz `tests/primjer.py` + `uvoz/uvoz.py`) i navesti ograničenja. Ovaj dokumentacijski postupak ne označava stare draft PR-ove kao pregledane niti nalaže njihovo spajanje.
