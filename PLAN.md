# PLAN – Najjeftinija košarica

Owner's instructions of 5 Nov 2026: one part at a time – build, test, fix, then tick. Never skip a part.
A bug is fixed at its root cause everywhere and gets a test. Order of work: Part 1 → Part 4 → Part 2 → 3 → 5 → 6 → 7.

Legend: `[x]` done and tested · `[ ]` not done yet · `[~]` done with a limit that is written next to it.
Every ticked line says how it was checked. "Live" means checked on the published app address.

App: https://antiquecroatianoak-sudo.github.io/Najjeftinija-kosarica/

Live (5 Nov 2026, 17:42 Zagreb): everything below is published – PR #22 (Parts 1 and 4) and PR #23 (Parts 2, 3, 5, 6, 7); publish run 42064404881 green, live data version c9348b8457.

## Part 1 – Data
- [x] Products and prices from all Croatian chains' official daily price lists – 26 chains, all status "ok" for 5 Nov 2026, 225,417 products, 1,520 stores (real published `meta.json`). Limit: Studenac publishes only 20 stores (checked on studenac.hr); store locations still filling (NTL 213/342, Stridon 1/41).
- [x] Prices update automatically every day – scheduled 08:17 and 16:47 Zagreb time on the main branch. Confirmed: first scheduled run of the new job fired by itself on 5 Nov 2026 at 16:45 UTC (GitHub starts schedules up to ~1 h late) and succeeded – run 42067651982.
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
- [x] Build the list by voice; typing also works – browser test speaks "kruh, mljeko i deset jaja" through a simulated recogniser → Kruh, Mlijeko 1 l, Jaja 10 kom, and shows "Razumio sam: …"; spelling variants (mljeko/mleko) and one wrong letter are understood; 15 s safety stop so the microphone can't stay stuck in "Slušam…"; typing tested with a 15-item sentence on real data. Not testable here: the real microphone on your phone.
- [x] Groups with subgroups; "kruh" searches all kinds of bread – 68 groups with subgroups; "kruh" = "Kruh · sve vrste"; product grouping fixed for all groups (first type-word decides, non-food never in food groups). Fixed today on real data: polystyrene craft eggs → not eggs; chicken bones → not chicken; kids' rice meal → baby food; coffee drinks / 3-in-1 / cappuccino mixes → drinks, not coffee.
- [x] Default amount when none is said (milk 1 l, potatoes 1 kg), shown and changeable – shown with "zadano", − and + change it (test). NEW: groups sold by weight now compare by kg/l around a typical pack (biscuits 200 g, jam 350 g, tea 40 g, sweets 100 g, ice cream 0,5 l, toilet paper 10 rolls) instead of "1 package", where the tiniest pack always won.
- [x] Quantity, brand and type always shown next to the price – every result line: pack size, brand, type (subgroup), number of packs, price per kg/l/kom; "količina nije objavljena" when the store did not publish it. Root fix: 7,929 products had sizes like "0,415 kom" (weight written as pieces) – now read correctly from the name or marked unknown. NEW: "neobično niska cijena – provjeri u trgovini" next to prices below 1/8 of the normal price per kg/l (e.g. chicken legs 0,29 €/kg).

## Part 3 – Results (after the list is locked)
- [x] Cheapest item of each group and which store has it – view A, checked on real data with a 15-item list (each line: product, brand, size, type, store, price, price per kg/l).
- [x] Cheapest single store for the whole list – view B (real data: Konzum 19,13 € for the 15 items; with location: real stores in the circle).
- [x] Best mix of two stores – view C (real data: Konzum + Trgovina Krk 15,64 €, 3,49 € less than all in Konzum); test checks the pair is never dearer than one store.
- [x] Tapping an item swaps it for the next cheapest in the same group – browser test: "Kruh bijeli 700 g" → "Kruh polubijeli 310 g", and "Vrati" undoes it.
- [x] User chooses stores; only those are searched – real data: only Konzum + Lidl ticked → A, B and C show only those two, and "2 od 26 lanaca".

