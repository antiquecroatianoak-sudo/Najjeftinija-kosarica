# 🛒 Najjeftinija košarica

A phone app (works in Chrome on Android, can be installed like a normal app) that compares grocery
prices in all Croatian supermarket chains and tells you where your shopping is cheapest.
The app itself is in Croatian.

**Address of the app (after it is published):**
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

### Step 1 – Put the new app on the main branch
The new app is on the branch `ccr-1c31c1df-63brmk`. It goes live when it is merged into the main
branch `claude/dreamy-hopper-f6e4u0`.

1. Open https://github.com/antiquecroatianoak-sudo/Najjeftinija-kosarica/pulls in Chrome.
2. Open the pull request for the new app (Claude can create it for you – just ask).
3. Wait for the green ✓ next to "Cijene i objava / provjere".
4. Tap **Merge pull request** → **Confirm merge**.

### Step 2 – Wait for the first publish (about 10–20 minutes)
1. Open the **Actions** tab of the repository.
2. Tap the newest run of **Cijene i objava**. When both steps (`provjere` and `objava`) have a green ✓,
   the app is live.
3. If you don't want to wait for tomorrow's automatic run: **Actions → Cijene i objava → Run workflow →
   Run workflow** (green button).

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
- Product groups are sorted by keywords. Some products may land in the wrong group or in none;
  these can still be found by typing their name. Report such cases and they can be fixed in `uvoz/grupe.json`.

---

## For developers

| Path | What it is |
|---|---|
| `app/` | The whole web app (no build step). `js/usporedba.js` = results A/B/C, `js/popis.js` = voice/typed list, `sw.js` = offline cache (`kosarica-` prefix only) |
| `uvoz/uvoz.py`, `uvoz/kolicina.py` | Daily import (Python 3.13, standard library only) |
| `uvoz/grupe.json` | Product groups, subgroups, spoken words, default amounts |
| `tests/` | `test_uvoz.py` (import), `logika.test.mjs` (app logic), `preglednik.cjs` (full app in a phone-size browser) |
| `.github/workflows/dnevno.yml` | Tests on every branch; daily import + publish on the main branch |

Run all checks locally:
```
python3 -m unittest discover -s tests -p "test_*.py"
node --test tests/logika.test.mjs
python3 tests/primjer.py /tmp/p && python3 uvoz/uvoz.py --arhiva /tmp/p/2026-11-05.zip /tmp/p/2026-11-04.zip --izlaz app/data/hr --bez-dopune
node tests/preglednik.cjs app
```
