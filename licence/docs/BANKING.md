# Bankovni modul

Cilj: plaćanja pretplata s bankovnog računa automatski povezati s licencama – bez ručnog unosa –
i otkriti pretplate koje nitko nije upisao.

## Faze

```
[izvor]  izvod camt.053 / CSV  ──┐
         živi konektor (PSD2) ───┤   1. autentifikacija (samo konektor)
                                 ▼
                     2. sinkronizacija: parsiranje -> RawTransaction
                                 ▼
                     tokenizacija IBAN-a, maskiranje kartica, deduplikacija (otisak)
                                 ▼
                     3. sparivanje s licencama (bodovanje, bez ML-a)
                                 ▼
             matched / suggested / unmatched  -> ručna potvrda u sučelju
                                 ▼
             uvidi: nepraćene ponavljajuće pretplate, razlike u cijeni, webhook bank.matched
```

### 1. Autentifikacija

**Uvoz izvoda (implementirano):** nema vjerodajnica banke; administrator preuzme izvod iz internetskog bankarstva
(ISO 20022 camt.053 XML ili CSV) i uveze ga. To je najsigurniji put: aplikacija nikad nema pristup računu.

**Živi konektor (protokol definiran, nije implementiran):** PSD2 Account Information Service zahtijeva licenciranog
AISP-a (vlastitu licencu ili ugovor s agregatorom otvorenog bankarstva) i privolu korisnika. Protokol (`banking/connector.py`):

1. `authorize_url` – OAuth2 authorization code s **PKCE**; `state` vezan uz organizaciju i jednokratan; samo read-only opseg.
2. `exchange_code` – zamjena koda za privolu; refresh token / consent id čuvati **šifrirano** (KMS ili tajne platforme), nikad u zapisima;
   PSD2 privola traje najviše 180 dana – spremiti datum isteka.
3. `fetch(consent, since, cursor)` – samo knjižene transakcije od zadnjeg kursora (inkrementalno), mapirane u `RawTransaction`.
4. Obnova – obavijest administratoru prije isteka privole.

Dok konektor nije konfiguriran, `GET /api/bank/connect` vraća 501 s uputom za uvoz izvoda.

### 2. Sinkronizacija i čistoća podataka

- camt.053: `Stmt/Acct/Id/IBAN`, `Ntry/Amt@Ccy`, `CdtDbtInd` (DBIT = isplata, negativno), `BookgDt`, primatelj
  (`Cdtr/Nm` za isplate), opis (`RmtInf/Ustrd`, `AddtlNtryInf`), referenca banke (`AcctSvcrRef`). Imenski prostori se zanemaruju (različite verzije).
- CSV: stupci se prepoznaju po nazivu (hrvatski i engleski: datum, iznos ili isplata/uplata, valuta, primatelj, opis, referenca); cp1250 i UTF-8; zbirni retci se preskaču.
- **Deduplikacija:** otisak = SHA-256 (token računa + referenca banke, ili datum|iznos|valuta|primatelj|opis); ponovni uvoz istog izvoda ne stvara duplikate.
- **Zaštita podataka:** IBAN -> HMAC token + zadnje 4 znamenke; 12–19 znamenki i IBAN-i u tekstu maskirani (`•••• 1234`) prije spremanja.
- Ograničenja: 10 MB po izvodu; XML bez DTD/ENTITY.

### 3. Sparivanje (deterministički, objašnjivo)

Za svaku isplatu i svaku licencu koja se plaća:

| Signal | Bodovi |
|---|---|
| Iznos točan (±1 %) | 0,45 |
| Iznos + PDV 25 % ili 13 % | 0,30 |
| Iznos ±10 % (promjena cijene, tečaj) | 0,20 |
| Riječi naziva licence / ključa korištenja u primatelju ili opisu | 0,25–0,35 |
| Datum ±5 dana od planirane naplate (±10: 0,10) | 0,20 |

Različite valute uspoređuju se preko tečajne liste. **Automatski spareno** kad je najbolji rezultat ≥ 0,70 i barem 0,15 ispred
drugog kandidata; **prijedlog** od 0,40; ostalo nespareno. Svaka odluka ima objašnjenje (npr. „iznos, naziv, datum naplate”)
i može se ručno potvrditi, promijeniti, zanemariti ili vratiti (bilježi se u reviziji).

### Uvidi

- **Moguće nepraćene pretplate:** nesparene isplate istom primatelju u ≥ 2 različita mjeseca, iznosi unutar 15 % – jedan klik ih dodaje kao licencu.
- **Plaćeno drukčije od evidencije:** sparena plaćanja koja odstupaju > 2 % od upisanog troška (osim PDV-a 25 %) – kandidat za ažuriranje ili pregovore.
- Webhookovi `bank.matched` i `bank.unmatched_recurring`.
