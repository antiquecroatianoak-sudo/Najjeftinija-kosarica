# Unaprijed zadani kriterij: „značajno nadmašuje konkurenciju”

Zapisano 13.11.2026., **prije** statističke analize, da se kriterij ne može prilagoditi rezultatima.
Odluka vlasnika: optimizacija je uspješna samo ako sustav značajno nadmašuje konkurenciju.

## Usporedni sustavi

- Referentne strategije iz `scenariji/usporedba.py`: `vlastita`, `tou`, `cjenovni_prag`. One oponašaju ponašanje tržišnih sustava prema javnoj dokumentaciji.
- Ako se omogući, i stvarni otvoreni optimizator (EMHASS) pokrenut u istom simulatoru.
- Zatvoreni komercijalni sustavi ne mogu se pokrenuti u simulatoru. Za njih se uspoređuje samo funkcionalnost, prema javnoj dokumentaciji (vidi `USPOREDBA_FUNKCIJA.md`).

U svakom scenariju „najbolji konkurent” je strategija s najnižim troškom.

## K1 – trošak (primarni)

1. Za scenarije s mrežom i definiranom granicom računa se **udio ostvarive uštede**:
   `U(s) = (trošak_vlastita − trošak_s) / (trošak_vlastita − granica)`.
2. U obzir ulaze samo scenariji u kojima je raspon `trošak_vlastita − granica` barem 0,50 €. U manjem rasponu udio je samo šum.
3. Razlika po scenariju: `Δ = U(pametna) − U(najbolji konkurent)`.
4. **Uspjeh K1** zahtijeva oba uvjeta:
   - **medijan Δ ≥ 0,10** (barem 10 postotnih bodova više ostvarive uštede),
   - jednostrani **test predznaka** (bolje / lošije, a izjednačeni |Δ| < 0,02 izostavljaju se) s **p < 0,05**.

## K2 – pouzdanost i udobnost (uvjet)

U nijednom scenariju naš sustav ne smije biti lošiji od najboljeg konkurenta iznad praga šuma, i to ni po jednom od ovih mjerila:
- neisporučena energija: prag 10 Wh,
- ograda pod naponom: prag 0,2 %,
- minute bez tople vode: prag 15 min,
- sati stresa biljaka: prag 1 h,
- sigurnosna kršenja: 0.

Dodatno, u scenarijima s kvarom ograde pokrivenost mora biti bolja od svih konkurenata.

## Odluka

- **Optimizacija uspješna:** K1 i K2 su oba ispunjena.
- **Djelomično:** ispunjen je samo jedan. Navodi se točno koji.
- **Neuspješna:** nije ispunjen nijedan.

Ishod se upisuje bez obzira na to je li povoljan.

## Dopuna 13.11.2026. – nakon 1. ocjene, PRIJE 2. ocjene (skup 2028.)

**Nalaz na razvojnim tjednima (2026.), ne na skupovima za ocjenu:** pokus isključivanja pokazao je da cijelu prednost
konkurenta u trošku kod obične dinamičke tarife daje lošija usluga. Pravilo „3 najjeftinija sata” za bojler ostavlja
stanare oko 17 h tjedno bez tople vode. Uz jednako pravilo za bojler naše upravljanje je 8 % jeftinije.
K1 je, dakle, uspoređivao trošak uz nejednaku uslugu.

- **Presuda 1. ocjene (2027.) ostaje: DJELOMIČNO.** Ne mijenja se.
- Za **2. ocjenu (2028.)** računaju se oba:
  - **K1:** nepromijenjen. Konkurenti kakvi jesu.
  - **K1‑R:** isti test i pragovi, ali konkurenti dobivaju isto jamstvo tople vode kao naša jezgra
    (`--ravnopravno`), pa se uspoređuje samo upravljanje energijom.
- **Odluka za 2. ocjenu:** optimizacija upravljanja energijom je **USPJEŠNA** ako vrijede K1‑R i K2. Ishod K1 navodi se
  uz nju, bez obzira na to kakav je.
