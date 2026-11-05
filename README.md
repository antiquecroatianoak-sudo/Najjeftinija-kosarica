# 🛒 Najjeftinija košarica

A phone app (works in Chrome on Android, can be installed like a normal app) that compares grocery
prices in all Croatian supermarket chains and tells you where your shopping is cheapest.
The app itself is in Croatian.

**Address of the app:**
https://antiquecroatianoak-sudo.github.io/Najjeftinija-kosarica/

---

## What the app does (version 1)

| Feature | Where in the app |
|---|---|
| Speak your list in Croatian (or type it). "kruh" searches all kinds of bread. No amount said → normal amount (milk 1 l, potatoes 1 kg), which you can change with − and + | **Popis** |
| Lock the list, then see: **A** cheapest item everywhere, **B** cheapest single store, **C** best pair of two stores | **Rezultati** |
| Every result shows price, pack size, number of packs, price per kg/l, brand and type | **Rezultati** |
| Tap a product → next cheapest of the same kind (with "Vrati" to undo) | **Rezultati** |
| Choose which chains to search | **Više → Moje trgovine** |
| Map of stores, your location, circle of 2 / 5 / 10 / 20 km (then prices of the real stores in the circle are used) | **Karta** |
| Savings counter (top right, always visible) | header, **Više → Moja ušteda** |
| Weekly deals | **Akcije** |
| Family list (send a link; it opens the list on their phone) | **Više → Obiteljski popis** |
| Send list and result via WhatsApp, Viber, SMS | **Pošalji** button |
| "Report wrong price" | ⓘ next to each product |
| Data status per chain (date, fresh / older / missing) | **Više → Status podataka** |
| Barcode scan in the store | **Više → Skeniraj barkod** |
| Error report you can copy and paste into Claude Code | **Više → Prijavi grešku** |
| Country choice (only Croatia active now) | **Više → Postavke** |

Honesty rule: stores never pay for position. Ranking depends only on price.

## How the prices get in (automatic, every day)

1. Every day at about 8:17 and again in the afternoon, GitHub runs `uvoz/uvoz.py` for free.
2. It downloads the official daily price lists of all chains (the ones the law NN 75/2025 requires),
   collected by the free public project cijene.dev.
3. It removes bad prices (0,00 €, prices 4× too high or low), merges the same product from different
   chains (barcode, otherwise brand + name + size) and sorts products into groups (Kruh, Mlijeko…).
4. If a chain is missing today, it uses that chain's price list from up to 3 days ago and marks it
   "stariji cjenik". If today's data is much worse than yesterday's, it **does not publish** – the app
   keeps showing the last good prices.
5. It runs all tests, then publishes the app with the new prices.
6. If something fails, GitHub opens an **issue** called "Dnevno ažuriranje cijena nije uspjelo" with
   a ready error report. You get an email. Copy the report into Claude Code and ask it to fix it.

**Cost: 0 € per month** (GitHub Pages and GitHub Actions are free for a public repository).

---

## What you need to do (step by step, from your Android phone)

### Step 1 – Nothing to merge: the app is live
The new app was merged on 5 November 2026 (pull request #16) and published the same day with real prices.
Every day GitHub updates the prices by itself. To update them right now:
**Actions → Cijene i objava → Run workflow → Run workflow** (green button), then wait about 10 minutes.

### Step 2 – Check that the prices are fresh
In the app: **Više → Status podataka** shows the date of the prices for every chain.

### Step 3 – Open and install on your phone
1. Open https://antiquecroatianoak-sudo.github.io/Najjeftinija-kosarica/ in **Chrome**.
2. If you see the old app, close the tab and open it again (the new version replaces the old one).
3. Chrome menu **⋮** → **Add to Home screen** / **Install app**.
4. The first time you tap the microphone, Chrome asks for permission → **Allow**.

### Step 4 – Try it
1. Tap the microphone and say: *„kruh, dvije litre mlijeka, jaja i pola kile krumpira”*.
2. Tap **Zaključaj popis i usporedi cijene**.
3. Switch between **A**, **B** and **C**. Tap a product to see the next cheapest.
4. Open **Karta**, tap **5 km** → allow location → back to **Rezultati**: now you see real stores near you.
5. Tap **Kupio/la sam – zabilježi uštedu** and watch the counter at the top.

### If something is wrong
- In the app: **Više → Prijavi grešku → Kopiraj izvješće**, paste it into Claude Code.
- For a wrong price: tap ⓘ next to the product → **Prijavi pogrešnu cijenu**.

---

## Not done yet (honest list)

- **Ads and Premium (1,99 €/month)** – the places for them are ready in the app, but no ad network
  and no payment system are connected. Both need accounts in your name (for example Google AdSense
  and a payment provider). Claude can guide you when you want to start.
- **Family list in real time** (everyone sees changes instantly) – needs a small online database.
  Now the family list works by sending a link.
- **Google Play store** – the app is a web app you install from Chrome. A Play Store version is possible later.
- **Other countries** – the settings already have the country choice; only Croatia has data.
- **Studenac** publishes official prices for only about 20 of its stores (checked 5 Nov 2026 on
  studenac.hr itself). The app shows those stores; prices of other Studenac stores are not public.
- **Store locations**: most come from the cijene-api project; the rest are looked up once on OpenStreetMap
  (© OpenStreetMap contributors): first the exact address, then a shop of the same chain **on the same
  street**, then the street itself (only short local streets). At most 400 lookups per run, so the first days fill the
  map step by step. A store whose address cannot be found exactly stays off the map (better no pin than
  a wrong pin). **Više → Status podataka** shows "N na karti" for every chain.
- Product groups are sorted by keywords. Some products may land in the wrong group or in none;
  these can still be found by typing their name. Report such cases and they can be fixed in `uvoz/grupe.json`.

---

## For developers

| Path | What it is |
|---|---|
| `app/` | The whole web app (no build step). `js/usporedba.js` = results A/B/C, `js/popis.js` = voice/typed list, `sw.js` = offline cache (`kosarica-` prefix only) |
| `uvoz/uvoz.py`, `uvoz/kolicina.py` | Daily import (Python 3.13, standard library only) |
| `uvoz/lokacije.py` | Store coordinates from OpenStreetMap Nominatim (1 request/s, saved in `data/hr/lokacije.json`) |
| `uvoz/grupe.json` | Product groups, subgroups, spoken words, default amounts |
| `tests/` | `test_uvoz.py` (import), `test_lokacije.py` (store locations), `logika.test.mjs` (app logic), `preglednik.cjs` (full app in a phone-size browser) |
| `.github/workflows/dnevno.yml` | Tests on every branch; daily import + publish on the main branch |

Run all checks locally:
```
python3 -m unittest discover -s tests -p "test_*.py"
node --test tests/logika.test.mjs
python3 tests/primjer.py /tmp/p && python3 uvoz/uvoz.py --arhiva /tmp/p/2026-11-05.zip /tmp/p/2026-11-04.zip --izlaz app/data/hr --bez-dopune
node tests/preglednik.cjs app
```
