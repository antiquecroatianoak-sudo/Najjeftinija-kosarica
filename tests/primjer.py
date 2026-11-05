"""Izradi primjer arhive cjenika u obliku koji koristi cijene.dev (za testove i lokalni pregled bez interneta).

Namjerno sadrži zamke iz stvarnih cjenika: cijenu 0,00, cijenu 100× preveliku u jednoj poslovnici, količinu
upisanu kao 31 kg umjesto 310 g, proizvod bez barkoda u dva lanca, višestruko pakiranje 6×1,5 l, akcijske
cijene, lanac koji danas nedostaje (NTL) i cjenik koji nije složen po poslovnici (Lidl).

    python tests/primjer.py <mapa>
"""

from __future__ import annotations

import csv
import io
import random
import sys
import zipfile
from pathlib import Path

# naziv, marka, količina (polje), jedinica (polje), osnovna količina, vrsta, osnovna cijena EUR, barkod
PROIZVODI = [
    ("Kruh polubijeli 500 g", "Pan-Pek", "500", "g", 0.5, "kg", 1.29, "3850104000011"),
    ("Kruh bijeli 700 g", "Klara", "700", "g", 0.7, "kg", 1.49, "3850104000028"),
    ("Kruh sa sjemenkama 500 g", "Klara", "500", "g", 0.5, "kg", 2.19, "3850104000035"),
    ("Kruh integralni 400 g", "Mlinar", "400", "g", 0.4, "kg", 1.99, "3850104000042"),
    ("Tost kruh 500 g", "Pan-Pek", "500", "g", 0.5, "kg", 1.39, "3850104000059"),
    ("Kruh polubijeli 310 g", "Mlinar", "31", "kg", 0.31, "kg", 0.89, "3850104000066"),
    ("Brašno za kruh T-850 1 kg", "Podravka", "1", "kg", 1.0, "kg", 1.09, "3850104000073"),
    ("Mlijeko trajno 2,8% m.m. 1 l", "Dukat", "1", "l", 1.0, "l", 1.29, "3850108000014"),
    ("Mlijeko trajno 2,8% m.m. 1 l", "K Plus", "1", "l", 1.0, "l", 0.99, "4061458000015"),
    ("Svježe mlijeko 3,2% m.m. 1 l", "Vindija", "1", "l", 1.0, "l", 1.39, "3850108000021"),
    ("Mlijeko bez laktoze 1,5% 1 l", "Dukat", "1", "l", 1.0, "l", 1.69, "3850108000038"),
    ("Mlijeko trajno 0,5 l", "Meggle", "0,5", "l", 0.5, "l", 0.69, "3850108000045"),
    ("Mliječna čokolada 100 g", "Milka", "100", "g", 0.1, "kg", 1.49, "7622300000011"),
    ("Zobeni napitak 1 l", "Alpro", "1", "l", 1.0, "l", 2.49, "5411188000016"),
    ("Jogurt tekući 2,8% 1 kg", "Dukat", "1", "kg", 1.0, "kg", 1.59, "3850108000052"),
    ("Kiselo vrhnje 12% 180 g", "Vindija", "180", "g", 0.18, "kg", 0.79, "3850108000069"),
    ("Maslac 250 g", "Dukat", "250", "g", 0.25, "kg", 3.49, "3850108000076"),
    ("Sir gauda narezani 400 g", "Paladin", "400", "g", 0.4, "kg", 4.49, "3850108000083"),
    ("Svježi kravlji sir 500 g", "Dukat", "500", "g", 0.5, "kg", 1.99, "3850108000090"),
    ("Jaja M podni uzgoj 10/1", "Pipo", "10", "kom", 10, "kom", 2.69, "3850109000017"),
    ("Jaja L slobodni uzgoj 6 kom", "Pipo", "6", "kom", 6, "kom", 2.29, "3850109000024"),
    ("Krumpir bijeli 2 kg", "", "2", "kg", 2.0, "kg", 1.79, "2000000000015"),
    ("Krumpir mladi 1 kg", "", "1", "kg", 1.0, "kg", 1.29, "2000000000022"),
    ("Čips paprika 150 g", "Chipsy", "150", "g", 0.15, "kg", 1.79, "3850110000016"),
    ("Banane 1 kg", "", "1", "kg", 1.0, "kg", 1.39, "2000000000039"),
    ("Jabuke Gala 1 kg", "", "1", "kg", 1.0, "kg", 1.49, "2000000000046"),
    ("Sok od jabuke 1 l", "Fructal", "1", "l", 1.0, "l", 1.69, "3850111000013"),
    ("Riža dugo zrno 1 kg", "Zlatno polje", "1", "kg", 1.0, "kg", 1.99, "3850112000010"),
    ("Špageti 500 g", "Barilla", "500", "g", 0.5, "kg", 1.69, "8076800000017"),
    ("Penne 500 g", "Podravka", "500", "g", 0.5, "kg", 1.19, "3850112000027"),
    ("Šećer kristal 1 kg", "Viro", "1", "kg", 1.0, "kg", 1.09, "3850113000017"),
    ("Sol morska sitna 1 kg", "Solana Pag", "1", "kg", 1.0, "kg", 0.59, "3850113000024"),
    ("Suncokretovo ulje 1 l", "Zvijezda", "1", "l", 1.0, "l", 1.99, "3850114000014"),
    ("Maslinovo ulje ekstra djevičansko 0,5 l", "Monini", "0,5", "l", 0.5, "l", 6.99, "8005510000017"),
    ("Mljevena kava 250 g", "Franck", "250", "g", 0.25, "kg", 4.29, "3850115000011"),
    ("Mljevena kava 500 g", "Barcaffe", "500", "g", 0.5, "kg", 7.49, "3830015000017"),
    ("Voda izvorska negazirana 6x1,5 l", "Jana", "", "", 9.0, "l", 4.49, "3850116000018"),
    ("Mineralna voda 1,5 l", "Jamnica", "1,5", "l", 1.5, "l", 0.89, "3850116000025"),
    ("Pivo svijetlo 0,5 l", "Ožujsko", "0,5", "l", 0.5, "l", 1.09, "3850117000015"),
    ("Pileća prsa file 1 kg", "Perutnina Ptuj", "1", "kg", 1.0, "kg", 8.99, "3850118000012"),
    ("Pileći batak 1 kg", "Vindija", "1", "kg", 1.0, "kg", 4.49, "3850118000029"),
    ("Mljeveno miješano meso 500 g", "PIK", "500", "g", 0.5, "kg", 4.29, "3850118000036"),
    ("Šunka narezana 100 g", "Gavrilović", "100", "g", 0.1, "kg", 1.89, "3850119000019"),
    ("Hrenovke pileće 400 g", "Gavrilović", "400", "g", 0.4, "kg", 2.49, "3850119000026"),
    ("Tuna komadi u ulju 80 g", "Eva", "80", "g", 0.08, "kg", 1.49, "3850120000015"),
    ("Toaletni papir 3-slojni 10 kom", "Zewa", "10", "kom", 10, "kom", 4.99, "3850121000012"),
    ("Deterdžent za rublje 20 pranja", "Ariel", "1", "kom", 1, "kom", 9.99, "8001090000016"),
    ("Pasta za zube 75 ml", "Colgate", "75", "ml", 0.075, "l", 1.99, "8714789000011"),
    ("Keksi petit beurre 200 g", "Kraš", "200", "g", 0.2, "kg", 0.99, "3850122000019"),
    ("Banane premium 1 kg", "Chiquita", "1", "kg", 1.0, "kg", 1.79, "2000000000053"),
]
# proizvodi bez barkoda (marka + naziv + količina trebaju ih spojiti)
BEZ_BARKODA = [("Domaći kruh 600 g", "Pekara Dubravica", "600", "g", 0.6, "kg", 1.59)]

