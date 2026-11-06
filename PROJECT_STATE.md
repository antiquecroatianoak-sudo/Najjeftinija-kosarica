# Najjeftinija košarica — glavni zapis stanja

## AKTUALNO: nova aplikacija od nule (5.11.2026.)

Provjereno: 5.11.2026. ~11:15 CET (Europe/Zagreb). Ovaj odjeljak je aktualan; odjeljak „Povijesno” niže opisuje obrisanu staru aplikaciju i ostaje samo kao trag.

### Odluka vlasnika (5.11.2026.)
Obrisati sav stari kod i napraviti novu aplikaciju od nule, bez ponovne upotrebe stare. Android-prijateljska (i u pregledniku), hrvatski jezik, spremna za više država (izbor u postavkama), pokretanje samo za Hrvatsku. Prvo mala radna verzija (baza cijena glavnih lanaca, glasovni popis, rezultati A i B, zamjena), zatim ostale funkcije. Trošak ≤ ~5 €/mj. Vlasnik ne programira i radi s Android mobitela; upute na jednostavnom engleskom.
Sačuvano iz starog: samo `AGENTS.md`, ovaj zapis (povijest) i radni tok `.github/workflows/claude-task.yml` (most za zadatke, nije kod aplikacije).

### Implementirano na grani `ccr-1c31c1df-63brmk` (nije spojeno, nije objavljeno)
- Uvoz (`uvoz/`): dnevne arhive cijene.dev (službeni cjenici NN 75/2025), ponovni pokušaji preuzimanja, odbacivanje loših cijena (0/apsurdne/>4× od uobičajene u lancu i među lancima), spajanje po barkodu pa marka+naziv+količina, količina samo ako je potvrđena jediničnom cijenom, ~55 grupa s podgrupama, Interspar odvojen od Spara (pretpostavka: vrsta poslovnice „hiper”), lanac koji danas nedostaje ili je <50 % jučerašnjeg uzima se iz arhive do 3 dana unatrag (status „stari”), zaštita objave ako je novi cjenik <60 % objavljenoga, izvješće o grešci (`izvjesce-greske.md`). Cijene stvarnih poslovnica kao razlike od uobičajene cijene lanca (datoteke po sadržaju u `data/hr/s/`), koordinate iz `senko/cijene-api` enrichment/stores.csv.
- Aplikacija (`app/`): glasovni (hr-HR) i upisani popis, zadane količine po grupi, zaključavanje, rezultati A/B/C, izbor lanaca, zamjena (odbijeni proizvod se preskače u A/B/C, „Vrati”), marka u izgovoru sužava grupu („Dukat mlijeko”, „nutella”), ne nudi pakiranje >2,5× tražene količine ako postoji primjereno, karta (Leaflet 1.9.4 iz npm-a, OSM pločice), lokacija i krug 2/5/10/20 km s cijenama stvarnih poslovnica (najbližih 60), ušteda (prosjek trgovina koje imaju sve stavke minus plaćeno), akcije, obiteljski popis poveznicom, slanje WhatsApp/Viber/SMS, prijava pogrešne cijene (GitHub issue ili kopiranje), status podataka, skener barkoda (BarcodeDetector + ručni unos), izvješće o grešci, izbor države, mjesto za oglas i opis Premiuma (bez naplate).
- Radni tok `.github/workflows/dnevno.yml`: provjere na svakoj grani i PR-u; na zadanoj grani dnevno 07:17 i 15:47 UTC uvoz → objava na Pages → provjera objavljene verzije; pri neuspjehu otvara/dopunjuje issue s oznakom `greška-objave`. Stari `dnevno-azuriranje.yml` obrisan.

