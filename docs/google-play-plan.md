# Plan: Najjeftinija košarica on Google Play

Written: 5.11.2026. 10:08 CET (Europe/Zagreb). Status: **plan only**. Nothing in this file is built, tested or published yet.

## Where we start (checked in the repo)
- The app already exists as a web app (PWA) in `site/`, published with GitHub Pages: https://antiquecroatianoak-sudo.github.io/Najjeftinija-kosarica/
- Prices update every day for free through GitHub Actions (`.github/workflows/dnevno-azuriranje.yml`).
- The price data already covers the big chains (Konzum, Lidl, Plodine, Kaufland, NTL, Eurospin, SPAR/INTERSPAR) and smaller ones listed in `docs/redoslijed-lanaca.md`.
- Not confirmed on 5.11.2026: the live Pages version and today's price data. This session's network blocks github.io.

So steps 2 and 3 of the original list mostly exist already. The new work is turning the web app into an Android app for Google Play.

## Approach
Use a **Trusted Web Activity (TWA)**: a small Android app that opens our existing web app full screen, with no browser bar. We build it with Google's free tool Bubblewrap.
- Pros: one codebase. Price updates keep working without new app releases. No server needed.
- Cons: the phone needs Chrome (or another browser that supports TWA). It is not a "real" native app.
- We would only switch to a native app if Google rejects the app as "just a website". That is a risk to watch, not something we expect.

## What you must do or pay for

| Item | Cost | Who | When |
|---|---|---|---|
| Google Play developer account (personal) | **25 USD, once** | You (card, ID verification, phone number) | Before step 4 |
| Server | **0 €**: GitHub Pages + GitHub Actions are enough | — | — |
| Own domain (e.g. kosarica.hr) | Optional, ~10–20 €/year | You | Only if you want it |
| Signing key for the app | 0 € | We make it, **you keep a backup** (if you lose it, you can't update the app) | Step 2 |
| Privacy policy page | 0 € (hosted on Pages) | We write it, you approve it | Before step 4 |
| 12+ testers for 14 days in a row | 0 € | You invite people (Gmail addresses) | Step 4 |
| Store texts, screenshots, icon, feature graphic | 0 € | We prepare them, you approve | Step 5 |
| Android phone with Chrome | — | You | Step 2 |

Note: Google now asks for **at least 12** testers, not 20. Check this in Play Console before the test, because Google changes these rules. About 20 people is still a good idea, because some people drop out.

## Steps

1. **Plan (this file).** Done when you agree with the approach and the costs.
2. **First Android version (TWA).**
   - Pick the app ID (proposal: `hr.najjeftinijakosarica.app`, which can't be changed later).
   - Add `.well-known/assetlinks.json` so Android trusts our site. This needs a check: GitHub Pages on a project URL (`…github.io/Najjeftinija-kosarica/`) can't serve the root `/.well-known/` file. Options are a user/organisation Pages site, a custom domain, or accepting a browser bar in the app.
   - Build the APK/AAB with Bubblewrap, targeting API level 36 (required for new apps from 31.8.2026).
   - You install the APK on your phone and test it (voice, list, comparison, offline).
   - Done when the app runs on your phone and all existing tests (`tests/`) pass.
3. **All chains and features.** Check which chains in the daily import are missing or weak. Finish the open fixes (e.g. draft PR #7: wrong quantities such as 310 g shown as 31 kg). Done when the coverage report and tests are green on the production branch.
4. **Closed test on Google Play.** Create the account, upload the AAB to the closed test track and invite the testers. Run it 14+ days, then collect and fix problems. Done when Google accepts the production access request.
5. **Publish.** Store listing, Data safety form (the app collects no personal data, location stays on the phone; to be confirmed against the code), content rating, then release. Done when the app is live on Google Play and installs from the store.

## Open decisions for you
- App ID and app name on the store.
- Domain: free `github.io` or your own domain. This affects the assetlinks problem in step 2.
- Who the 12–20 testers will be.
