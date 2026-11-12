# License Pulse – zapis stanja

## 12. 11. 2026. 20:37 (Europe/Zagreb)

- **Izdvajanje:** nalog vlasnika (12. 11. 2026.): projekt premjestiti u zaseban repozitorij i u CI uključiti sve dokumentirane testove.
  Izdvojeno iz `antiquecroatianoak-sudo/Najjeftinija-kosarica`, grana `claude/saas-license-tracking-app-zbw0dm`, mapa `licence/`
  (`git subtree split`, povijest sačuvana; izvorni zadnji commit `f0b95ca`).
- **CI:** `.github/workflows/ci.yml` – `unit (3.11)`, `unit (3.13)`, `e2e`, `docker` na svakom pushu i PR-u.
  Obaveznost (branch protection) postavlja vlasnik u postavkama repozitorija – opisano u README.
- **Stanje funkcionalnosti i ograničenja:** README.md i docs/. Neprovjereno: živi ECB dohvat, isporuka webhooka na javni URL,
  stvarni izvodi hrvatskih banaka, živi PSD2 konektor (nije implementiran).
- **Pravilo:** prije spajanja moraju proći sve četiri CI provjere; lokalno iste naredbe iz README.md.
