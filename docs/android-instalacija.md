# Probna Android aplikacija — kako je instalirati na mobitel

Napisano 5.11.2026. (Europe/Zagreb). Ovo je **probna** verzija (korak 2 plana u `docs/google-play-plan.md`), nije s Google Playa.

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
- **Gore se vidi traka s adresom.** Android tek tada potvrdi da aplikacija i web-stranica pripadaju istom vlasniku, kad na korijenu domene postoji datoteka `/.well-known/assetlinks.json`. Na adresi `…github.io/Najjeftinija-kosarica/` to još ne postoji (odluka o domeni je otvorena).
- **Svaka nova probna verzija ima drugi privremeni potpis.** Prije instalacije nove verzije deinstaliraj staru. Popis u staroj aplikaciji tada se gubi. Trajni ključ uvodimo prije Google Playa.
- Potreban je Chrome na mobitelu.

## Što provjeriti i javiti
- Otvara li se aplikacija i učitavaju li se cijene.
- 🎤 glasovni unos: pita li za mikrofon, razumije li stavke.
- Zaključavanje popisa, usporedba, „Sve u jednoj trgovini”, karta/lokacija.
- Ostaje li popis spremljen nakon zatvaranja aplikacije.
- Radi li bez interneta (zrakoplovni način) s već učitanim cijenama.
