# PLAN – Najjeftinija košarica

Owner's instructions of 5 Nov 2026: one part at a time – build, test, fix, then tick. Never skip a part.
A bug is fixed at its root cause everywhere and gets a test. Order of work: Part 1 → Part 4 → Part 2 → 3 → 5 → 6 → 7.

Legend: `[x]` done and tested · `[ ]` not done yet · `[~]` done with a limit that is written next to it.
Every ticked line says how it was checked. "Live" means checked on the published app address.

App: https://antiquecroatianoak-sudo.github.io/Najjeftinija-kosarica/

## Part 1 – Data
- [x] Products and prices from all Croatian chains' official daily price lists – 26 chains, all status "ok" for 5 Nov 2026, 225,417 products, 1,520 stores (real published `meta.json`). Limit: Studenac publishes only 20 stores (checked on studenac.hr); store locations still filling (NTL 213/342, Stridon 1/41).
- [~] Prices update automatically every day – scheduled 08:17 and 16:47 Zagreb time on the main branch; every publish today was green. Waiting to see the first scheduled run fire (15:47 UTC, 5 Nov).
- [x] No duplicate products – no barcode twice; NEW: same brand + same name + same pack size under different barcodes is merged into one product (about 1,464 such duplicates in real data, e.g. "Šećer kristal Agragold 1 kg" ×2). Size in a name is ignored only when it IS the pack size (kettle 1,7 l ≠ 1,8 l; milk 2,8 % ≠ 3,5 %). Scanner still finds every barcode. Tests: `test_nema_duplikata`, `test_naziv_bez_kolicine`.
- [x] On problems: retry, skip bad prices, keep the last good data – download retries; 0,00 / absurd / 4× off prices skipped; missing chain taken from up to 3 days older list; publish stopped if new data much weaker. Tests: `test_lose_cijene`, `test_stari_podaci_za_lanac_koji_nedostaje`, `test_zastita_objave`.
- [x] Bigger problems create an error report that can be pasted into Claude Code – `izvjesce-greske.md` written by the import (test `test_zastita_objave` checks it); a failed daily run opens a GitHub issue "Dnevno ažuriranje cijena nije uspjelo" with the report; in the app: Više → Prijavi grešku.
- [x] Data status screen shows when prices were last updated – checked with the real data in a phone-size browser (`tests/kupac.cjs status`): date 5.11.2026 and every chain shown.

## Part 4 – Location (fix right after Part 1)
Root causes found: (1) no location control on the main screen, only a separate map tab; (2) store prices could wait minutes on a weak connection (3 tries × 20 s per store); (3) the browser tests never had store coordinates (`--bez-dopune` silently dropped the coordinates file), so the location path was never really tested – fixed in the importer, tests now require stores inside the circle.
- [x] One location icon on the main screen – big button at the top of the list screen: "Trgovine u blizini · Cijela Hrvatska" or "U krugu 5 km · 77 trgovina". The same button is the location chip on the results screen.
- [x] One tap gets the user's location – the tap asks the phone for the position at once and opens the radius panel; own 20 s safety timer (the screen can never wait forever); clear message if location is refused or off, with "Pokušaj ponovno".
- [x] User picks a radius: 2, 5, 10 or 20 km – each button shows the number of stores inside (real data, central Zagreb: 19 / 77 / 146 / 199).
- [x] Only stores inside the circle are used – on the map and in the results – same circle and same store count on the list button, the map and the results (test checks the numbers match). Limit: the 60 nearest stores are compared when more are inside (e.g. 60 of 77).
- [x] Goes straight back to the list; no extra steps; screen never gets stuck – picking a radius closes the panel and shows the list (0.8 s on real data); store prices load in the background, so results are ready at once. Slow network: hard 15 s limit; if no store loads in time, chain prices are shown with an explanation and "Pokušaj ponovno" (test with 60 s delayed store files: result after 15.4 s).
- [x] Location is optional (everything works without it) – "Bez lokacije (cijela Hrvatska)" in the panel; refused permission tested: clear message, app keeps working.

## Part 2 – Shopping list
- [ ] Build the list by voice; typing also works
- [ ] Groups with subgroups; "kruh" searches all kinds of bread
- [ ] Default amount when none is said (milk 1 l, potatoes 1 kg), shown and changeable
- [ ] Quantity, brand and type always shown next to the price

## Part 3 – Results (after the list is locked)
- [ ] Cheapest item of each group and which store has it
- [ ] Cheapest single store for the whole list
- [ ] Best mix of two stores
- [ ] Tapping an item swaps it for the next cheapest in the same group
- [ ] User chooses stores; only those are searched

## Part 5 – Extra screens
- [ ] Savings counter (main feature)
- [ ] Weekly deals
- [ ] Shared family list
- [ ] "Report wrong price" button
- [ ] In-store barcode scan to check the price
- [ ] Share list and results via Viber, WhatsApp, etc.

## Part 6 – Design and money
- [ ] Modern, attractive, premium-looking design, easy for everyone
- [ ] Free version with a few small ads
- [ ] Premium about 1.99 EUR/month: no ads, extra features
- [ ] Stores can never pay to look cheaper

## Part 7 – Final check
- [ ] Every part tested together as a normal customer would use it (real data, phone size)
- [ ] PLAN.md updated and final report given
