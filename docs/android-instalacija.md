# Probna Android aplikacija — kako je instalirati na mobitel

Napisano 5.11.2026. (Europe/Zagreb). Ovo je **probna** verzija (korak 2 plana u `docs/google-play-plan.md`), nije s Google Playa.

Od 5.11.2026. ovo je **izvorna Android aplikacija** (Kotlin/Compose) prema vlasnikovim uputama, a ne više web-stranica u omotaču. **Prije instalacije deinstaliraj prethodnu probnu verziju** (isti naziv, drugi potpis).

## Preuzimanje (jedna poveznica, bez prijave)
Na mobitelu u Chromeu otvori:

**https://github.com/antiquecroatianoak-sudo/Najjeftinija-kosarica/releases/download/proba/najjeftinija-kosarica.apk**

Poveznica uvijek vodi na zadnju probnu verziju. GitHub je sam izgradi nakon svake promjene u mapi `android/` (radni tijek **Android aplikacija (TWA)**).

## Instalacija
1. Kad preuzimanje završi, dodirni `najjeftinija-kosarica.apk` (obavijest ili Chrome → Preuzimanja).
2. Android pita smije li ta aplikacija (npr. Chrome ili Datoteke) instalirati nepoznate aplikacije → **Postavke** → uključi **Dopusti iz ovog izvora** → natrag → **Instaliraj**.
3. Ako Play Protect upozori na nepoznatog razvojnog programera → **Više pojedinosti** → **Ipak instaliraj**. To je očekivano za probnu verziju izvan Google Playa.
4. Otvori **Najjeftinija košarica** s početnog zaslona.

## Što je normalno u probnoj verziji
- **Samo nekoliko velikih lanaca**: Konzum, Lidl, Kaufland, Spar i Plodine. Svi lanci dolaze u koraku 3.
- **Cijena je najniža objavljena u lancu**, ne cijena pojedine poslovnice. Poslovnice, karta i radijus dolaze u koraku 3.
- **Svaka nova probna verzija ima drugi privremeni potpis.** Prije instalacije nove verzije deinstaliraj staru. Popis spremljen u aplikaciji tada se gubi. Trajni ključ uvodimo prije Google Playa.
- **Cijene se osvježavaju** kad se aplikacija otvori uz internet. Novi katalog nastaje pri svakoj novoj izgradnji aplikacije; svakodnevno automatsko osvježavanje uključuje se spajanjem u glavnu granu.

## Što provjeriti i javiti
- Otvara li se aplikacija i učitavaju li se cijene.
- 🎤 glasovni unos: pita li za mikrofon, razumije li stavke.
- Razumije li količine („2 litre mlijeka”, „pola kile sira”, „6 jaja”), odabir trgovina, „Najjeftinije ukupno” i „Sve u jednom lancu”, dodir za sljedeći najjeftiniji, gumb „Pošalji”.
- Ostaje li popis spremljen nakon zatvaranja aplikacije.
- Radi li bez interneta (zrakoplovni način) s već učitanim cijenama.
