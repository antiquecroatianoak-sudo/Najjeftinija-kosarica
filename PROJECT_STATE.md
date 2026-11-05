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
