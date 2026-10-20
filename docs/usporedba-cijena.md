# Jedinične cijene i iznos za pakiranja — 20.10.2026.

Korisnik je potvrdio: količina znači broj pakiranja, a povoljnost se uspoređuje po kg/l/kom. Broj pakiranja ne utječe na poredak.

Glavni ukupan iznos zbraja cijene cijelih odabranih pakiranja. Usporedba trgovina računa jednu osnovnu jedinicu svake stavke; usporedne količine i najpovoljnija kombinacija svih dopuštenih trgovina izričito su prikazane. Cijena pakiranja u svakoj trgovini je zaseban iznos. Nepotpune košarice su označene i ne proglašavaju se najboljima za puni popis.

Iznos pakiranja u jednoj trgovini može biti manji uz manju dobivenu količinu. To ne znači nižu jediničnu cijenu. Glavni prikaz i usporedni zbroj stoga imaju različite jasne oznake. Usporedni zbroj nije iznos na blagajni.

Uklonjena je pretvorba većeg broja komada u manji broj pakiranja za jaja i druge višekomadne proizvode. Odabir najjeftinijeg lanca za isti proizvod sada radi i kad cijene nisu unaprijed sortirane.

Provjere: node tests/kosarica.cjs; node tests/skupine.cjs; node --check site/aplikacija.js; Playwright sa sintetičkim cjenikom, odabirom trgovine, promjenom količina i širinama 320/390/768/1280px. Nema JS grešaka ni vodoravnog prelijevanja. To nije revizija svih količina u izvornim cjenicima; poznat problem 310 g -> 31 kg ovim zahvatom nije popravljen.
