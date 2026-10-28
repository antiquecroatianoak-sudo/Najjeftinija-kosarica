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
