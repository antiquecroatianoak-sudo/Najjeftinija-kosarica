# Pozicioniranje: slabosti kategorije -> prednosti License Pulsea

**Ograničenje ove analize:** u ovoj radnoj sesiji nije bilo pristupa webu za provjeru pojedinih proizvoda
(cijene, značajke, verzije). Zato ovdje nema tvrdnji o određenim konkurentima. Analiza opisuje tipične obrasce
u kategoriji SaaS management / license tracking alata, kakve korisnici često navode. Prije korištenja u prodaji
ili marketingu provjerite ih na aktualnim stranicama i recenzijama konkretnih proizvoda.

| Česta slabost u kategoriji | Posljedica za mali tim | Kako je License Pulse riješen |
|---|---|---|
| Pretrpano sučelje, mnogo modula i izbornika | Nitko ga ne otvara nakon uvođenja | Četiri prikaza, prvi zaslon odgovara na pitanje „koliko gubimo i što napraviti sada”; prečaci; visok kontrast |
| Ušteda skrivena u izvješćima | Teško opravdati alat | **Trenutačni gubitak** i **ROI kalkulator** na vrhu nadzorne ploče, projekcija prema stvarnim datumima naplate |
| Cijena i uvođenje za enterprise (prodajni pozivi, integracije, tjedni postavljanja) | Nedostupno timu od 5–50 ljudi | Jedan kontejner, jedna SQLite datoteka, rad za par minuta; uvoz postojeće tablice (CSV/Excel) s automatskim mapiranjem |
| Ovisnost o mnogo integracija prije ikakve vrijednosti | Prazna ploča prvih tjedana | Vrijednost odmah iz ručnog unosa ili uvoza; integracije (SSO korištenje, izvodi) su dodatak |
| Teška arhitektura, spor rad | Čekanje, frustracija | Standardna biblioteka, bez frameworka i bez AI modela; lokalna predmemorija, optimistična ažuriranja, rad bez mreže |
| „Crna kutija” automatike | Nepovjerenje u brojke | Deterministička pravila s objašnjenjem (zašto je licenca neaktivna, zašto je transakcija sparena); iznos bez tečaja se ne nagađa |
| Podaci u tuđem oblaku, nejasna lokacija | Pravna i sigurnosna pitanja | Self-hosted; lokacija podataka = vaš poslužitelj; tokenizacija IBAN-a i e-mailova; bez telemetrije |
| Valute i PDV kao naknadna misao | Krivi zbrojevi u europskim tvrtkama | ECB referentna valuta po organizaciji, prepoznavanje PDV-a 25 %/13 % pri sparivanju, hrvatski formati brojeva i datuma |

## Ključne poruke

1. **Vidite gubitak u prvoj sekundi.** Iznos koji tim plaća za nekorištene licence je najveći broj na zaslonu.
2. **Ušteda s datumom.** „Otkažite X do 20. 11. i izbjegnite 41,97 €” umjesto općenitih preporuka.
3. **Bez ručnog održavanja.** Korištenje iz SSO-a mijenja status automatski; bankovni izvod sam pronalazi plaćanja i nepraćene pretplate.
4. **Lagano i vaše.** Jedan kontejner, vaši podaci, radi i na skromnom poslužitelju.

## Što namjerno nije u opsegu

- Automatsko pregovaranje s dobavljačima: alat priprema listu i argumente (obnova unutar 90 dana, rast cijene,
  neaktivnost, godišnja obveza), a pregovore vodi čovjek.
- Otkrivanje svih aplikacija preko pristupa e-pošti/pregledniku zaposlenika – invazivno za male timove; zamijenjeno izvodima i SSO-om.
