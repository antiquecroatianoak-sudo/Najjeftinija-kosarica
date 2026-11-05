# Najjeftinija košarica — glavni zapis stanja

Provjereno: 28.10.2026. 14:36 CET (Europe/Zagreb). Prije nastavka ponovno provjeriti autoritativnu granu i objavu. Ovaj zapis zamjenjuje stare sažetke samo za činjenice ovdje potvrđene.

## Identitet i odvajanje
- GitHub: `antiquecroatianoak-sudo/Najjeftinija-kosarica`.
- Aktivna zadana/produkcijska grana potvrđena GitHubom: `claude/dreamy-hopper-f6e4u0`; ne pretpostavljati `main`.
- URL iz aktualnog README-ja: https://antiquecroatianoak-sudo.github.io/Najjeftinija-kosarica/
- Runtime u `site/`, uvoznik u `scripts/azuriraj_cijene.py`. Aktualni `site/sw.js` navodi prefiks `kosarica-`, cache `kosarica-v34` i opseg vlastite aplikacije.
- Oznaka v34 potvrđena je u izvornom kodu; ovaj nastavak nije ponovno potvrdio posljednji Pages deploy ni verziju na korisnikovu uređaju.
- EUnekretnine2 i građevinska aplikacija imaju zasebne repozitorije, poslovna pravila, podatke i objave. Ne prenosi njihove zadatke ili tajne ovamo.

## Dogovorena pravila
- Uspoređivati isti korisnikov popis i količine. Razlikovati broj pakiranja, veličinu pakiranja i jediničnu cijenu kg/l/kom.
- Cijenu i količinu prikazivati po dokazivom podatku izvora, bez izmišljene pretvorbe ili jedinice.
- „Sve u jednom dućanu” treba označavati cijeli popis u jednoj stvarnoj poslovnici. Procjenu po lancu iz više poslovnica jasno odvojiti.
- Sačuvati ručni popis i odabire; glasovni unos mora imati razumljiva stanja i greške.
- Izolirati service worker i cache u vlastiti prefiks/opseg. Ne brisati podatke drugih aplikacija.
- Ne tvrditi da su svi cjenici, količine, klasifikacije, glasovni unos ili offline ponašanje provjereni bez konkretnog dokaza.
- Nova dostava ili dogovaranje s trgovinama nije dio ovog kontinuitetskog zadatka; ne implementirati iz proturječnih povijesnih sažetaka.

