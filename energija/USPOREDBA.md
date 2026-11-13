# Usporedba s tržišnim pristupima – metodologija i rezultati

## Što se može, a što ne može pošteno tvrditi

Rezultati zatvorenih komercijalnih aplikacija pod jednakim uvjetima ne postoje u javnom obliku. Njihov kod se ne može pokrenuti u ovom simulatoru, a proizvođači ne objavljuju usporedive testove. Zato se ovdje **ne tvrdi** da sustav nadmašuje bilo koju imenovanu aplikaciju.

Uspoređuje se s **referentnim strategijama**: ponašanjem koje tipični sustavi na tržištu nude prema javnoj dokumentaciji. Sve se izvodi na istim scenarijima, u istom simulatoru i s istim mjerilima:

| Strategija | Što radi |
|---|---|
| `vlastita` | Zadani način hibridnog izmjenjivača (baterija pokriva razliku sunca i potrošnje), bojler na NT tajmeru, navodnjavanje na tajmeru u 7 h, bez nadzora ograde i struje pumpe. Aparat pastira je trajno priključen. |
| `tou` | Kao `vlastita`, uz prisilno punjenje baterije iz mreže u jeftinoj tarifi (ToU raspored). |
| `cjenovni_prag` | Dinamička tarifa: puni ispod 25. percentila cijena, čuva ispod medijana, bojler u 3 najjeftinija sata. |
| `pametna` | Ova jezgra. |
| `granica` | Procjena: optimalna baterija uz **savršeno znanje budućnosti** (satni model, ista potrošnja). Pokazuje koliko se uopće moglo postići. Ne uzima u obzir zabranu punjenja na mrazu, pa je u hladnom valu napuhana. |

Pokretanje: `python3 -m scenariji.usporedba --izlaz rezultati/`. Svih 18 scenarija s 4 strategije izvodi se paralelno, za oko 4 minute.

## Mjerila (sva: niže = bolje)

- **Trošak:** satni neto obračun mreže + trošenje baterije (0,03 €/kWh protoka) − vrijednost promjene napunjenosti na kraju razdoblja (prosječna izvozna cijena, ista za sve strategije).
- **Udobnost:**
  - minute bez tople vode dok su stanari tu (spremnik ispod oko 19 °C ekvivalenta),
  - sati u kojima je zona tla ispod 22 % vlage (stres biljaka).
- **Pouzdanost:** udio ograde pod naponom iznad 4 kV (mjereno u simulatoru, a ne kako ga vidi jezgra), neisporučena energija i sigurnosna kršenja.

**Ocjena je višekriterijska (Pareto)**, s pragom šuma (2 cente, 15 min, 1 h, 10 Wh, 0,2 %):

| Ishod | Značenje |
|---|---|
| dominira | Bolja od svake referentne strategije: nije lošija ni po jednom mjerilu, a bolja je po barem jednom. |
| nenadmašena | Nijedna referentna strategija nije bolja po svemu; neka je bolja po nekom mjerilu. Kompromis se navodi u tablici. |
| nadmašena | Neka referentna strategija nije lošija ni po čemu, a bolja je po barem jednom mjerilu. |

## Što je usporedba otkrila i kako je popravljeno

| Nalaz | Popravak | Učinak |
|---|---|---|
| Ljeti noću baterija se praznila za jeftinu NT tarifu, a sutra se punila suncem koje bi se inače izvezlo. Ciklus je skuplji od kupnje. | Vrijednost kWh u bateriji je izvozna cijena / učinkovitost + **dvostruko** trošenje (pražnjenje i ponovno punjenje). | Toplinski val: −2,45 € → −7,62 € |
| Neiskorišteni večernji skokovi i negativne podnevne cijene. | Prodaja iz baterije kad izvoz vrijedi više od energije kasnije; sigurnosni faktor 1,5–2 na prognozu potrošnje; nikad na mrazu (nemoguće ponovno puniti). | Volatilne cijene: −0,56 € → −2,11 € |
| Prodaja iz baterije u hladnom valu, a zatim kupnja po 1 €/kWh. | Bez prodaje dok je punjenje fizički nemoguće ili dok navike nisu naučene. | Hladni val: 19,28 € → 16,93 € |
| Topla voda: bojler se grijao tek kad bi netko stigao; pomični prozor stalno je odgađao grijanje. | Osjetnik spremnika; udobnost ispod 42 °C dok su stanari tu; u fazi učenja fiksni rok do 15 h. | Tjedan bez sunca: 1050 → 0 min bez tople vode; zima s dinamičkom tarifom: 162 → 42 min |
| Otočni rad: SoC točno 15 % zaključao je bateriju prije isključenja trošila. | Kaskada isključivanja do soc_min + 2 %; kritična trošila smiju do 7 %. | Ljeto bez mreže: 1,6 → 0 kWh neisporučeno |
| Otočni rad: bojler + kuhanje iznad snage izmjenjivača (3 kW). | Upravljanje vršnom snagom; rezerva za kućni vrh u satima kad je vrh vjerojatan. | 0 kWh neisporučeno; manje minuta bez tople vode od referentnih (408 prema 746) |
| Lažna uzbuna o starenju baterije iz 5 dana šuma. | Theil–Sen nagib, najmanje 7 dana podataka; scenarij sada provjerava i lažne uzbune. | Starenje prepoznato kad postoji, šutnja kad ne postoji |
| Mjerilo ograde „sve dionice ispravne” nije razlikovalo izoliranu dionicu od ugašene ograde. | Mjeri se udio ograde pod naponom. | Prednost izolacije je sada vidljiva (98,2 % prema 95,0 % u oluji) |

Isprobano, ali odbačeno jer nije pomoglo: kratkoročna korekcija prognoze iz stvarne proizvodnje (nowcasting) i rubni AI kao zamjena za profil navika.

## Rezultati

Vidi `rezultati/usporedba.md` iz zadnjeg pokretanja. Sažetak je u `STANJE.md`, uz commit i datum.

## Ograničenja

- Sve vrijedi **u simulatoru**. Stvarni hardver, stvarne navike i stvarne cijene mogu dati drugačije brojke; vidi `SPREMNOST.md`.
- Referentne strategije su pojednostavljene; stvarni proizvodi mogu imati dodatne funkcije.
- Granica je satni model, a ne stvarni optimum (bez mraza, bez vršne snage, bez ograničenja izvoza).
- Prodaja iz baterije u mrežu ovisi o uvjetima priključka. Kad nije dopuštena (`politika.izvoz_iz_baterije = false`), dio ušteda u dinamičkim scenarijima nestaje.