# lanac -> (broj poslovnica, faktor cijene, proizvodi koje nema)
LANCI = {
    "konzum": (6, 1.06, set()),
    "lidl": (3, 0.93, {"3850108000014"}),
    "kaufland": (2, 0.95, set()),
    "plodine": (3, 1.00, set()),
    "tommy": (3, 1.03, set()),
    "studenac": (4, 1.08, {"3850118000012"}),
    "spar": (3, 1.02, set()),
    "eurospin": (2, 0.92, {"3850115000011"}),
    "ntl": (2, 0.99, set()),
    "ktc": (2, 1.01, set()),
}
GRADOVI = [("Zagreb", "10000", 45.8150, 15.9819), ("Split", "21000", 43.5081, 16.4402), ("Rijeka", "51000", 45.3271, 14.4422),
           ("Osijek", "31000", 45.5550, 18.6955), ("Zadar", "23000", 44.1194, 15.2314), ("Velika Gorica", "10410", 45.7125, 16.0756)]


def poslovnice(lanac, n):
    out = []
    for i in range(n):
        grad, pbr, lat, lon = GRADOVI[i % len(GRADOVI)]
        vrsta = "hipermarket" if lanac == "spar" and i == 2 else "supermarket"
        out.append({"store_id": f"{lanac[:2].upper()}{i + 1:03d}", "type": vrsta, "address": f"Ulica {lanac.title()} {i + 10}",
                    "city": grad, "zipcode": pbr, "lat": lat + 0.004 * (i + 1) * (1 if i % 2 else -1), "lon": lon + 0.003 * (i + 1)})
    return out