## Part 5 – Extra screens
- [x] Savings counter (main feature) – always visible top right; "Kupio/la sam" adds the saving (real data: 0,00 € → 9,30 €); Više → Moja ušteda shows the history.
- [x] Weekly deals – real data: 150 deals in 0,1 s, biggest discount first, search and group filter.
- [~] Shared family list – works by sending a link (opens the same list on the other phone; tested). Limit: not live/real-time; that needs an online database (a cost/account decision for you).
- [x] "Report wrong price" button – ⓘ next to every product → "Prijavi pogrešnu cijenu" (opens a GitHub issue or copies the report); tested on real data.
- [x] In-store barcode scan to check the price – camera scan (where the phone's Chrome supports it) or typing the number; real data: 5449000000286 → Coca-Cola 2L with prices per chain; merged duplicates keep every barcode.
- [x] Share list and results via Viber, WhatsApp, etc. – "Pošalji" uses the phone's share menu, plus direct WhatsApp/Viber/SMS links (tested).

## Part 6 – Design and money
- [x] Modern, attractive, premium-looking design, easy for everyone – checked on screenshots at phone size (320–768 px, no sideways scrolling); big buttons, light and dark mode.
- [~] Free version with a few small ads – small marked ad places are in the app. Limit: no ad network is connected; that needs an account in your name (e.g. Google AdSense).
- [~] Premium about 1.99 EUR/month: no ads, extra features – described in Postavke ("uskoro · 1,99 €/mj"). Limit: payments are not connected; that needs a payment provider account in your name.
- [x] Stores can never pay to look cheaper – ranking uses only price; stated in the app next to the ad place and in Postavke; no code path changes order for ads or Premium.

## Part 7 – Final check
- [x] Every part tested together as a normal customer would use it (real data, phone size) – one session on the real published data (224k+ products, 1,520 stores): status → 15-item list → A/B/C → only Konzum+Lidl → savings → deals → barcode → report button → family list → location 5 km → results → map; no JavaScript errors. Automated: Python tests OK, Node 16/16, browser test 38 checks incl. voice, refused location and slow network.
- [x] PLAN.md updated and final report given

## Round 2 – whole-app review and ideas from the best apps (5 Nov 2026)
Researched: Basket, Trolley, Usporedi cijene (HR) – whole-basket comparison by store; Flipp, Marktguru – deals and followed products; Listonic, Bring! – suggestions while typing, frequent items, ticking items off in the shop.
- [x] Grouping checked for the cheapest product in every chain for 34 everyday items (26 chains each). Fixed by type: pet food, offal/bones/skin, coffee sweets and drinks, bread mixes, decorations (polystyrene eggs, "offert."), clotheslines, perfume ("Lagerfeld" ≠ lager), body scrub ("Rose"), fish guts, baby muesli, cooking wafers, pickled/fried onions, passata. 14,022 products moved to a better group. Tests: `test_razvrstavanje.py` (real names).
- [x] Start screen: 3 short steps for a new user; microphone and typing in one row once the list has items, so the list is visible at once; no repeated item names.
- [x] Suggestions while typing ("mli" → Mlijeko, Mliječna čokolada, Mlijeko bez laktoze); tap adds the item.
- [x] "Često kupuješ": quick-add from your own most-used items (before that: "Brzo dodaj" with common items).
- [x] Shopping mode: circle next to every item → "u košarici" (ticked items go to the bottom, "3 od 10 u košarici"), also on a locked list.
- [x] Favourites: "☆ Prati cijenu" on every product; Akcije shows "★ Tvoji favoriti na akciji" first; Više → Moji favoriti with today's cheapest price.
- [x] App version 1.3.0 shown at the bottom of Više; new version always downloads fresh files.

## Round 3 – is the deal real? (6 Nov 2026)
- [x] Daily update confirmed again: scheduled run 42187631312 (6 Nov, 08:25 UTC) loaded the prices of 6 Nov – 227,574 products, 28 chains; dm, KTC and Lorenco had not published yet, so yesterday's prices were used for them (as designed).
- [x] Lowest price in the last 30 days and anchor price (both required by NN 75/2025) are now imported per chain. Product details show "najniža u 30 d" and "sidrena" per chain; results and deals show "✓ najniža cijena u 30 dana" or "u 30 dana bilo i X €"; deals screen has "Samo prave akcije". Tests: Python, Node, browser (31 of 61 sample deals are genuine). Live (version 1.4.0, publish run 42194789739, data 6c116695c3): 19 of 28 chains publish the 30-day lowest price, incl. Konzum, Lidl, Kaufland, Spar, Interspar, Tommy, Studenac, Eurospin, KTC, Ribola, dm; not yet Plodine, NTL, Gavranović, Boso and a few small chains (for them no badge is shown).
- [x] Locked list (in the shop) is grouped by shop section in the usual walking order – Voće i povrće → Kruh i peciva → Mliječno i jaja → Meso, riba → Smrznuto → Namirnice → Kava, čaj i slatko → Pića → Dom i higijena (idea from Bring!). Browser test checks the order.
- [x] "Upute do trgovine": with location on, the chosen store (one store and both stores of the best pair) has a button that opens Google Maps directions to that exact shop (idea from Basket). Browser test checks the link.

## Round 4 – no wrong low prices, colourful start screen (6 Nov 2026)
- [x] Unusually low prices (almost always a mistake in the shop's price list) are no longer shown anywhere. Rule, measured on all 438,345 real prices: the same product sold by 3+ chains at under 1/4 of its usual price, or a price per kg/l under 1/16 of the usual for that kind of product (1/20 when only the broad group is known) → 204 prices left out (e.g. Vino Arabella 0,20 €, chicken legs 0,29 €/kg, sugar 4 kg for 0,02 €); with real data chicken now shows 1,86 €/kg. Softer rules would also have hidden real prices (body lotion 1,10 €, sunflower oil), so they were not used. These prices are left out: not in A, B, C, swaps, deals, favourites or product details (details say how many were left out). Tests: `logika.test.mjs` (both rules; A, B, C and deals).
- [x] Start screen with big coloured tiles. Empty list: Akcije tjedna, Skeniraj barkod, Favoriti, Obiteljski popis. List with items: „Pošalji popis obitelji” – WhatsApp (pick person or group in WhatsApp), Iz imenika (opens the phone book, you tap a person → WhatsApp or SMS straight to them), Viber, SMS i ostalo. Browser test checks the tiles, the WhatsApp link with the list and a simulated phone-book pick (091 234 5678 → WhatsApp +385 91 234 5678). Not testable here: the real phone book (works in Chrome on Android; elsewhere the app offers WhatsApp/Viber/SMS instead).
- [x] Milk → yogurt again (owner's report 6 Nov): cause was a list item saved on the phone by an older version as a plain text search ("mljeko" → found "Mljekara" yogurt); saved items were never re-checked. Now every saved or received item is re-recognised when the app starts (old "mljeko" → Mlijeko 1 l). English names of 40 common groceries are understood too ("milk" → Mlijeko, not Milka). Tests: Node (old saved item, English names) and browser (phone with an old saved list → milk, no yogurt).

## Round 5 – security and robustness review (6 Nov 2026)
- [x] Security: a family-list link could insert HTML into the receiver's list screen – fixed (text is always escaped); browser test proven to fail without the fix.
- [x] Security: the "@claude" GitHub task workflow can now be started only by the owner/collaborators (public users open issues through "Report wrong price").
- [x] Saved lists remember group names, not positions, so future group changes can never turn milk into another group.
- [x] Damaged or old saved data and absurd values from links (e.g. 10^12 packs) can no longer break the app.
- [x] A slow, older results calculation can no longer overwrite a newer screen; a double tap cannot count savings twice.
- [x] Faster start: data preparation 548 → 209 ms on real data.
- [x] Published: version 1.5.0 live (PR #27, publish run 42205274123 green, data 6c116695c3).

## Round 6 – only chains with 19+ stores (6 Nov 2026)
- [x] Chains with fewer than 19 stores are removed in the daily import (owner's decision; dm kept because it publishes one price list for all its 100+ shops). Removed today: Boso, Trgovina Krk, Roto, Dukat, Trgocentar, Vrutak, Bure, Žabac, Djelo Vodice, Jadranka, Lorenco (61 stores, ~39,400 products only they sell). Checked every day, so a chain that grows to 19+ stores comes back automatically. Tests: Python `MaliLanci`.
- [x] Published: run 42212785056 green, data 12174de0dc. The import log confirms 12 small chains left out (also Branka, which appeared today); 16 chains, 1,384 stores and 185,057 products remain.

## Round 7 – navigation and stores on the list (6 Nov 2026)
- [x] Phone Back button works like a real app: closes a panel → previous screen → list → only then leaves the app (before, it closed the whole app). Back buttons say where they go ("‹ Više") and return exactly where you came from.
- [x] Bottom bar: Popis · Usporedba · Akcije · Skeniraj · Više; the active tab is highlighted, also on sub-screens. Map: from the location button, Više and a start-screen tile.
- [x] On the list, every item shows its cheapest shop and price in a bigger, coloured line ("Mlijeko" → "● Kaufland · 0,44 €"); with location on, the real nearby store. Store names bigger in results A too.
- [x] Tests: browser checks for Back button, panel closing, back-button target, active tab, store line on every item. Version 1.6.0.
- [x] Published 1.6.0: PR #29, run 42223793731 green, data 1593f29b9e. Picture of all screens: `docs/pregled-1.6.0.png`.
- [x] Stridon removed (owner's decision 6 Nov): not imported at all, like Metro. Test `PreskoceniLanci`.

## Round 8 – premium look (owner's 4 proposals, 6 Nov 2026)
- [x] 1. Flat design with subtle layered shadows; prices prominent, store addresses in a thinner grey font.
- [x] 2. "Jedna trgovina": swipeable carousel – the focused store in front, others smaller and faded behind; its basket shows below.
- [x] 3. "Kupio/la sam": confetti, a tick that draws itself, savings counter counts up (calm version when the phone asks for less motion).
- [x] 4. Ads: elegant rounded banner with a fine border in the app's colours.
- Tests: browser checks for the carousel, celebration and ad banner. Picture: `docs/pregled-1.7.0.png`. Version 1.7.0.
- [x] One-hand use (owner's 3rd note): fixed action bar just above the bottom menu – list: "Pošalji" + "Zaključaj i usporedi"; results: "Pošalji" + "Kupio/la sam". "Pošalji" opens a bottom panel with WhatsApp / phone book / Viber / SMS tiles.
- [x] Less clutter: share tiles out of the middle of the list, shorter tips, roomier cards. Browser test checks the bar is visible in the bottom quarter of the screen.
