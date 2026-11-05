# PLAN – Najjeftinija košarica

Owner's instructions of 5 Nov 2026: one part at a time – build, test, fix, then tick. Never skip a part.
A bug is fixed at its root cause everywhere and gets a test. Order of work: Part 1 → Part 4 → Part 2 → 3 → 5 → 6 → 7.

Legend: `[x]` done and tested · `[ ]` not done yet · `[~]` done with a limit that is written next to it.
Every ticked line says how it was checked. "Live" means checked on the published app address.

App: https://antiquecroatianoak-sudo.github.io/Najjeftinija-kosarica/

## Part 1 – Data
- [ ] Products and prices from all Croatian chains' official daily price lists
- [ ] Prices update automatically every day
- [ ] No duplicate products
- [ ] On problems: retry, skip bad prices, keep the last good data
- [ ] Bigger problems create an error report that can be pasted into Claude Code
- [ ] Data status screen shows when prices were last updated

## Part 4 – Location (fix right after Part 1)
- [ ] One location icon on the main screen
- [ ] One tap gets the user's location
- [ ] User picks a radius: 2, 5, 10 or 20 km
- [ ] Only stores inside the circle are used – on the map and in the results
- [ ] Goes straight back to the list; no extra steps; screen never gets stuck
- [ ] Location is optional (everything works without it)

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