### Testirano (lokalno, 5.11.2026., prije commita)
- `python3 -m unittest discover -s tests -p "test_*.py"`: 18 testova OK; prvi CI na `b9abb0c`: Python i Node prošli, test u pregledniku pao na provjeri rada bez interneta (test nije čekao da se cijene spreme); drugi CI pokazao da Playwright offline ne vrijedi za service worker – test sada simulira prekid isključivanjem poslužitelja (količine 310 g/31 kg, 6×1,5 l, duplikati, loše cijene, stari lanac, Interspar, grupe, koordinate, zaštita objave, service worker).
- `node --test tests/logika.test.mjs`: 13/13 OK.
- `node tests/preglednik.cjs app` (Chromium, Pixel 7) na velikom lokalnom primjeru (9 000 stvarnih naziva proizvoda iz enrichment, 338 stvarnih poslovnica, izmišljene cijene): sve provjere prošle, bez JS grešaka, bez vodoravnog pomicanja na 320/768 px, rad bez interneta iz spremljenih podataka.
- Razvrstavanje provjereno uzorkom na ~29 700 stvarnih naziva (enrichment): ~26 % bez grupe; poznate preostale greške manjeg opsega.
- GitHub Actions „Cijene i objava” na `daeeffe`: posao `provjere` USPJEŠAN (run 42008484834: Python, Node, preglednik na primjeru); `objava` preskočena jer grana nije zadana (ispravno).
- NIJE provjereno: stvarni uvoz s api.cijene.dev (mreža ove sesije ga blokira – prvi stvarni uvoz bit će u GitHub Actions), stvarni glasovni unos na Android uređaju, kamera/skener na uređaju, OSM pločice, objava na Pages.