## Potvrđeno spojeno u repozitorij
| Promjena | Dokaz | Što ova provjera ne dokazuje |
|---|---|---|
| Stvarne cijene i ukupna košarica po poslovnici | [PR #12](https://github.com/antiquecroatianoak-sudo/Najjeftinija-kosarica/pull/12), merged | Aktualnu kvalitetu svih uvoznih redaka |
| Karta, lokacija/radijus, kombinacija poslovnica, filtar marke i izolacija cachea | [PR #14](https://github.com/antiquecroatianoak-sudo/Najjeftinija-kosarica/pull/14), merged; aktualni sw.js potvrđuje vlastiti prefiks | Provjeru svih funkcija na uređaju i izolaciju druge aplikacije |
| Zaštita od starijeg/slabijeg cjenika i službeni datum prije 8:00 | [PR #15](https://github.com/antiquecroatianoak-sudo/Najjeftinija-kosarica/pull/15), merged | Uspješan posljednji dnevni uvoz ili Pages deploy |

Ispravak starog sažetka: lokacija/radijus i filtar marke nisu samo plan; PR #14 je spojen. Ne tražiti njihovu ponovnu implementaciju bez provjere postojećeg koda.

## Otvoreno i nepotvrđeno
- [PR #7](https://github.com/antiquecroatianoak-sudo/Najjeftinija-kosarica/pull/7) je otvoren draft: korekcija količine kada naziv i polje odstupaju točno 10×/100×/1000×, uključujući prijavu kruha 310 g prikazanog kao 31 kg. Nije spojen; ne opisivati popravak kao objavljen. Aktualni head `3488107840821f5928dcdd5caece9d5fe1d3f100`.
- Autor PR #7 navodi da bilježnica prikazana kao 42 l zahtijeva izvorne retke; naziv bez količine nije dovoljan za sigurnu korekciju. To ostaje nalaz za provjeru.
- [PR #4](https://github.com/antiquecroatianoak-sudo/Najjeftinija-kosarica/pull/4) je otvoren draft komunikacijskog testa; ne spajati/objavljivati kao funkcionalni popravak.
- Glasovni unos, potpunost/klasifikacija cjenika i ponašanje na mobitelu/offline nisu ponovno ispitani ovim dokumentacijskim zadatkom.
- Povijesni zapis spominje ovisnost o zasebnom popravku građevinske aplikacije. Njezino sadašnje stanje nije potvrđeno ovdje; ne tvrditi da je međusobna izolacija potpuno provjerena.

## Sljedeći konkretan korak
Pregledati PR #7 i usporediti ga s aktualnom produkcijskom granom. Provjeriti stvarne/sintetičke retke polja i dopune, očuvanje multipakiranja te primjere 310 g/31 kg i nedostajuće/nevaljane jedinice. Prije spajanja potvrditi relevantne testove na aktualnom headu i svježi uvoz/Pages ishod. Ne gurati stari lokalni commit preko remotea.

## Provjera posljedica prije izmjene
| Dio tijeka | Što provjeriti |
|---|---|
| Uvoz | Datum i potpunost izvora, količine/jedinice, barkodovi, zaštita od starog/slabijeg cjenika |
| Izračun | Isti popis i količine, ukupna cijena i cijena/kg/l/kom, multipakiranja, puna poslovnica nasuprot kombinaciji |
| Spremanje | Ručni popis i odabiri, prekid rada, prethodne valjane cijene |
| Sučelje i glas | Jasno slušanje/greška, dostupnost poslovnica, odsutne stavke, mobilna usporedba |
| Objava i offline | Točna produkcijska grana, Pages ishod, vlastiti service-worker scope/cache i odsutnost učinka na drugu aplikaciju |

## Zapis nastavka
- 28.10.2026.: uspostavljen zaseban glavni zapis na zahtjev vlasnika. Provjereni su identitet/grana, aktualni README, sw.js i stanja PR-ova; aplikacijski kod, cjenici i objava nisu mijenjani ovim zadatkom.
- Sljedeća cjelina dodaje odluku, implementaciju, točan dokaz testiranja, objavljenu verziju ili izričito „nije objavljeno”, otvoreno i sljedeći korak.

## Zapis 5.11.2026. 10:08 CET (Europe/Zagreb) — plan za Google Play
- Zahtjev vlasnika: plan u 5 koraka (plan i troškovi → prva verzija na mobitelu → svi lanci i funkcije → zatvoreni test na Google Playu → objava).
- Izrađen samo plan: `docs/google-play-plan.md`. Predloženi pristup je TWA (Bubblewrap) oko postojećeg PWA-a, bez poslužitelja. Status: **planirano**; ništa nije implementirano, testirano ni objavljeno.
- Troškovi: Google Play račun 25 USD jednokratno; poslužitelj 0 € (Pages + Actions); domena opcionalna. Zahtjev zatvorenog testa za nove osobne račune je prema sekundarnim izvorima 12 testera kroz 14 dana; prije testa provjeriti u Play Consoleu. Nove aplikacije moraju ciljati API 36 od 31.8.2026. (developer.android.com).
- Zapreka: TWA traži `/.well-known/assetlinks.json` u korijenu domene; projektni Pages URL to ne pokriva. Potrebna je odluka (korisnička Pages stranica ili vlastita domena).
- Nije provjereno: mreža ove sesije blokira github.io (403), pa živa verzija i datum cjenika nisu potvrđeni.
- Sljedeći korak: vlasnik potvrđuje pristup, ID aplikacije i domenu. Zatim slijedi korak 2 (TWA build + assetlinks). Gotovo kad APK radi na vlasnikovu mobitelu i testovi u `tests/` prolaze.

## Zapis 5.11.2026. 10:20 CET (Europe/Zagreb) — korak 2: probna Android aplikacija
- Vlasnik je odobrio TWA pristup i troškove. ID aplikacije `hr.najjeftinijakosarica.app` i domena github.io korišteni su kao **pretpostavka** (prijedlog), još nisu izričito potvrđeni. ID je reverzibilan do prvog uploada na Google Play.
- Implementirano: `android/` (android-browser-helper 2.5.0, AGP 8.10.1, target/compile SDK 36) i `.github/workflows/android.yml` (APK + AAB; trajni ključ iz tajni `ANDROID_KEYSTORE_B64` itd., inače privremeni ključ po pokretanju). Upute: `docs/android-instalacija.md`.
- Dokaz: run [42000408675](https://github.com/antiquecroatianoak-sudo/Najjeftinija-kosarica/actions/runs/42000408675) na commitu `a011f0a` je success; artefakt `kosarica-android-1` (APK + AAB) vrijedi do 5.12.2026. Postojeći testovi u `tests/` (14) lokalno prolaze; `site/` nije mijenjan.
- Nije testirano: instalacija i rad na stvarnom mobitelu. Bez assetlinks.json na korijenu domene aplikacija prikazuje traku s adresom. Ništa nije spojeno u produkcijsku granu ni objavljeno na Google Play.
- Sljedeći korak: vlasnik instalira APK i javi rezultat provjera iz `docs/android-instalacija.md`; odluka o domeni za assetlinks. Gotovo kad aplikacija radi na vlasnikovu mobitelu.

## Zapis 5.11.2026. (Europe/Zagreb) — instalacija nezadovoljavajuća, odluka o javnoj poveznici otvorena
- Vlasnik javlja da trenutačni način preuzimanja/pokretanja „nije dobar” (artefakt traži prijavu na GitHub i zip). Točan neuspjeli korak još nije poznat.
- Pripremljena, ali **nije spojena ni gurnuta**: GitHub Release `proba` sa stalnom javnom poveznicom na APK. Zaustavljena jer otvara javni pristup bez izričitog odobrenja vlasnika (AGENTS.md). Zakrpa postoji samo u privremenom spremniku sesije; ako nestane, promjenu treba ponovno napisati.
- Sljedeći korak: vlasnik bira javnu poveznicu ili privatni put, i navodi što točno ne radi (preuzimanje, instalacija ili sama aplikacija).

## Zapis 5.11.2026. 10:25 CET (Europe/Zagreb) — javna poveznica za probni APK
- Vlasnik je izričito odobrio javnu poveznicu. Commit `13ac171`, run [42001605523](https://github.com/antiquecroatianoak-sudo/Najjeftinija-kosarica/actions/runs/42001605523) success.
- Objavljeno: GitHub prerelease `proba` s `najjeftinija-kosarica.apk` (458 379 B). Bez prijave preuzeto i provjereno: HTTP 200, potpisan APK. Poveznica: https://github.com/antiquecroatianoak-sudo/Najjeftinija-kosarica/releases/download/proba/najjeftinija-kosarica.apk
- Nije testirano: instalacija i rad na vlasnikovu mobitelu.

## Zapis 5.11.2026. (Europe/Zagreb) — nesporazum: vlasnik traži novu aplikaciju
- Vlasnik javlja da probni APK nije „nova aplikacija” prema uputama koje je poslao „iz oblaka”. U ovom razgovoru primljen je samo odjeljak „14. Steps” (koraci 1–5); odjeljci 1–13 nisu primljeni. U repozitoriju, issueima i PR-ovima nije nađena nova specifikacija.
- Ono što je izgrađeno (TWA u `android/`, release `proba`) samo omata **postojeću** web-aplikaciju. To je pretpostavka iz ovog razgovora, ne vlasnikova specifikacija.
- Sljedeći korak: vlasnik dostavlja potpune upute (odjeljke 1–13). Zatim slijedi usporedba sa zatečenim stanjem i odluka o tome što se zadržava. Release `proba` ostaje javan dok vlasnik ne odluči drukčije.

## Zapis 5.11.2026. 11:00 CET (Europe/Zagreb) — vlasnikove upute pronađene; izvorna Android aplikacija v0.2
- Vlasnikove potpune upute (odjeljci 1–14) nalaze se u njegovu Claude Docs dokumentu „Najjeftinija košarica – upute za Claude Code” (https://claude.ai/artifact/5gXoqhEjcWGtgPThjskNMV). Traže **izvornu Android aplikaciju** (Material 3), mali server do ~5 €/mj., premium, oglase, admin i sl. Prvi odgovor u ovom razgovoru primio je samo odjeljak 14. Zato je TWA omotač bio pogrešna pretpostavka; zamijenjen je.
- Plan i troškovi prepisani prema uputama: `docs/google-play-plan.md`.
- Implementirano (korak 2, prva verzija):
  - `android/jezgra`: čista Kotlin logika s 12 JVM testova; lokalno prošlo 5.11. — razumijevanje popisa, količine i brojevi riječima, najmanji trošak za količinu, najjeftinije ukupno, sve u jednom lancu, ušteda, bez pretvorbe kg↔l.
  - `android/app`: Kotlin/Compose — glas hr-HR i upis, odabir lanaca, zamjena sljedećim najjeftinijim, slanje, ugrađeni katalog za rad bez interneta i osvježavanje.
  - `scripts/app_katalog.cjs` s testom `tests/app-katalog.cjs` gradi katalog iz objavljenog `proizvodi.json` po istim pravilima `site/skupine.js`. Dodan je samo izvoz `zaAplikaciju`; postojeći testovi (15 datoteka) prolaze.
- Prvi lanci: Kaufland, Konzum, Lidl, Plodine, Spar. Katalog 5.11.2026.: 26.201 proizvoda; Lidl samo 632 — slab izvor, istražiti u koraku 3.
- Cijena u aplikaciji je **najniža objavljena u lancu** (označeno u sučelju). Stvarna poslovnica, radijus i karta dolaze u koraku 3.
- Dokazi: CI [42005820823](https://github.com/antiquecroatianoak-sudo/Najjeftinija-kosarica/actions/runs/42005820823) na `c85785f`: build + proba na emulatoru (API 34) uspješni, bez rušenja; snimke uz release `proba`. Javni APK: `releases/download/proba/najjeftinija-kosarica.apk`; katalog: `releases/download/podaci/katalog.json.gz`.
- Nije testirano: vlasnikov mobitel; glasovni unos na stvarnom uređaju. Na emulatoru je osvježavanje kataloga javilo „nema veze”; razlog se istražuje.
- Nije spojeno ni objavljeno na Google Play. Dnevno osvježavanje kataloga za aplikaciju tek nakon spajanja u produkcijsku granu (raspored radi samo na zadanoj grani).
- Sljedeći korak: vlasnik instalira APK i javi što ne valja. Zatim korak 3 prema planu. Gotovo kad aplikacija radi na vlasnikovu mobitelu.

## Zapis 5.11.2026. 11:20 CET (Europe/Zagreb) — proba na emulatoru i sumnjive cijene
- Na emulatoru su se kao najjeftinije pojavile nemoguće cijene (Kaufland: tost 600 g 0,21 €, mlijeko 0,27 €/l). Katalog sad izbacuje ponude ispod 30 % ili iznad 10× medijana jedinične cijene skupine (min. 8 ponuda); test u `tests/app-katalog.cjs`.
- CI [42008408730](https://github.com/antiquecroatianoak-sudo/Najjeftinija-kosarica/actions/runs/42008408730) na `4fd3804`: build, testovi jezgre i proba na emulatoru uspješni, bez rušenja. Osvježavanje kataloga s interneta radi. Katalog: 24.434 proizvoda.
- Upis „kruh, 2 litre mlijeka, 6 jaja, pola kile sira, xyzzy” daje tost 500 g 0,70 €, 2 × 1 l mlijeka 1,08 €, 6 jaja 1,59 € (akcija) i 2 × 250 g svježeg sira 2,58 €. Ukupno 5,95 €; „xyzzy” je označen kao nepronađen, nije tiho preskočen.
- Nije testirano: vlasnikov mobitel, glasovni unos na stvarnom uređaju, slanje preko Vibera/WhatsAppa.
