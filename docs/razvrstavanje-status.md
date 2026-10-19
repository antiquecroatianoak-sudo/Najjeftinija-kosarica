# Razvrstavanje — provjerena radna verzija, bez objave

Polazna i povratna verzija: 5014e1656381434d40e68304fbd188696849fb99, grana backup/prije-razvrstavanja-2026-10-19.
Radna grana: codex/razvrstavanje-proizvoda-2026-10-19. Produkcija nije promijenjena.

Zajednički mehanizam primijenjen je na svih 237.881 artikl aktualnog cjenika. Ima 223 osnovne definicije i 400 nepraznih skupina uključujući izvedene kombinacije okusa. Automatski prepoznaje vrstu za 77.743 retka; 160.138 ostaje nerazvrstano. Te brojke nisu ručna potvrda kvalitete. Ne tvrditi da su svi artikli ispravno razvrstani.

Prolaze fixture testovi različitih proizvođača i pakiranja kruha i soka; mješavina naranče i jabuke nije sok samo od naranče; sirup, nektar i gazirano imaju vlastitu vrstu; vrećice, košare i kalupi nisu kruh; krušne mrvice nisu kruh; boje/ukrasi za jaja nisu jaja; BR. nije Brie; mlijeko za tijelo i biljni napitci odvojeni su od običnog mlijeka; tehničko i mirisno ulje odvojeni su od jestivog; krmno brašno odvojeno od običnog. Ručno nije pregledan cijeli cjenik.

Neutvrđene proizvode treba sačuvati kao moguća podudaranja, jasno označena i bez proglašenja najpovoljnijeg. Testovi i audit: tests/skupine.cjs i docs/razvrstavanje-pregled.json.

Sljedeće: povezati pripremljeni indeks s aplikacijom u radnoj grani, provjeriti memoriju/učitavanje na mobitelu i dnevno automatsko obnavljanje; pregled prije objave. Poznata pogrešna količina kruha 310g ->31kg u cjeniku nije riješena ovim razvrstavanjem.

Spremati nakon cjeline ili otprilike svakih pet minuta aktivnog rada; korisnik ne želi stalna pitanja i potvrde.
