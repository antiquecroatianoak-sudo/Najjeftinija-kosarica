# Jedinične cijene i iznos za pakiranja — 20.10.2026.

Korisnik je potvrdio: količina znači broj pakiranja, a povoljnost se uspoređuje po kg/l/kom. Broj pakiranja ne utječe na poredak.

Glavni ukupan iznos zbraja cijene cijelih odabranih pakiranja. Usporedba trgovina računa jednu osnovnu jedinicu svake stavke; usporedne količine i najpovoljnija kombinacija svih dopuštenih trgovina izričito su prikazane. Cijena pakiranja u svakoj trgovini je zaseban iznos. Nepotpune košarice su označene i ne proglašavaju se najboljima za puni popis.

Iznos pakiranja u jednoj trgovini može biti manji uz manju dobivenu količinu. To ne znači nižu jediničnu cijenu. Glavni prikaz i usporedni zbroj stoga imaju različite jasne oznake. Usporedni zbroj nije iznos na blagajni.

Uklonjena je pretvorba većeg broja komada u manji broj pakiranja za jaja i druge višekomadne proizvode. Odabir najjeftinijeg lanca za isti proizvod sada radi i kad cijene nisu unaprijed sortirane.

Provjere: node tests/kosarica.cjs; node tests/skupine.cjs; node --check site/aplikacija.js; Playwright sa sintetičkim cjenikom, odabirom trgovine, promjenom količina i širinama 320/390/768/1280px. Nema JS grešaka ni vodoravnog prelijevanja. To nije revizija svih količina u izvornim cjenicima; poznat problem 310 g -> 31 kg ovim zahvatom nije popravljen.

## Dopuna nakon korisnikove provjere — 20.10.2026.
Prethodna fiksna usporedba po jednoj osnovnoj jedinici nije odgovarala očekivanju. Sve trgovine sada dobivaju stvarnu referentnu količinu trenutno prikazanog odabranog artikla: broj pakiranja puta sadržaj. Dva mlijeka od litre znače 2 l u svakoj trgovini, odnosno deset pakiranja po 200 ml. Referentna osnovna jedinica također se uzima iz odabranog proizvoda. Nepotpune košarice nemaju usporedni novčani zbroj. Jedinična cijena i dalje određuje izbor proizvoda; ukupna košarica uvažava stvarne odabrane količine. Za pakiranja koja ne daju točnu količinu, posebno se prikazuje cijena cijelih pakiranja za barem traženu količinu.

## Ispravak: odabir jedne trgovine mijenjao je referentnu količinu — 20.10.2026.
Uzrok (reproducirano): referentna količina uzimala se iz trenutno prikazanog popisa ponuda, a on se u pregledu jedne trgovine sužava na tu trgovinu. Ako ta trgovina ima drugo pakiranje (npr. 100 ml umjesto 1 l), usporedba se tiho prebacivala s 1 l na 0,1 l, a glavni iznos zbrajao je jedno malo pakiranje. Razlika između mješovite košarice i jedne trgovine tako je mogla biti i desetak puta.

Namjeravano ponašanje (nepromijenjeno značenje količine: broj pakiranja × sadržaj odabranog artikla):
- Referentni artikl uvijek dolazi iz pregleda svih dopuštenih trgovina. Ulazak u jednu trgovinu i izlazak iz nje ne mijenjaju ga; listanje proizvoda unutar jedne trgovine ne mijenja referencu.
- U pregledu jedne trgovine kartica i glavni iznos prikazuju cijela pakiranja te trgovine za barem referentnu količinu (npr. 10 × 100 ml za 1 l), isto kao redak te trgovine u usporedbi.
- Promjena dopuštenih trgovina (uključivanje/isključivanje) vraća referencu na najpovoljniju ponudu.

Provjere: node tests/kosarica.cjs (novi regresijski slučaj za različita pakiranja po trgovinama pada na starom kodu), node tests/skupine.cjs, node tests/glasovni-unos.cjs, Playwright sa sintetičkim cjenikom na 320/390/1280 px bez JS grešaka i vodoravnog prelijevanja.

## Uvoz količina: pakiranje iza količine — 20.10.2026.
Nazivi poput „Jogurt 125 g x 4” ili „Voda 0,5 L x 6” prije su se čitali kao jedno pakiranje (125 g), pa je cijena po kg bila četiri puta previsoka. Sada se prepoznaju kao 500 g odnosno 3 l, kao i postojeći oblik „6x0,5 l”. Provjera: python3 tests/kolicine.py.

Nije provjereno na produkcijskom cjeniku: iz ovog okruženja nisu dostupni github.io ni cijene.dev, pa broj zahvaćenih proizvoda, svježina, duplikati i greške uvoza nisu izmjereni. Poznati 310 g -> 31 kg nije reproduciran na samom parseru; vjerojatno dolazi iz izvornog zapisa količine ili dopune.

## Istaknuti iznos trgovine = zbroj kartica te trgovine — 20.10.2026.
Prije: redak trgovine istaknuto je prikazivao usporedni iznos (jedinična cijena × referentna količina, s decimalnim dijelovima pakiranja) i po njemu poredao trgovine, a nakon otvaranja trgovine kartice zbrajaju cijela pakiranja. Uz to, proizvodi bez usporedive količine nisu ulazili u iznos retka, ali jesu u kartice.
Sada: istaknuti iznos i poredak trgovina su iznos cijelih pakiranja, izračunat istom ponudom i istim brojem pakiranja kao kartica kad se trgovina otvori (uključujući alternativu odabranu u toj trgovini). Pri otvaranju trgovine kartice zadano prikazuju iste ponude kao njezin redak. Usporedni iznos po jedinici ostaje kao sporedan redak s oznakom „usporedba, nije iznos na blagajni”. Poredak proizvoda po jediničnoj cijeni nije promijenjen. Nepotpune košarice i dalje su „Nepotpuno”, uz iznos za prikazane proizvode.
Ovo ne objašnjava nužno svaku prijavljenu razliku; korisnikova točna košarica nije poznata.
