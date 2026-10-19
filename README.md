# 🛒 Najjeftinija košarica

Jednostavna web aplikacija za Android mobitel:

1. **Glasom složiš popis** za kupovinu (npr. „kruh, mlijeko i jaja”).
2. **Zaključaš popis** – aplikacija za svaku stavku pokaže **najjeftiniji proizvod**
   iz svih hrvatskih trgovačkih lanaca, s **trgovinom, cijenom i količinom**.
3. **Dodirom na proizvod** vidiš sljedeći najjeftiniji iz iste grupe
   (strelica ◀ vraća na prethodni).

Cijene se **svaki dan automatski** preuzimaju iz javnih cjenika koje trgovine po
zakonu moraju objavljivati (NN 75/2025), preko besplatnog projekta
[cijene.dev](https://cijene.dev). Isti proizvod (isti barkod) prodaje se u više
lanaca, ali u aplikaciji se pojavljuje **samo jednom** – s najnižom cijenom.

---

## Kako je pokrenuti (jednom, ~5 minuta, bez programiranja)

Sve se radi na stranici **github.com**, može i s mobitela, ali je lakše s računala.

### Korak 1 – Repozitorij mora biti javan
Besplatno objavljivanje radi samo za javne repozitorije.
`Settings` (Postavke) → skroz dolje `Danger Zone` → `Change visibility` → **Public**.
(Ako je već javan, preskoči.)

### Korak 2 – Uključi GitHub Pages
`Settings` → u lijevom izborniku `Pages` → pod **Source** odaberi **GitHub Actions**.

### Korak 3 – Pokreni prvo ažuriranje
Gore klikni karticu `Actions` → lijevo **Dnevno ažuriranje cijena** →
desno gumb **Run workflow** → zeleni **Run workflow**.
Pričekaj par minuta da se pojavi zelena kvačica ✅.

### Korak 4 – Otvori aplikaciju na mobitelu
U **Google Chromeu** na Androidu otvori:

**https://antiquecroatianoak-sudo.github.io/Najjeftinija-kosarica/**

### Korak 5 – Dodaj je na početni zaslon
U Chromeu: izbornik **⋮** (gore desno) → **Dodaj na početni zaslon** / **Instaliraj aplikaciju**.
Sad je otvaraš kao svaku drugu aplikaciju.

Kad prvi put dodirneš 🎤, Chrome će pitati smiješ li koristiti mikrofon – odaberi **Dopusti**.

---

## Svakodnevno korištenje

- Dodirni **🎤 Reci što trebaš kupiti** i izgovori stvari. Može više odjednom:
  „kruh, mlijeko, jaja i banane”.
- Pogrešnu stavku makni crvenim **✕**.
- Dodirni **🔒 Zaključaj popis** – vidiš najjeftinije proizvode i ukupnu cijenu.
- Ne sviđa ti se proizvod? **Dodirni ga** za sljedeći najjeftiniji.
- **🔓 Otključaj** ako želiš dodati ili maknuti stavke.
- Popis ostaje spremljen u mobitelu i kad zatvoriš aplikaciju.

Savjet: koristi jednostavne nazive kakvi pišu na proizvodima (npr. „mlijeko”,
„toaletni papir”, „maslinovo ulje”). Ako nešto ne nađe, probaj drugu riječ.

---

## Što je gdje (za znatiželjne)

| Datoteka | Čemu služi |
|---|---|
| `site/index.html`, `site/stil.css`, `site/aplikacija.js` | Sama aplikacija (izgled i ponašanje) |
| `scripts/azuriraj_cijene.py` | Preuzima cijene i miče duplikate |
| `.github/workflows/dnevno-azuriranje.yml` | Svaki dan u ~7 h pokrene preuzimanje i objavi aplikaciju |

Napomene:
- Prikazuje se najniža cijena proizvoda u bilo kojoj poslovnici tog lanca
  (uključujući akcijske cijene). U tvojoj poslovnici cijena može biti malo drukčija.
- Metro je izostavljen jer je veleprodaja (treba poslovna kartica).
