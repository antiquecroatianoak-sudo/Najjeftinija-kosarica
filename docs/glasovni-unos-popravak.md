# Glasovni unos: regresija prijavljena 20.10.2026.

Korisnik potvrđuje da je prethodni način prepoznavanja radio za jedan artikl. Više naziva završavalo je u jednoj stavci. Nakon uvođenja continuous=true i interimResults=true Chrome pokazuje slušanje bez rezultata. Uzrok na stvarnom uređaju nije potvrđen.

Vraćene su continuous=false i interimResults=false. Aplikacija zadržava sesiju do drugog pritiska te nakon završetka kratkog prepoznavanja pokreće novo. Razdvajanje više artikala ostaje uključeno i za običan tekstni unos. Naknadni pritisak dopunjava spremljeni popis.

Prikaz razlikuje pokušaj pokretanja od događaja audiostart. Postoje ograničenja čekanja pokretanja (15 s), rezultata (20 s nakon događaja servisa ili rezultata) i završetka (2 s). Dva uzastopna prazna završetka prekidaju automatske ponovne pokušaje. Kasni događaji iz stare sesije/instance ignoriraju se. Odbijena dozvola, blokirana usluga, mreža, nedostupan mikrofon i nepodržan jezik imaju zasebne poruke.

Ako nema Web Speech API-ja, aplikacija objašnjava ograničenje i otvara standardno tekstno polje. Korisnik može koristiti diktiranje svoje tipkovnice ako ga uređaj nudi. To nije ugrađeni glasovni unos aplikacije niti jamstvo diktiranja u svakom pregledniku. Nije dodan zaseban servis za transkripciju, nije ugovoren plaćeni servis i nije pohranjen API ključ.

Provjere: tests/glasovni-unos.cjs (simulacije uspjeha i kvarova), tests/kosarica.cjs, tests/skupine.cjs i lokalni Chromium s umetnutim simuliranim prepoznavanjem. Stvarni mikrofon korisnika nije moguće provjeriti iz ovog okruženja. Popravak regresije zahtijeva korisnički pokus na stvarnom uređaju; ne označavati univerzalni glasovni unos riješenim.
