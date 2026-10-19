"use strict";

// Jedna pravila za cijeli cjenik. Marka, lanac i pakiranje ne određuju vrstu.
// Pravila su namjerno pregledna: nepoznat naziv ostaje neklasificiran i pretraživ.
(function (root) {
  const normaliziraj = (s) => String(s).toLowerCase().replace(/đ/g, "d").normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]+/g, " ").trim();
  const korijen = (s) => {
    const k = s.length >= 4 ? s.replace(/[aeiou]+$/, "") : s;
    return k.length < 3 ? s : k; // Brie ne smije postati kratica „br.”.
  };
  const nastavci = new Set(["", "a", "e", "i", "o", "u", "om", "em", "im", "ima", "ama", "ih", "oj", "og", "ja", "je", "ji", "ju", "jom", "ovi", "ove", "ova", "evi", "eve"]);
  const odgovara = (w, k) => w.startsWith(k) && nastavci.has(w.slice(k.length));
  const prijedlozi = new Set(["s", "sa", "od", "za", "u", "na", "bez", "iz", "po"]);
  // id | naziv osnovne vrste | istovrijedni nazivi, a ne sastojci te vrste
  const zapis = `kruh|Kruh|kruh;hljeb;hleb;ciabatta;baget;baguette;baggette
pecivo|Pecivo|pecivo;zemicka;zemička;kajzerica;lepinja;somun;žemlja
tost|Tost|tost;toast
mrvice|Krušne mrvice|krušne mrvice;prezla;prezle
krutoni|Krutoni|krutoni;kockice kruha
brasno|Brašno|brašno
krmno-brasno|Krmno brašno|krmno brašno;brašno krmno
secer|Šećer|šećer
sol|Sol|sol
riza|Riža|riža
tjestenina|Tjestenina|tjestenina;špageti;spaghetti;makaroni;penne;fusilli;tagliatelle;rezanci
njoki|Njoki|njoki;gnocchi
griz|Griz|griz;krupica
kasa|Kaše|kaša
palenta|Palenta|palenta;žganci
zobene-pahuljice|Zobene pahuljice|zobene pahuljice
pahuljice|Pahuljice|pahuljice;cornflakes;muesli;musli;granola
mlijeko|Mlijeko|mlijeko
biljno-mlijeko|Biljni napitci|biljni napitak;bademovo mlijeko;zobeno mlijeko;kokosovo mlijeko;sojino mlijeko
mlijeko-tijelo|Mlijeko za tijelo|mlijeko za tijelo;mlijeko za njegu tijela;mlijeko tijelo
jogurt|Jogurt|jogurt;yogurt
kefir|Kefir|kefir
acidofil|Acidofil|acidofil
sir|Sir|sir;gouda;gauda;edamer;ementaler;mozzarella;mascarpone;ricotta;parmezan;brie;camembert;feta
vrhnje|Vrhnje|vrhnje;pavlaka
maslac|Maslac|maslac;butter
margarin|Margarin|margarin
jaja|Jaja|jaja;jaje
puding|Puding|puding;pudding
sladoled|Sladoled|sladoled
ulje|Jestivo ulje|ulje
tehnicko-ulje|Tehničko ulje|motorno ulje;ulje za motore
kozmeticko-ulje|Kozmetičko ulje|ulje za tijelo;ulje za kosu;ulje za usne;ulje za nokte
mirisno-ulje|Mirisno ulje|mirisno ulje;ulje mirisno;eterično ulje
ocat|Ocat|ocat;sirće
med|Med|med
dzem|Džem i marmelada|džem;marmelada;pekmez
cokoladni-namaz|Čokoladni namaz|čokoladni namaz;nutella
namaz|Namaz|namaz
pasteta|Pašteta|pašteta
humus|Humus|humus;hummus
ajvar|Ajvar|ajvar
senf|Senf|senf;mustard
majoneza|Majoneza|majoneza
kecap|Kečap|kečap;ketchup;kecap
umak|Umak|umak;pesto
juha|Juha|juha;soup
zacin|Začini|začin
kvasac|Kvasac|kvasac
prasak-pecivo|Prašak za pecivo|prašak za pecivo
soda-bikarbona|Soda bikarbona|soda bikarbona
zelatina|Želatina|želatina
cokolada|Čokolada|čokolada;čokol.;čok.
keks|Keksi|keks;keksi;cookies
napolitanke|Napolitanke|napolitanka;napolitanke;wafer
bomboni|Bomboni|bombon;bomboni;karamela;karamele
praline|Praline|pralina;praline;bombonijera
zvakace|Žvakaće gume|žvakaća guma;žvakaće gume;žvakaće
cips|Čips|čips;chips
smoki|Flips|flips;smoki
krekeri|Krekeri|kreker;krekeri
kokice|Kokice|kokice;popcorn
kolac|Kolači|kolač
torta|Torte|torta
kroasan|Kroasani|kroasan;croissant;croasan
krafna|Krafne|krafna;krofna;donut
burek|Burek|burek
pizza|Pizza|pizza;pizza
sendvic|Sendviči|sendvič
salata|Gotove salate|salata
piletina|Piletina|piletina;pileći;pileća;pileće;pile;chicken
puretina|Puretina|puretina;pureći;pureća;pureće;turkey
svinjetina|Svinjetina|svinjetina;svinjski;svinjska;svinjsko
junetina|Junetina|junetina;juneći;juneća;juneće
govedina|Govedina|govedina;goveđi;goveđa;goveđe
teletina|Teletina|teletina;teleći;teleća;teleće
janjetina|Janjetina|janjetina;janjeći;janjeća;janjeće
mljeveno-meso|Mljeveno meso|mljeveno meso;meso mljeveno
cevapi|Ćevapi|ćevapi;ćevapčići
pljeskavica|Pljeskavice|pljeskavica
sunka|Šunka|šunka
salama|Salama|salama
kobasica|Kobasice|kobasica;hrenovka;hrenovke
prsut|Pršut|pršut
slanina|Slanina|slanina;panceta;špek
tuna|Tuna|tuna;tunjevina
sardina|Sardine|sardina;srdela
losos|Losos|losos
oslic|Oslić|oslić
bakalar|Bakalar|bakalar
skusa|Skuša|skuša
pastrva|Pastrva|pastrva
orada|Orada|orada
brancin|Brancin|brancin;lubin
lignje|Lignje|lignja;lignje
kozice|Kozice i škampi|kozica;kozice;škamp;škampi
skoljke|Školjke|školjka;školjke;dagnja;dagnje
krumpir|Krumpir|krumpir;krompir
rajcica|Rajčica|rajčica;paradajz
paprika|Paprika|paprika
krastavac|Krastavci|krastavac;krastavci
mrkva|Mrkva|mrkva
luk|Luk|luk
cesnjak|Češnjak|češnjak;bijeli luk
kupus|Kupus|kupus;zelje
kelj|Kelj|kelj
spinat|Špinat|špinat
blitva|Blitva|blitva
tikvica|Tikvice|tikvica;tikvice
patlidzan|Patlidžan|patlidžan
brokula|Brokula|brokula
cvjetaca|Cvjetača|cvjetača;karfiol
celer|Celer|celer
cikla|Cikla|cikla
poriluk|Poriluk|poriluk
gljive|Gljive|gljiva;gljive;šampinjon;šampinjoni
grah|Grah|grah
grasak|Grašak|grašak
leca|Leća|leća
slanutak|Slanutak|slanutak
kukuruz|Kukuruz|kukuruz
masline|Masline|maslina;masline
jabuka|Jabuke|jabuka
banana|Banane|banana
naranca|Naranče|naranča;naranača;naran.;naranč.;orange
mandarina|Mandarine|mandarina
limun|Limun|limun;lemon
grejp|Grejp|grejp;grapefruit
kruska|Kruške|kruška
breskva|Breskve|breskva;peach
nektarina|Nektarine|nektarina
marelica|Marelice|marelica;apricot
sljiva|Šljive|šljiva
jagoda|Jagode|jagoda;strawberry
malina|Maline|malina;raspberry
borovnica|Borovnice|borovnica;blueberry
visnja|Višnje|višnja
tresnja|Trešnje|trešnja
grozdje|Grožđe|grožđe
lubenica|Lubenica|lubenica
dinja|Dinja|dinja
kivi|Kivi|kivi;kiwi
ananas|Ananas|ananas;pineapple
mango|Mango|mango
avokado|Avokado|avokado
orah|Orasi|orah;orasi
badem|Bademi|badem
lješnjak|Lješnjaci|lješnjak;lješnjaci
kikiriki|Kikiriki|kikiriki
pistacija|Pistacije|pistacija
indijski-orah|Indijski oraščići|indijski oraščić;indijski orah
grozdjice|Grožđice|grožđica;grožđice
datulje|Datulje|datulja;datulje
sok|Voćni sok|sok;juice
nektar|Voćni nektar|nektar;nectar
sirup|Sirup|sirup
napitak|Napitci|napitak;piće
voda|Voda|voda
mineralna-voda|Mineralna voda|mineralna voda;voda mineralna
gazirano-pice|Gazirana pića|gazirano piće;gazirani sok;cola;coca cola;fanta;sprite;cockta;pepsi;fizzy;schweppes;sanpellegrino
energetsko-pice|Energetska pića|energetsko piće;energy drink;red bull
kava|Kava|kava;coffee;caffe
caj|Čaj|čaj;tea
kakao|Kakao|kakao;cocoa
pivo|Pivo|pivo;beer
vino|Vino|vino;wine
pjenušac|Pjenušac|pjenušac;prosecco;šampanjac
rakija|Rakija|rakija;lozovača;travarica;šljivovica
votka|Votka|votka;vodka
gin|Gin|gin
viski|Viski|viski;whisky;whiskey
rum|Rum|rum
liker|Liker|liker
sampon|Šampon|šampon;shampoo
regenerator|Regenerator|regenerator
gel-tusiranje|Gel za tuširanje|gel za tuširanje;gel tuširanje
sapun|Sapun|sapun;soap
dezodorans|Dezodorans|dezodorans;deodorant;deo
krema|Krema|krema;cream
losion|Losion|losion;lotion
pasta-zube|Pasta za zube|pasta za zube;zubna pasta
cetkica-zube|Četkica za zube|četkica za zube
toaletni-papir|Toaletni papir|toaletni papir;wc papir
maramice|Maramice|maramica;maramice
pelene|Pelene|pelena;pelene
ulosci|Higijenski ulošci|uložak;ulošci
tamponi|Tamponi|tampon
deterdzent|Deterdžent|deterdžent;det.
omeksivac|Omekšivač|omekšivač
sredstvo-ciscenje|Sredstvo za čišćenje|sredstvo za čišćenje;čistač;čistilo
spuzvica|Spužve|spužva;spužvica
krpa|Krpe|krpa
rukavice|Rukavice|rukavica;rukavice
hrana-zivotinje|Hrana za životinje|hrana
hrana-bebe|Hrana za bebe|hrana za bebe;hrana za dojenčad
pijesak-macke|Pijesak za mačke|pijesak
vrecice|Vrećice|vrećica;vrećice;vreć.;vreća
kosara|Košare|košara;košarica
kalup|Kalupi|kalup
posuda|Posude|posuda
kutija|Kutije|kutija
tanjur|Tanjuri|tanjur
casa|Čaše|čaša
salica|Šalice|šalica
boca|Boce|boca
tava|Tave|tava
lonac|Lonci|lonac;lonci
noz|Noževi|nož;noževi
daska|Daske|daska
cjedilo|Cjedila|cjedilo
stolnjak|Stolnjaci|stolnjak
salvete|Salvete|salveta;salvete
boja|Boje|boja
naljepnica|Naljepnice|naljepnica
igracka|Igračke|igračka;igr.;igrač.
svijeca|Svijeće|svijeća;lampion
zarulja|Žarulje|žarulja
baterija|Baterije|baterija
sjeme|Sjeme|sjeme
cvijet|Cvijeće|cvijet;cvijeće
majica|Majice|majica
carape|Čarape|čarapa;čarape
rucnik|Ručnici|ručnik
torba|Torbe|torba`;

  const vrste = zapis.split("\n").map((s) => {
    const [id, naziv, aliases] = s.split("|");
    return { id, naziv, aliases: aliases.split(";").map((a) => normaliziraj(a).split(" ").map(korijen)) };
  });
  const definicije = new Map(vrste.map((v) => [v.id, v]));
  const indeks = new Map();
  for (const v of vrste) for (const alias of v.aliases) {
    const k = alias[0].slice(0, 3);
    if (!indeks.has(k)) indeks.set(k, []);
    indeks.get(k).push({ v, alias });
  }
  const voce = new Set(["naranca", "jabuka", "banana", "mandarina", "limun", "grejp", "kruska", "breskva", "marelica", "sljiva", "jagoda", "malina", "borovnica", "visnja", "tresnja", "grozdje", "ananas", "mango"]);
  const okusiVrste = new Set(["sok", "nektar", "sirup", "jogurt", "dzem", "sladoled", "caj", "napitak"]);
  const overrides = new Map([
    ["sok", new Set(["nektar", "sirup", "gazirano-pice", "energetsko-pice"])],
    ["voda", new Set(["mineralna-voda"])],
    ["brasno", new Set(["krmno-brasno"])],
    ["namaz", new Set(["cokoladni-namaz"])],
  ]);

  function pronadiRijeci(r) {
    const hits = [];
    for (let pos = 0; pos < r.length; pos++) {
      for (const { v, alias } of indeks.get(r[pos].slice(0, 3)) || []) {
        if (alias.every((a, j) => r[pos + j] && odgovara(r[pos + j], a))) hits.push({ id: v.id, pos, duzina: alias.length });
      }
    }
    return hits;
  }

  const opisne = new Set(["bio", "eko", "organsko", "organic", "premium", "mini", "maxi", "xxl", "xl", "domaci", "domaca", "domace", "svjezi", "svjeza", "svjeze", "trajno", "trajno", "snizeno", "pak", "pakirano", "pakirani", "svj", "smrznuti", "smrznuta", "smrznuto", "zamrznuti", "zamrznuta", "zamrznuto", "bijeli", "crni", "polubijeli", "razani", "integralni", "rezani", "tvrdi", "meki", "mladi", "trajni", "prirodni", "vocni", "100", "n", "fis"]);
  function analiziraj(tekst, marka = 0, upit = false, pripremljeneRijeci = null) {
    const r = pripremljeneRijeci || normaliziraj(tekst).split(" ").filter(Boolean);
    const hits = pronadiRijeci(r);
    // „s okusom”, „za kruh”, „od sira” opisuju sastojak ili namjenu.
    const boundary = r.findIndex((w) => prijedlozi.has(w));
    const heads = hits.filter((h) => boundary < 0 || h.pos < boundary || (h.pos === 0 && h.duzina > 1));
    heads.sort((a, b) => a.pos - b.pos || b.duzina - a.duzina);
    let glavni = heads[0] || null;
    // Nepoznate riječi prije glavne imenice mogu skrivati stvarnu vrstu.
    // Ne nagađaj da je sastojak (npr. mlijeko u kavi) glavni proizvod.
    if (glavni && !upit && r.slice(Math.max(0, Number(marka) || 0), glavni.pos)
      .some((w) => !opisne.has(w) && !/^\d/.test(w))) glavni = null;
    if (glavni && overrides.has(glavni.id)) {
      const special = hits.find((h) => overrides.get(glavni.id).has(h.id));
      if (special) glavni = special;
    }
    // Oprema za kruh i slični proizvodi dobivaju svoju vrstu po glavnoj imenici.
    const naziv = r.join(" ");
    const promijeni = (id) => { glavni = { ...glavni, id }; };
    if (glavni?.id === "mlijeko") {
      if (/\b(tijel\w*|njeg\w*|lice|lica|ruke|suncanje)\b/.test(naziv)) promijeni("mlijeko-tijelo");
      else if (/\b(kokos\w*|sojin\w*|soja|bademov\w*|zoben\w*|rizino)\b/.test(naziv)) promijeni("biljno-mlijeko");
    }
    if (glavni?.id === "ulje") {
      if (/\b(motor\w*|lancol|pantherol|dvotaktn\w*|cetverotaktn\w*)\b/.test(naziv)) promijeni("tehnicko-ulje");
      else if (/\b(mirisno|mirisna|etericn\w*)\b/.test(naziv)) promijeni("mirisno-ulje");
      else if (/\b(tijel\w*|kosu|kose|masazu|nokte|usne|lica|lice|celul\w*|ogx)\b/.test(naziv)) promijeni("kozmeticko-ulje");
    }
    if (glavni?.id === "jaja" && /\b(ukras\w*|uskr\w*|plast\w*|stirop\w*|styropor|pik|privjesak|staklen\w*|cm|kosaric\w*|sarena|bojan\w*)\b/.test(naziv)) glavni = null;
    if (glavni?.id === "hrana-zivotinje") {
      if (/\b(beb\w*|dojenc\w*|djeca|djecu)\b/.test(naziv)) promijeni("hrana-bebe");
      else if (!/\b(pas|pse|psa|psi|ps\w*|mack\w*|ptice|ptic\w*|glodav\w*|ribic\w*|zivotinj\w*)\b/.test(naziv)) glavni = null;
    }
    if (glavni?.id === "sol" && /\b(kupku|kupanje|peril\w*|odmrz\w*|ceste)\b/.test(naziv)) glavni = null;
    if (glavni && (glavni.id === "kruh" || voce.has(glavni.id))
      && /\b(ukras\w*|umjetn\w*|bozic\w*|stirop\w*|staklen\w*)\b/.test(naziv)) glavni = null;
    const kozmetika = /^(balea|nivea|essence|alverde|sundance|afrodita|uriage|ogx|weleda|eucerin)\b/.test(naziv);
    if (kozmetika && glavni && !["mlijeko-tijelo", "kozmeticko-ulje", "mirisno-ulje", "krema", "losion", "sampon", "regenerator", "sapun", "gel-tusiranje", "dezodorans", "pasta-zube"].includes(glavni.id)) glavni = null;
    const okusi = [...new Set(hits.filter((h) => voce.has(h.id)).map((h) => h.id))].sort();
    return { rijeci: r, hits, glavni, okusi };
  }

  function otisak(proizvodi) {
    let hash = 2166136261;
    for (const p of proizvodi) {
      const s = p[0] + "\x00" + p[1] + "\x00" + p[4] + "\n";
      for (let j = 0; j < s.length; j++) hash = Math.imul(hash ^ s.charCodeAt(j), 16777619);
    }
    return (hash >>> 0).toString(16).padStart(8, "0");
  }
  function pripremi(proizvodi, spremljeno = null, tokeni = null) {
    if (spremljeno && (spremljeno.verzija !== 1 || spremljeno.brojProizvoda !== proizvodi.length
      || spremljeno.otisak !== otisak(proizvodi))) throw new Error("Indeks skupina ne odgovara cjeniku");
    // Na mobitel šalji mali unaprijed pripremljeni indeks, bez analize 237.000 naziva u memoriji.
    const analiza = spremljeno ? null : proizvodi.map((p) => analiziraj(p[0], p[4]));
    const dajAnalizu = (i) => analiza ? analiza[i] : analiziraj(proizvodi[i][0], proizvodi[i][4], false, tokeni?.[i]);
    const poVrsti = new Map();
    const katalog = new Map();
    const vrstePoRedu = new Array(proizvodi.length).fill(null);
    const dodaj = (id, naziv, i, roditelj = null) => {
      if (!katalog.has(id)) katalog.set(id, { id, naziv, roditelj, indeksi: [] });
      katalog.get(id).indeksi.push(i);
    };
    let nerazvrstano = 0;
    if (spremljeno) {
      for (const s of spremljeno.katalog) {
        katalog.set(s.id, s);
        if (!s.roditelj) {
          poVrsti.set(s.id, s.indeksi);
          for (const i of s.indeksi) {
            if (!Number.isInteger(i) || i < 0 || i >= proizvodi.length) throw new Error("Neispravan indeks proizvoda");
            vrstePoRedu[i] = s.id;
          }
        }
      }
      nerazvrstano = vrstePoRedu.filter((x) => !x).length;
    } else analiza.forEach((a, i) => {
      if (!a.glavni) { nerazvrstano++; return; }
      const id = a.glavni.id;
      vrstePoRedu[i] = id;
      if (!poVrsti.has(id)) poVrsti.set(id, []);
      poVrsti.get(id).push(i);
      dodaj(id, definicije.get(id).naziv, i);
      if (okusiVrste.has(id) && a.okusi.length) {
        const podid = id + "/" + a.okusi.join("+");
        dodaj(podid, definicije.get(id).naziv + " · " + a.okusi.map((x) => definicije.get(x).naziv).join(" + "), i, id);
      }
    });

    function razrijesiUpit(upit) {
      const q = analiziraj(upit, 0, true);
      if (!q.glavni) return null;
      const id = q.glavni.id;
      const aliasHit = q.hits.filter((h) => h.id === id).sort((a, b) => b.duzina - a.duzina)[0];
      const izostavi = new Set();
      if (aliasHit) for (let j = 0; j < aliasHit.duzina; j++) izostavi.add(aliasHit.pos + j);
      const trazeniOkusi = okusiVrste.has(id) ? q.okusi : [];
      if (trazeniOkusi.length) for (const h of q.hits) if (voce.has(h.id)) {
        for (let j = 0; j < h.duzina; j++) izostavi.add(h.pos + j);
      }
      const dodatno = q.rijeci.filter((w, j) => !izostavi.has(j) && !prijedlozi.has(w)).map(korijen);
      return { q, id, dodatno, trazeniOkusi };
    }
    function pogoci(upit) {
      const up = razrijesiUpit(upit);
      if (!up) return null; // Neprepoznati nazivi ostaju u postojećem pretraživanju.
      const {id, dodatno, trazeniOkusi} = up;
      const clanovi = id === "kruh" ? [...(poVrsti.get(id) || []), ...(poVrsti.get("tost") || [])] : poVrsti.get(id) || [];
      return clanovi.filter((i) => {
        const a = dajAnalizu(i);
        // Naranča+jabuka nije isto što i sok samo od naranče.
        if (trazeniOkusi.length && a.okusi.join("+") !== trazeniOkusi.join("+")) return false;
        return dodatno.every((k) => a.rijeci.some((w) => odgovara(w, k)));
      });
    }
    // Moguća podudaranja nisu potvrđeni članovi skupine. Ostaju vidljiva za pregled.
    function moguciPogoci(upit) {
      const up = razrijesiUpit(upit);
      if (!up) return [];
      const aliasi = definicije.get(up.id).aliases;
      const nadji = [];
      for (let i = 0; i < proizvodi.length; i++) {
        if (vrstePoRedu[i]) continue;
        const rijeci = analiza ? analiza[i].rijeci : tokeni?.[i] || normaliziraj(proizvodi[i][0]).split(" ");
        const imaVrstu = aliasi.some((alias) => rijeci.some((_, p) => alias.every((k, j) => rijeci[p+j] && odgovara(rijeci[p+j], k))));
        if (!imaVrstu) continue;
        if (!up.dodatno.every((k) => rijeci.some((w) => odgovara(w, k)))) continue;
        const a = dajAnalizu(i);
        if (up.trazeniOkusi.length && a.okusi.join("+") !== up.trazeniOkusi.join("+")) continue;
        nadji.push(i);
      }
      return nadji;
    }
    return { pogoci, moguciPogoci, katalog: [...katalog.values()], nerazvrstano, ukupno: proizvodi.length,
      vrstaProizvoda: (i) => vrstePoRedu[i],
      izvezi: () => ({ verzija: 1, brojProizvoda: proizvodi.length, otisak: otisak(proizvodi), katalog: [...katalog.values()] }) };
  }
  const api = { pripremi, analiziraj, definicije: vrste.map(({id,naziv}) => ({id,naziv})) };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.Skupine = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
