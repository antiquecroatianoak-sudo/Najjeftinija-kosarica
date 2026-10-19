# Razvrstavanje — rad u tijeku

Polazna objavljena verzija: 5014e1656381434d40e68304fbd188696849fb99.
Sigurnosna grana: backup/prije-razvrstavanja-2026-10-19.
Radna grana: codex/razvrstavanje-proizvoda-2026-10-19.

Prvi eksperimentalni mehanizam spremljen je u site/skupine.js. Još NIJE spojen s aplikacijom i NIJE objavljen. Svi postojeći dohvat i produkcijsko ponašanje ostaju na polaznoj verziji.

Pravila: osnovna vrsta prema glavnom nazivu; marka i pakiranje ne mijenjaju skupinu; okus sužava vrstu; mješavina voća nije isto što i jedan okus; neprepoznati nazivi ostaju pretraživi.

Početna automatizirana obrada cjenika od 19.10.2026. (237.881 red) traje oko sekunde u lokalnom Nodeu. To je vrijeme izvršavanja pravila, a ne vrijeme razvoja ili dokaz kvalitete. Trenutno ima 216 eksperimentalnih definicija i izvedene podskupine. Broj točno razvrstanih proizvoda nije potvrđen.

Poznati problemi prve radne verzije koje treba riješiti PRIJE integracije: kratice BR. pogrešno prepoznaje kao brie; ukrasna jaja i neki kozmetički proizvodi ulaze u hranu; neki nazivi bez prepoznate glavne imenice se pogrešno klasificiraju prema sastojku. Potrebni su testovi i konzervativno označavanje nejasnih artikala. Ne tvrditi da je razvrstavanje završeno.

Dalje: ispraviti lematizaciju kratkih naziva i granice sastojaka, dodati negativne primjere, pregledati stvarne pogotke kruha/soka i ostalih skupina; tek zatim povezati modul s pretraživanjem u radnoj grani i pripremiti pregled prije objave.

Korisnik traži spremanje napretka nakon dovršene cjeline ili približno svakih pet minuta aktivnog rada. To nije zakazani proces i ne uklanja limite računa.
