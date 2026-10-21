"""Službeni cjenici bez mreže (zamijenjeno preuzimanje): python3 tests/sluzbeni.py"""
import importlib.util
import json
import sys
import tempfile
import zipfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import azuriraj_cijene as a  # noqa: E402
import sluzbeni_cjenici as sl  # noqa: E402

D = date(2026, 10, 21)
# Stvarni oblici zaglavlja (izvidnica 21.10.2026.): Krk/NTL CSV sa ";" i "Naziv posebnog oblika prodaje", Vrutak XML.
KRK = ('"Naziv proizvoda";"Šifra proizvoda";"Marka proizvoda";"Neto količina";"Jedinica mjere";"Maloprodajna cijena";'
       '"Naziv posebnog oblika prodaje";"Cijena za jedinicu mjere";"Sidrena cijena";"Barkod";"Kategorija proizvoda";"Dostupnost"\r\n'
       '"KRUMPIR ZA GASTRO 1 kg";"7001";"";"1";"kg";",10";"";",10";"";"2001";"Hrana";"dostupno"\r\n'
       '"AJVAR DOMAĆI  BLAGI 360 g ZORELA";"049803";"ZORELA";",36";"kg";"2,79";"TNC";"7,75";"4,09";"3856003936795";"Hrana";"dostupno"\r\n'
       '"NEDOSTUPNO 1 kg";"7002";"";"1";"kg";"1,00";"";"1,00";"";"2002";"Hrana";"nedostupno"\r\n').encode("utf-8")
KRK2 = KRK.replace(b",10\";\"\";\",10", b"1,09\";\"\";\"1,09")
WEB = {
    "https://trgovina-krk.hr/objava-cjenika/": (
        '<a href="/csv/Supermarket_Sv. Bernardina 6c_KRK_1_21102026_04_30_19.csv">a</a>'
        '<a href="/csv/Supermarket_Sv. Bernardina 6c_KRK_1_20102026_04_30_19.csv">stari</a>'
        '<a href="/csv/Supermarket_Vrbnik 2_VRBNIK_2_21102026_04_31_00.csv">b</a>').encode(),
    "https://trgovina-krk.hr/csv/Supermarket_Sv.%20Bernardina%206c_KRK_1_21102026_04_30_19.csv": KRK,
    "https://trgovina-krk.hr/csv/Supermarket_Vrbnik%202_VRBNIK_2_21102026_04_31_00.csv": KRK2,
}
dohvaceno = []


def dohvati(url):
    url = sl.siguran_url(url)
    dohvaceno.append(url)
    if url not in WEB:
        raise OSError(f"HTTP Error 404: {url}")
    return WEB[url]


sl.dohvati = dohvati
rez = sl.preuzmi_lanac("trgovina-krk", D)
assert rez["uspjeh"] and len(rez["koristene"]) == 2, rez
assert not any("20102026" in u for u in dohvaceno), "only today's files are downloaded"
krk = next(x for x in rez["koristene"] if "Bernardina" in x["url"])
assert krk["poslovnica"] == "Supermarket_Sv. Bernardina 6c_KRK_1" and krk["zapisi"][0]["_redak"] == 2
assert krk["nepoznati"] == ["Sidrena cijena", "Kategorija proizvoda"]

with tempfile.TemporaryDirectory() as tmp:
    cdev = Path(tmp) / "c.zip"
    with zipfile.ZipFile(cdev, "w") as zf:  # arhiva cijene.dev s lancem koji nema službenog čitača
        zf.writestr("nepoznat/products.csv", "product_id,barcode,name,brand,quantity,unit\n1,,Mlijeko 1 l,,1,l\n")
        zf.writestr("nepoznat/prices.csv", "store_id,product_id,price,unit_price,special_price\ns1,1,1.09,1.09,\n")
        zf.writestr("trgovina-krk/products.csv", "product_id,barcode,name,brand,quantity,unit\n9,,Staro,,1,kg\n")
        zf.writestr("trgovina-krk/prices.csv", "store_id,product_id,price,unit_price,special_price\ns9,9,9.99,9.99,\n")
    sast = Path(tmp) / "s.zip"
    izvj = a.sastavi_arhivu(cdev, D, sast, lanci_sluzbeno=["trgovina-krk"])
    assert izvj["trgovina-krk"]["izvor"] == "službeni cjenici" and izvj["trgovina-krk"]["poslovnica"] == 2
    assert izvj["nepoznat"]["izvor"] == "cijene.dev" and izvj["konzum"]["izvor"] == "nema podataka", izvj
    stat = {}
    r = a.obradi_sve(sast, {}, stat)
    po = {p[0]: p for p in r["proizvodi"]}
    assert "Staro" not in po, "official data replaces the secondary archive for that chain"
    g = po["KRUMPIR ZA GASTRO 1 kg"]
    pon = g[6][0]
    assert g[5][1] == 0.1 and r["izvori"][r["poslovnice"][pon[0]][4]][0].endswith("Bernardina%206c_KRK_1_21102026_04_30_19.csv")
    assert pon[4] == 2 and pon[1:4] == [2, 1.09, 0], "trace: official file and row 2; other store 1,09 € is the range only"
    ajvar = po["AJVAR DOMAĆI  BLAGI 360 g ZORELA"]
    assert ajvar[6][0][3] == 1 and ajvar[6][0][5] == "TNC", "promotion name from the official list"
    assert "NEDOSTUPNO 1 kg" not in po, "unavailable rows are not offered"
    pok = a.pokrivenost(r, stat, "2026-10-21", izvj)
    assert pok["lanci"]["Trgovina Krk"]["provjereno_prema_sluzbenom_izvoru"] == 2
    assert pok["lanci"]["Nepoznat"]["provjereno_prema_sluzbenom_izvoru"] == 0 and pok["lanci"]["Nepoznat"]["izvor"] == "cijene.dev"
    assert "konzum" in pok["bez_podataka"]
    mapa = Path(tmp) / "posl"
    a.zapisi_poslovnice(mapa, r, "2026-10-21")
    ber = json.loads((mapa / f"{pon[0]}.json").read_text())
    assert ber["izvor"][0].endswith("21102026_04_30_19.csv") and ber["r"] == [2, 3], ber
print("OFFICIAL PASS: today's files only, row numbers, unknown columns kept, unavailable rows dropped, official data "
      "replaces cijene.dev per chain, fallback kept and unverified, chain without data reported, trace file+row on the "
      "chain price and in the store file, promotion name (NTL/Krk 'TNC'), coverage counts verified offers")
