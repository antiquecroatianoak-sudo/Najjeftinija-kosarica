"""
Izvidnica službenih cjenika (samo čitanje, radna grana): python scripts/izvidnica_cjenika.py [GGGG-MM-DD]

Za svaki lanac otvori javnu stranicu s cjenicima koju lanac objavljuje (NN 101/2026, t. II i VII), poštuje robots.txt,
ispiše pronađene poveznice na datoteke (CSV/XML/ZIP/JSON/XLSX) i iz jedne datoteke prve retke, da se vidi stvarni
oblik zapisa. Ništa ne uvozi i ne objavljuje. Ne zaobilazi zaštitu (403, JS izazov, prijava).
"""
import io
import json
import re
import sys
import urllib.parse
import urllib.request
import urllib.robotparser
import zipfile
from datetime import date, datetime
from zoneinfo import ZoneInfo

AGENT = "NajjeftinijaKosarica/1.0 (+https://github.com/antiquecroatianoak-sudo/Najjeftinija-kosarica)"
RE_POVEZNICA = re.compile(r"""(?:href|src|"url"|"URL")\s*[=:]\s*["']([^"']+)["']""", re.I)
RE_DATOTEKA = re.compile(r"\.(csv|xml|zip|json|xlsx?)(?:$|[?#&])", re.I)


def ulazi(d: date) -> dict[str, list[str]]:
    """Javne stranice/kazala cjenika po lancu (adrese kakve lanci objavljuju)."""
    return {
        "konzum": [f"https://www.konzum.hr/cjenici?date={d:%Y-%m-%d}"],
        "lidl": ["https://www.lidl.hr/c/cijene/s10073252"],
        "plodine": ["https://www.plodine.hr/info-o-cijenama"],
        "kaufland": ["https://www.kaufland.hr/akcije-novosti/popis-mpc.html"],
        "spar": [f"https://www.spar.hr/datoteke_cjenici/Cjenik{d:%Y%m%d}.json"],
        "ntl": [f"https://ntl.hr/cjenik/?date={d:%Y-%m-%d}"],
        "studenac": [f"https://www.studenac.hr/cjenici/PROIZVODI-{d:%Y-%m-%d}.zip"],
        "tommy": [f"https://spiza.tommy.hr/api/v2/shop/store-prices-tables?date={d:%Y-%m-%d}&page=1&itemsPerPage=200&channelCode=general"],
        "ktc": ["https://www.ktc.hr/cjenici"],
        "eurospin": ["https://www.eurospin.hr/cjenik/"],
        "dm": ["https://content.services.dmtech.com/rootpage-dm-shop-hr-hr/novo/promocije/nove-oznake-cijena-i-vazeci-cjenik-u-dm-u-2906632?mrclx=false"],
        "ribola": [f"https://ribola.hr/ribola-cjenici/?date={d:%d.%m.%Y}"],
        "boso": ["https://www.boso.hr/cjenik/"],
        "trgocentar": ["https://trgocentar.com/Trgovine-cjenik/"],
        "trgovina-krk": ["https://trgovina-krk.hr/objava-cjenika/"],
        "vrutak": ["https://www.vrutak.hr/cjenik-svih-artikala"],
        "zabac": ["https://zabacfoodoutlet.hr/cjenik/"],
        "lorenco": ["https://lorenco.hr/dnevne-cijene/"],
        "roto": ["https://www.rotodinamic.hr/cjenici/"],
        "stridon": ["https://stridon.hr/hr/supermarketi"],
        "branka": ["https://www.branka.hr/cjenik"],
        "bure": ["https://www.bure.hr/cjenici-arhiva"],
        "djelo_vodice": ["https://dv10.djelo-vodice.hr/"],
        "dukat": ["https://dukat.hr/diskonti"],
        "jadranka_trgovina": ["https://jadranka-trgovina.com/cjenici/"],
        "brodokomerc": ["http://www.brodokomerc.hr/cijene"],
    }