### Spojeno i objavljeno (provjereno 5.11.2026. 11:28 CET, Europe/Zagreb)
- Uzrok vlasnikove pritužbe: sesije su se otvarale na zadanoj grani sa starom aplikacijom, a nova aplikacija nije bila spojena ni objavljena, pa je javna adresa i dalje prikazivala staru.
- Vlasnik je izričito naložio: „Merge the new web app and publish it.” [PR #16](https://github.com/antiquecroatianoak-sudo/Najjeftinija-kosarica/pull/16) (`ccr-1c31c1df-63brmk` → `claude/dreamy-hopper-f6e4u0`) spojen; merge commit `19fe4d7`.
- Prije spajanja, lokalno na `1120066`: 18 Python testova OK, logika 13/13, preglednik (primjer podataka) „SVE PROVJERE SU PROŠLE”.
- [Run 42009381562](https://github.com/antiquecroatianoak-sudo/Najjeftinija-kosarica/actions/runs/42009381562) na `19fe4d7`: `provjere` uspješne, `objava` uspješna. Pages deployment za `19fe4d7` „Reported success”; provjera objave: „Objavljena verzija podataka: 0f2fb9242a”.
- Prvi stvarni uvoz (arhiva 2026-11-05): 220 769 proizvoda, 1 464 poslovnice, 25 lanaca. Prethodni `meta.json` nije postojao (404 sa stare stranice), pa je usporedba zaštite objave ovaj put preskočena – očekivano za prvu objavu.
- Nalazi iz uvoza za provjeru: NTL 287 poslovnica, 0 s koordinatama (ne prikazuje se u krugu na karti); Studenac samo 20 poslovnica u arhivi; Eurospin 31/45 s koordinatama.
- Grana sesije `claude/claude-code-app-issue-bhn89z` premotana na `19fe4d7` i gurnuta.
- NIJE provjereno: otvaranje objavljene adrese na vlasnikovu Androidu (ova sesija nema pristup github.io), glas i kamera na uređaju, zamjena stare verzije u cacheu na vlasnikovu mobitelu (stari service worker koristio je `kosarica-v34`).

### Popravci nakon prve objave (5.11.2026. ~12:00 CET, Europe/Zagreb)
Nalog vlasnika: „Fix all the problems and continue with the app.”
- Dijagnoza izvora u GitHub Actions ([run 42011274811](https://github.com/antiquecroatianoak-sudo/Najjeftinija-kosarica/actions/runs/42011274811), privremeni radni tok, uklonjen nakon nalaza):
  - **Studenac:** i službeni `www.studenac.hr/cjenici/PROIZVODI-2026-11-05.zip` ima samo 20 datoteka poslovnica (kao arhiva cijene.dev). Nedostatak je na izvoru i ne može se popraviti uvozom; status podataka sad to navodi napomenom (`DJELOMICNO_OBJAVLJUJU`).
  - **Koordinate:** enrichment `stores.csv` nema nijednu NTL koordinatu; bez koordinata su i Gavranović (179), Ribola (61), Stridon (41), Trgovina Krk (14), Boso (14), Roto (9) i manji lanci (~650 poslovnica). Nominatim iz GitHub Actions radi; uzorak: točni kućni brojevi rang 30, dio samo ulica (rang 26), dio bez rezultata zbog adresa bez dijakritika/razmaka.
  - NTL je 5.11. imao 288 poslovnica, 4.11. 343 (razlika u izvoru; nije dalje istraženo).
- **Implementirano:** `uvoz/lokacije.py` – koordinate preko Nominatima za poslovnice bez dopune; prihvaća kućni broj (rang ≥ 28) ili samo kratku lokalnu ulicu, nikad glavnu cestu ni razinu grada; čišćenje adresa („Nikole16A”, „A.Senoe”); najviše 400 upita po pokretanju, 1/s; predmemorija `data/hr/lokacije.json` objavljuje se i čita sljedećim pokretanjem (`--lokacije`); neuspjeh se ponovno traži nakon 30 dana; kvar 429/403 prekida traženje bez rušenja uvoza. `meta.json` dobiva `lokacije` statistiku.
- **Grupe:** 9 novih grupa (žestoka pića, zimnica/masline, gotova jela, kakao napici, proteinski, kozmetika, kućanski potrošni, osvježivači/svijeće, protiv insekata) dodane na kraj popisa (postojeće razvrstavanje se ne mijenja), uz dopune riječi postojećim grupama. Na 29 684 stvarnih naziva iz enrichment: bez grupe 25,9 % → 14,6 %.
- **Testirano lokalno (prije commita):** Python 27 testova OK (9 novih u `tests/test_lokacije.py`), Node 13/13, preglednik „SVE PROVJERE SU PROŠLE”; uvoz s lažnim Nominatimom: 30/30 poslovnica s koordinatama i zapisan `lokacije.json`.
- **Nije provjereno:** stvarno popunjavanje koordinata dok ne prođe objava na zadanoj grani; točnost pojedinih OSM točaka na terenu.
- **Spojeno i objavljeno** (provjereno 5.11.2026. ~11:55 CET): [PR #17](https://github.com/antiquecroatianoak-sudo/Najjeftinija-kosarica/pull/17), merge `f89f163`; [run 42012381262](https://github.com/antiquecroatianoak-sudo/Najjeftinija-kosarica/actions/runs/42012381262) `provjere` i `objava` uspješni. Prvi krug lokacija: 399 upita, 73 kućni broj + 71 ulica, 126 nije nađeno (ponovno za 30 dana), 401 odgođeno za sljedeća pokretanja. Na karti nakon toga: NTL 22/287, Gavranović 91/173, Boso 6/14, Ribola/Roto/Stridon još odgođeni. Studenac napomena vidljiva u `meta.json`.
- **Nalaz:** provjera objave ispisala je istu verziju `0f2fb9242a` jer hash verzije nije uključivao koordinate; Pages deployment za `f89f163` je javio uspjeh, ali sama provjera verzije nije to dokazivala. Popravak: hash verzije sada uključuje broj koordinata po lancu (sljedeći commit).
- **Spojeno i objavljeno** (provjereno 5.11.2026. ~12:10 CET): [PR #18](https://github.com/antiquecroatianoak-sudo/Najjeftinija-kosarica/pull/18), merge `08da143`; [run 42014495372](https://github.com/antiquecroatianoak-sudo/Najjeftinija-kosarica/actions/runs/42014495372) uspješan; provjera objave: „Objavljena verzija podataka: 783bbceff0” (nova verzija, dokazuje novu objavu). Predmemorija lokacija pročitana s objavljene stranice (270 zapisa). Drugi krug: 46 kućni broj + 60 ulica, 143 nije nađeno, 152 odgođeno. Na karti: NTL 123/287, Gavranović 91/173, Ribola 0/61 i Roto 0/9 još na redu; glavni lanci 95–100 %.
- **Poboljšanje traženja adresa** (nalog vlasnika „Proceed.”, 5.11.2026. ~12:40 CET): dijagnoza [run 42019240935](https://github.com/antiquecroatianoak-sudo/Najjeftinija-kosarica/actions/runs/42019240935) na 45 od 269 neuspjelih adresa (NTL 164, Gavranović 82): „lanac u gradu” našao 29, ali u Slatini četiri različite NTL adrese → ista NTL trgovina (pogrešno bez provjere ulice); „ulica bez broja” 9–11, ali vraća i benzinsku/poštu/školu. Implementirano (`PRETRAGA = 2`): trgovina istog lanca na OSM-u prihvaća se samo ako je u istoj ulici (zadnja značajna riječ ulice), ulica bez kućnog broja samo kao lokalna ulica (`highway`), neuspjesi starije verzije traže se odmah ponovno; do 4 upita po adresi. Testovi: Python 32 OK (14 za lokacije), Node 13/13, preglednik OK.
- **Spojeno i objavljeno** (provjereno 5.11.2026. ~13:05 CET): [PR #19](https://github.com/antiquecroatianoak-sudo/Najjeftinija-kosarica/pull/19), merge `17be345`; [run 42020085720](https://github.com/antiquecroatianoak-sudo/Najjeftinija-kosarica/actions/runs/42020085720) uspješan, „Objavljena verzija podataka: 30a99c67b9”. Ponovno traženje 112 starih neuspjeha: 24 trgovina u istoj ulici + 2 ulica, 86 i dalje nije nađeno (sad zapamćeno 30 dana); 398 upita, 309 odgođeno. Na karti: NTL 129/287 (bilo 123), Gavranović 108/173 (bilo 91), Boso 7/14, Eurospin 40/45, Lidl 116/116; Ribola 0/61, Roto 0/9 i Stridon još na redu (zakazana pokretanja 07:17 i 15:47 UTC, ~100–130 novih adresa po pokretanju).
- **Razvrstavanje – „mlijeko” je dalo nešto što nije mlijeko”** (prijava vlasnika 5.11.2026.; nalog: popraviti univerzalno za sve artikle). Provjereno ~14:00 CET na kopiji objavljenog `proizvodi.json` (verzija 30a99c67b9, 220 769 proizvoda; privremena grana `dijagnoza-podaci`, obrisana): glasovni dio ispravno daje grupu Mlijeko; za „mlijeko 1 l” u svakom lancu pobjeđuje pravo mlijeko, pa točan slučaj vlasnika nije reproduciran. Ali grupa Mlijeko imala je 391 proizvod, od toga ~190 tuđih (vrčevi, posude, gelovi za tuširanje, losioni i mlijeka za sunčanje, šlag, čokolade, „Desert od bivoljeg mlijeka”, dojenačko mlijeko, hrana za mačke) – uzrok: riječ grupe bilo gdje u nazivu. Isti uzrok u drugim grupama (čarape → sir/sok, „Stolnjak fantastik” → sok, „Pršut Pivac” → pivo, zubna pasta → tjestenina, lak za nokte → luk…).
- **Implementirano (isto pravilo za sve grupe):** vrstu određuje prva riječ vrste u nazivu; riječ iza „za/s/sa/od/i/u/na/bez/okus…” (i iza „&”, „/”) ne određuje vrstu, osim kratice na početku („S.kruh”); popis `neprehrambeno` u `grupe.json` isključuje grupe s `"hrana": true` (11 neprehrambenih grupa označeno `"hrana": false`); `marke` vrijede tek kad nema riječi vrste (Milka, Kinder, Jamnica, Jana, „protein”, „smrznut”); uklonjeni suvišni `isk` koji su pod starim pravilom bili potrebni. Na stvarnih 220 769: promijenjeno 10 662, bez grupe 114 097 → 118 459 (uglavnom neprehrambeno izbačeno iz prehrambenih grupa); Mlijeko 391 → 198 (2 granična: „Maresi mlijeko za kavu”, „Aa h&b mlijeko”); jaja, banane, jabuke, krumpir, vrhnje, luk bez sumnjivih. Pregledani svi prijelazi u prehrambene grupe s ≥5 proizvoda.
- **Testirano:** Python 40 OK (novo `tests/test_razvrstavanje.py`, 8 testova sa stvarnim nazivima), Node 13/13, preglednik „SVE PROVJERE SU PROŠLE”.
- **Spojeno i objavljeno** (provjereno 5.11.2026. ~15:00 CET): [PR #20](https://github.com/antiquecroatianoak-sudo/Najjeftinija-kosarica/pull/20), merge `cced539`; [run 42048187521](https://github.com/antiquecroatianoak-sudo/Najjeftinija-kosarica/actions/runs/42048187521) `provjere` i `objava` uspješni; „Objavljena verzija podataka: b941fab1f9”; uvoz: 225 417 proizvoda, 1 520 poslovnica, 26 lanaca. Privremena grana `dijagnoza-podaci` (kopija objavljenih podataka) nije se dala obrisati iz sesije (remote je odbio brisanje) – vlasnik je može obrisati na GitHubu; ne sadrži tajne.
- **Otvoreno (razvrstavanje):** točan proizvod koji je vlasnik dobio nije poznat (moguće „sljedeći najjeftiniji”, poslovnica u krugu ili stara verzija u pregledniku); zatražiti snimku zaslona ako se ponovi. Ostaju rubni slučajevi (npr. „Orah kiflice” prije, „Kakao kreker”); grupe se i dalje mogu doraditi po prijavama.
- **Snimka zaslona vlasnika (5.11.2026. 16:06):** stavka „MLJEKO · 1 pakiranje” → „Jogurt 2.8% mm 200g mljekara marina”; uz to „Vino Arabella Merlot” 0,20 € i „Agnesi Spaghetti Integrale” 0,30 € u Konzumu. Uzroci: (1) prepoznavanje govora zapisalo je „mljeko”; aplikacija ga nije prepoznala kao grupu pa je tražila tekst „mljek…” i našla „**Mljek**ara Marina”; (2) vino i Agnesi prodaje samo 1 od 188 Konzuma, a u procjeni „Cijela HR” cijena te jedne poslovnice prikazivala se kao cijena Konzuma.
- **Implementirano:** `app/js/popis.js` – ijekavski/ekavski i zapis govora (`kanon`: ije/je→e) te jedno krivo slovo za riječi od 5+ slova samo kad je pogodak jednoznačan (`blizu`); „mljeko/mleko/mlieko/beli kruh/jogrut” → ispravna grupa, „salama/salata”, „sir/sirup” ostaju različiti. `app/js/usporedba.js` – procjena po lancu (`procjena`) kod lanca s 20+ poslovnica ne uzima proizvod koji prodaje samo 1 poslovnica (na stvarnim podacima 4–18 % asortimana velikih lanaca, Stridon 47 %, Studenac 25 %); stvarne poslovnice u krugu i dalje imaju sve cijene. Odbačeno nakon mjerenja: pravilo jedinične cijene po grupi (>1 000 lažnih pogodaka) i 5 %/3 poslovnice (preveliki gubitak). `app/sw.js` verzija 1.0.0 → 1.0.1 da mobiteli preuzmu novi kod.
- **Testirano:** Node 15/15 (2 nova testa), Python 40 OK, preglednik „SVE PROVJERE SU PROŠLE”.
- **Spojeno i objavljeno** (provjereno 5.11.2026. ~16:30 CET): [PR #21](https://github.com/antiquecroatianoak-sudo/Najjeftinija-kosarica/pull/21), merge `678bcde`; [run 42052797184](https://github.com/antiquecroatianoak-sudo/Najjeftinija-kosarica/actions/runs/42052797184) `provjere` i `objava` uspješni; Pages deployment za `678bcde` „Reported success”; „Objavljena verzija podataka: 4afab4e239”. Sljedeći korak: vlasnik ponovno izgovori „mlijeko” na mobitelu (nakon zatvaranja i ponovnog otvaranja kartice). Gotovo kad stavka glasi Mlijeko s 1 l, a ne „1 pakiranje”.
- **Rad po PLAN.md (nalog vlasnika 5.11.2026. ~17:00 CET):** vlasnik je zatražio rad dio po dio s `PLAN.md`; status svakog dijela i dokazi su u `PLAN.md`. Ukratko: Dio 1 – spajanje istog proizvoda pod više barkodova (objavljeno, 224 435 proizvoda, verzija 9418b45341); Dio 4 – lokacija jednim gumbom na glavnom zaslonu, rok 15 s, rezerva s cijenama lanaca (objavljeno PR #22); Dio 2/3/5/6 – glas (simulirano), komadi u razlomku, zadane količine po težini, razvrstavanje, oznaka neobično niske cijene, provjere sa stvarnim podacima (`tests/kupac.cjs`). Otvoreno: oglasi i Premium naplata (trebaju vlasnikove račune), obiteljski popis u stvarnom vremenu (treba bazu), potvrda prvog zakazanog pokretanja novog radnog toka.
- **Otvoreno (lokacije):** ~50 % novih adresa Nominatim ne nađe (adrese bez dijakritika, npr. „Brace Gojaka”); ostaju bez točke i ponovno se traže nakon 30 dana. Moguće poboljšanje: vraćanje dijakritika / OSM trgovine po marki. Preostalih 152 obradit će zakazana pokretanja (07:17 i 15:47 UTC).
- **Verzija 1.5.0 (nalog vlasnika 6.11.2026., provjereno 6.11.2026. 11:06 Europe/Zagreb):** „we won't show unusual low prices … use that logic in filtering” i šareniji početni zaslon s glavnim funkcijama (slanje popisa preko WhatsAppa, izbor osobe iz imenika).
  - **Implementirano:** `Baza.prihvatljiva(i, c)` u `app/js/usporedba.js` – neobično niska cijena više se ne označava nego **izostavlja**. Pravilo izmjereno na stvarnih 438 345 cijena (podaci c9348b8457): (1) isti proizvod u 3+ lanca, cijena ispod 1/4 njegove srednje cijene; (2) cijena po kg/l ispod 1/16 srednje cijene iste podgrupe ili 1/20 cijele grupe kad podgrupe nema. Izostavlja 204 cijene (npr. „Vino Arabella Merlot” 0,20 € u Konzumu, „Pileći batak-zabatak za gastro” 0,29 €/kg u Trgovini Krk, šećer 4 kg 0,02 €); stvarni kupac (`tests/kupac.cjs`) sad za piletinu dobiva 1,86 €/kg. Odbačeno nakon mjerenja: 1/8 po vrsti (836 pogodaka, među njima stvarne cijene – Balea losion 1,10 €, Ziaja gel) i 1/4 najjeftinijih 10 % (369, suncokretovo ulje, šampon 0,99 €) – grupe miješaju vrlo različite proizvode. Pravilo se primjenjuje: A (i rang-lista za zamjenu), B, C, akcije, favoriti, „Blizu tebe” i tablica u detaljima proizvoda (uz napomenu koliko je cijena izostavljeno). Granica se računa jednom po proizvodu (`izracunajGranice`). Početni zaslon: prazan popis → 4 šarene pločice (Akcije tjedna, Skeniraj barkod, Favoriti, Obiteljski popis); s popisom → kartica „Pošalji popis obitelji” s pločicama WhatsApp (wa.me, osobu bira WhatsApp), Iz imenika (Contact Picker API, Chrome na Androidu; broj → međunarodni oblik `brojZaWhatsApp`, npr. 091… → 38591…, zatim WhatsApp ili SMS toj osobi; gdje preglednik ne daje imenik – izbor WhatsApp/Viber/SMS), Viber, SMS i ostalo. Šareniji glasovni okvir i koraci. Verzija 1.4.0 → 1.5.0 (sw.js i greske.js).
  - **Testirano lokalno:** Python 47 OK; Node 18/18 (testovi za oba pravila: A, B, C, akcije); preglednik „SVE PROVJERE SU PROŠLE” uključujući pločice, WhatsApp poveznicu s popisom i simulirani imenik (Mama, 091 234 5678 → wa.me/385912345678). NIJE provjereno: stvarni imenik na Android mobitelu (Contact Picker postoji samo u Chromeu na Androidu).

### Otvoreno / zapreke
- ~~Za objavu: spojiti granu u `claude/dreamy-hopper-f6e4u0`~~ – riješeno PR-om #16 (vidi gore).
- Paralelno: druga sesija radi na grani `ccr-c6eb8592-ad02ds` („izvorna Android aplikacija v0.2”, vlastiti radni tok `android.yml`). Vlasnik je za objavu odabrao web aplikaciju (5.11.2026.); Android grana nije spojena i temelji se na staroj aplikaciji (`dc75f54`).
- Draft PR #7 i #4 odnose se na obrisanu staru aplikaciju; nakon spajanja nove aplikacije postaju zastarjeli (ne zatvarati bez vlasnika).
- Oglasi, Premium naplata i obiteljski popis u stvarnom vremenu nisu povezani (trebaju vlasnikove račune/uslugu).

### Sljedeći konkretni korak
Spajanje i objava su gotovi (vidi gore); popravci PR #17/#18 objavljeni. Sljedeće: vlasnik otvara https://antiquecroatianoak-sudo.github.io/Najjeftinija-kosarica/ na Androidu (ako se prikaže stara aplikacija, zatvoriti karticu i ponovno otvoriti). Gotovo kad: na mobitelu se vidi nova aplikacija, status podataka pokazuje 5.11.2026., a A/B/C daju stvarne cijene. Zatim: nakon zakazanih pokretanja provjeriti `s_koordinatama` za Ribolu, Roto i Stridon u `meta.json`; poboljšati pronalazak adresa bez dijakritika.

---

## Povijesno: stara aplikacija (obrisana 5.11.2026.)

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
- 5.11.2026.: na zahtjev vlasnika stara aplikacija obrisana na grani `ccr-1c31c1df-63brmk`; nova aplikacija opisana u odjeljku „AKTUALNO”.
