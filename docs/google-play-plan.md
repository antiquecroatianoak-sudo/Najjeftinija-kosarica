# Plan: Najjeftinija košarica, a native Android app for Google Play

Written: 5.11.2026. (Europe/Zagreb). Source of requirements: the owner's document "Najjeftinija košarica – upute za Claude Code" (sections 1–14).
Status: **plan**. What is built is recorded in `PROJECT_STATE.md`.

Correction to the first plan (5.11.2026. 10:08): it proposed only a wrapper around the web app (TWA). The owner's document asks for a **native Android app**, so the TWA approach is replaced. The TWA test build was a misunderstanding.

## The plan in simple words
1. **Every day, a "robot" in the cloud** downloads the official price lists of all chains, cleans them, sorts products into groups and makes one small file for the phone.
   - For now this robot is GitHub Actions: free, and it already runs daily for the current web app.
2. **The phone app** (Kotlin + Jetpack Compose, Material 3) downloads only that small file.
   - It works offline with the last prices and shows their date.
   - It does all calculations on the phone (cheapest overall, cheapest in one shop, radius). Your location never leaves the phone.
3. **A small server (about €4–5/month)** is needed only later, for premium features: login, shared family list, price alerts, wrong-price reports and the admin screen. Until then the cost is €0.
4. **Multi-country ready:** the data file and the app carry country, currency and language fields. Launch is Croatia only.

## What you must do or pay for

| What | Cost | When |
|---|---|---|
| Google Play developer account | 25 USD, once (card, ID check) | Before the closed test (step 4) |
| Server for premium features (e.g. Hetzner CX22 or similar) | ≈ €4–5/month | Step 3, when premium and the admin screen are built |
| Domain (privacy policy, share links that open the app) | optional, ≈ €10–15/year | Recommended before step 4 |
| AdMob account (banner ads) | free | Step 3 |
| Google Play payments profile (premium subscription) | free; Google keeps 15% of subscriptions | Step 3 |
| 12+ testers for 14 days (Google's current rule; plan for about 20) | free | Step 4 |
| Tax/business registration for ad and subscription income | ask an accountant (e.g. paušalni obrt) | Before earning money |

Notes:
- With a personal Play account and in-app purchases, Google shows the developer's address on the store page. An organization account avoids the 14-day test rule, but it needs a D-U-N-S number.
- Name check: no Google Play app called "Najjeftinija košarica" was found. An iOS app is called "Košarica", so the full name is used everywhere and not the short "Košarica". Re-check in Play Console when creating the app.

## Steps (from the owner's document)
1. **Plan and costs**: this file.
2. **First working version** with a few big chains (Konzum, Lidl, Kaufland, Spar, Plodine): list by voice or typing, groups and amounts, cheapest overall, cheapest in one chain, chain choice, swap to next cheapest, share, offline. Test and install on your phone.
   - Done when it runs on your phone and all tests pass.
3. **All chains and features**:
   - per-store prices and radius map (OpenStreetMap)
   - opening hours
   - sale end dates and card prices
   - barcode scan, deals of the week, data status
   - savings counter
   - premium (two-shop mix, family list, alerts, history), ads with GDPR consent
   - admin screen, wrong-price reports, privacy policy and terms
   - widget and design polish
4. **Closed test** on Google Play with about 20 people, then fix problems.
5. **Publish** on Google Play.