def dohvati(url: str, najvise: int = 6_000_000) -> tuple[int, str, bytes]:
    zahtjev = urllib.request.Request(url, headers={"User-Agent": AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(zahtjev, timeout=40) as r:
        return r.status, r.headers.get("Content-Type", ""), r.read(najvise)


def dopusteno(url: str, roboti: dict) -> bool:
    p = urllib.parse.urlsplit(url)
    korijen = f"{p.scheme}://{p.netloc}"
    if korijen not in roboti:
        rp = urllib.robotparser.RobotFileParser()
        try:
            _, _, sadrzaj = dohvati(korijen + "/robots.txt", 500_000)
            rp.parse(sadrzaj.decode("utf-8", "replace").splitlines())
        except Exception:  # noqa: BLE001 - bez robots.txt vrijedi dopušteno
            rp.parse([])
        roboti[korijen] = rp
    return roboti[korijen].can_fetch(AGENT, url)


def pregled(sadrzaj: bytes, url: str) -> str:
    if sadrzaj[:2] == b"PK":
        try:
            zf = zipfile.ZipFile(io.BytesIO(sadrzaj))
        except zipfile.BadZipFile:
            return "ZIP (nepotpun u uzorku)"
        imena = zf.namelist()
        prvi = zf.read(imena[0])[:1200] if imena else b""
        return f"ZIP {len(imena)} datoteka, npr. {imena[:3]}\n      prvi: {prvi.decode('utf-8', 'replace')[:900]!r}"
    for kod in ("utf-8-sig", "cp1250"):
        try:
            tekst = sadrzaj.decode(kod)
            break
        except UnicodeDecodeError:
            tekst = None
    tekst = tekst if tekst is not None else sadrzaj.decode("latin-1")
    return repr(tekst[:900])


def main():
    d = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else datetime.now(ZoneInfo("Europe/Zagreb")).date()
    roboti: dict = {}
    for lanac, adrese in ulazi(d).items():
        for adresa in adrese:
            print(f"== {lanac}: {adresa}", flush=True)
            if not dopusteno(adresa, roboti):
                print("   robots.txt ne dopušta; preskočeno")
                continue
            try:
                status, vrsta, sadrzaj = dohvati(adresa)
            except Exception as e:  # noqa: BLE001
                print(f"   GREŠKA: {str(e)[:200]}")
                continue
            print(f"   HTTP {status} {vrsta} {len(sadrzaj)} B")
            if RE_DATOTEKA.search(urllib.parse.urlsplit(adresa).path) and not vrsta.startswith("text/html"):
                print("   uzorak: " + pregled(sadrzaj, adresa))
                continue
            tekst = sadrzaj.decode("utf-8", "replace")
            poveznice = []
            for m in RE_POVEZNICA.finditer(tekst):
                href = m.group(1).replace("\\/", "/")
                if RE_DATOTEKA.search(href) or "download" in href.lower() or "csv" in href.lower():
                    poveznice.append(urllib.parse.urljoin(adresa, href))
            poveznice = list(dict.fromkeys(poveznice))
            print(f"   poveznica na datoteke: {len(poveznice)}; prve: {poveznice[:4]}; zadnja: {poveznice[-1:] }")
            if not poveznice:
                print("   početak stranice: " + repr(re.sub(r"\s+", " ", tekst)[:600]))
                continue
            uzorak = next((p for p in poveznice if re.search(r"\.(csv|xml|zip)", p, re.I)), poveznice[0])
            if not dopusteno(uzorak, roboti):
                print(f"   uzorak {uzorak}: robots.txt ne dopušta")
                continue
            try:
                status, vrsta, sadrzaj = dohvati(uzorak)
                print(f"   uzorak {uzorak}: HTTP {status} {vrsta} {len(sadrzaj)} B\n   " + pregled(sadrzaj, uzorak))
            except Exception as e:  # noqa: BLE001
                print(f"   uzorak {uzorak}: GREŠKA {str(e)[:200]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