def napravi_arhivu(put: Path, datum: str, bez=(), pomak=0.0):
    rnd = random.Random(datum)
    zf = zipfile.ZipFile(put, "w", zipfile.ZIP_DEFLATED)
    for lanac, (n, faktor, nema) in LANCI.items():
        if lanac in bez:
            continue
        st = poslovnice(lanac, n)
        proizvodi, cijene = [], []
        for pi, (naziv, marka, kol, jed, osn, vrsta, cijena, bk) in enumerate(PROIZVODI):
            if bk in nema:
                continue
            pid = f"{lanac[:1]}{pi + 1000}"
            prikaz = naziv.upper() if lanac in ("konzum", "studenac") else naziv
            proizvodi.append({"product_id": pid, "barcode": bk, "name": prikaz, "brand": marka, "category": "", "unit": jed, "quantity": kol})
            for si, s in enumerate(st):
                regija = 1.0 + (0.05 if lanac == "konzum" and s["city"] == "Split" else 0.0)
                c = round(cijena * faktor * regija * (1 + pomak) + rnd.choice([0, 0, 0, 0.1, -0.1]) * (lanac in ("konzum", "tommy", "studenac")), 2)
                akcija = ""
                if (pi + len(lanac)) % 9 == 0:
                    akcija = f"{round(c * 0.75, 2):.2f}"
                if lanac == "konzum" and bk == "3850108000021" and si == 1:
                    c = c * 100            # pogreška u jednoj poslovnici
                if lanac == "tommy" and bk == "3850112000010" and si == 0:
                    c = 0.0                # cijena 0,00
                jedinicna = f"{c / osn:.2f}" if osn else ""
                cijene.append({"store_id": s["store_id"], "product_id": pid, "price": f"{c:.2f}", "unit_price": jedinicna,
                               "best_price_30": "", "anchor_price": "", "special_price": akcija, "available": "",
                               "special_sale_type": "akcija" if akcija else "", "anchor_price_date": ""})
        if lanac in ("plodine", "spar"):
            for naziv, marka, kol, jed, osn, vrsta, cijena in BEZ_BARKODA:
                pid = f"{lanac[:1]}-bez-1"
                proizvodi.append({"product_id": pid, "barcode": f"{lanac}:{pid}", "name": naziv, "brand": marka, "category": "", "unit": jed, "quantity": kol})
                for s in st:
                    c = round(cijena * faktor, 2)
                    cijene.append({"store_id": s["store_id"], "product_id": pid, "price": f"{c:.2f}", "unit_price": f"{c / osn:.2f}",
                                   "best_price_30": "", "anchor_price": "", "special_price": "", "available": "", "special_sale_type": "", "anchor_price_date": ""})
        if lanac == "lidl":
            rnd.shuffle(cijene)        # nije složeno po poslovnici
        else:
            cijene.sort(key=lambda r: (r["store_id"], r["product_id"]))   # kao u stvarnoj arhivi
        pisi(zf, f"{lanac}/stores.csv", st, ["store_id", "type", "address", "city", "zipcode"])
        pisi(zf, f"{lanac}/products.csv", proizvodi, ["product_id", "barcode", "name", "brand", "category", "unit", "quantity"])
        pisi(zf, f"{lanac}/prices.csv", cijene, ["store_id", "product_id", "price", "unit_price", "best_price_30", "anchor_price",
                                                  "special_price", "available", "special_sale_type", "anchor_price_date"])
    zf.writestr("archive-info.txt", "primjer")
    zf.close()


def pisi(zf, ime, redovi, stupci):
    b = io.StringIO()
    w = csv.DictWriter(b, fieldnames=stupci, extrasaction="ignore")
    w.writeheader()
    w.writerows(redovi)
    zf.writestr(ime, b.getvalue())


def napravi_koordinate(put: Path):
    with open(put, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "chain_code", "code", "type", "address", "city", "zipcode", "lat", "lon", "phone"])
        n = 0
        for lanac, (broj, _f, _n) in LANCI.items():
            for s in poslovnice(lanac, broj):
                if lanac == "ktc" and s["store_id"].endswith("2"):
                    continue          # jedna poslovnica bez koordinata
                n += 1
                w.writerow([n, lanac, s["store_id"], s["type"], s["address"], s["city"], s["zipcode"], s["lat"], s["lon"], ""])


def napravi_sve(mapa: Path):
    mapa.mkdir(parents=True, exist_ok=True)
    napravi_arhivu(mapa / "2026-11-05.zip", "2026-11-05", bez={"ntl"})
    napravi_arhivu(mapa / "2026-11-04.zip", "2026-11-04", pomak=0.01)
    napravi_koordinate(mapa / "poslovnice.csv")
    return [mapa / "2026-11-05.zip", mapa / "2026-11-04.zip"], mapa / "poslovnice.csv"


if __name__ == "__main__":
    print(napravi_sve(Path(sys.argv[1] if len(sys.argv) > 1 else "primjer")))
