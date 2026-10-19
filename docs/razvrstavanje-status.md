# Razvrstavanje — provjerena radna verzija, bez objave

Polazna i povratna verzija: 5014e1656381434d40e68304fbd188696849fb99, grana backup/prije-razvrstavanja-2026-10-19.
Radna grana: codex/razvrstavanje-proizvoda-2026-10-19. Produkcija nije promijenjena.

Zajednički mehanizam primijenjen je na svih 237.881 artikl aktualnog cjenika. Ima 223 osnovne definicije i 400 nepraznih skupina uključujući izvedene kombinacije okusa. Automatski prepoznaje vrstu za 77.743 retka; 160.138 ostaje nerazvrstano. Te brojke nisu ručna potvrda kvalitete. Ne tvrditi da su svi artikli ispravno razvrstani.

Prolaze fixture testovi različitih proizvođača i pakiranja kruha i soka; mješavina naranče i jabuke nije sok samo od naranče; sirup, nektar i gazirano imaju vlastitu vrstu; vrećice, košare i kalupi nisu kruh; krušne mrvice nisu kruh; boje/ukrasi za jaja nisu jaja; BR. nije Brie; mlijeko za tijelo i biljni napitci odvojeni su od običnog mlijeka; tehničko i mirisno ulje odvojeni su od jestivog; krmno brašno odvojeno od običnog. Ručno nije pregledan cijeli cjenik.

Neutvrđene proizvode treba sačuvati kao moguća podudaranja, jasno označena i bez proglašenja najpovoljnijeg. Testovi i audit: tests/skupine.cjs i docs/razvrstavanje-pregled.json.

## Integracija u radnoj grani — završena, još bez objave
- scripts/razvrstaj.cjs nakon redovitog uvoza cijena priprema site/data/skupine.json. Postojeći uvoz cijena nije promijenjen.
- Dnevni workflow u radnoj grani ima Node 22, fixture testove i pripremu indeksa prije objave. Pri pokretanju s radne grane objava je preskočena jer postojeći workflow objavljuje samo zadanu granu. Automatizam još NIJE u produkciji.
- Indeks za aktualni cjenik ima 543.056 bajtova. Broj proizvoda i otisak naziva/količina/marke sprječavaju uporabu indeksa drugog cjenika. Pri nedostajućem/zastarjelom indeksu aplikacija koristi postojeće pretraživanje i zadržava cijene.
- Frontend koristi zajednička pravila i unaprijed pripremljeni indeks; moguća podudaranja jasno označava kao vrstu za provjeru, drži ih na kraju i ne proglašava najpovoljnijim. Ukupan iznos upozorava kad odabrana ponuda zahtijeva provjeru vrste.
- Prošli su Node fixture testovi, provjera punog cjenika, ispravnost ponovnog učitavanja indeksa, odbacivanje zastarjelog indeksa i browser provjere na 320/390/768/1280px. Glasovni tok testiran simuliranim prepoznavanjem, ne stvarnim korisnikovim mikrofonom.
- U browseru kruh: 2.903 prepoznata člana +474 moguća; sok od naranče:122 prepoznata +12 mogućih. Sirup/nektar/gazirano i sokovi s drugim voćem nisu u prepoznatoj skupini samo naranče. To nije ručna potvrda svakog retka.

Sljedeće: pregled radne verzije i odluka o objavi; proširiti pravila i provjeriti nejasne nazive. Opći mehanizam radi nad cijelim cjenikom, ali nije svaki artikl razvrstan niti je time zajamčena točnost svih naziva. Poznata pogrešna količina kruha 310g ->31kg u cjeniku nije riješena ovim razvrstavanjem.

Spremati nakon cjeline ili otprilike svakih pet minuta aktivnog rada; korisnik ne želi stalna pitanja i potvrde.
