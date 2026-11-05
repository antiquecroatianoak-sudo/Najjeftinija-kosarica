"""PRIVREMENO: dijagnoza izvora za popravak koordinata i Studenca. Samo čita i ispisuje."""
import csv, io, json, sys, time, urllib.parse, urllib.request, zipfile
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

UA = "NajjeftinijaKosarica-dijagnoza/1.0 (+https://github.com/antiquecroatianoak-sudo/Najjeftinija-kosarica)"
D = Path(sys.argv[1]); D.mkdir(parents=True, exist_ok=True)


def get(url, timeout=120):
    r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=timeout)
    return r.status, r.headers, r.read()


def sekcija(t):
    print("\n==========", t, flush=True)


sekcija("STUDENAC službeni ZIP")
for d in (date.today(), date.today() - timedelta(days=1)):
    url = f"https://www.studenac.hr/cjenici/PROIZVODI-{d:%Y-%m-%d}.zip"
    try:
        st, h, b = get(url, 180)
        print(url, st, len(b), h.get("Content-Type"))
        zf = zipfile.ZipFile(io.BytesIO(b))
        imena = zf.namelist()
        print("članova:", len(imena))
        for i in imena[:8]: print("  ", i)
        print("  ...", imena[-3:])
        prvi = zf.read(imena[0])
        print("POČETAK PRVOG:", prvi[:2500].decode("utf-8", "replace"))
        # broj zapisa u prvom
        print("broj '<Proizvod' u prvom:", prvi.count(b"<Proizvod"), "veličina", len(prvi))
        break
    except Exception as e:
        print(url, "GREŠKA", repr(e)[:300])
for url in ("https://www.studenac.hr/cjenici", "https://www.studenac.hr/robots.txt"):
    try:
        st, h, b = get(url, 60)
        t = b.decode("utf-8", "replace")
        print(url, st, len(b))
        import re
        print("  poveznice zip/xml:", re.findall(r'href="([^"]+\.(?:zip|xml|csv))"', t)[:10])
        if "robots" in url: print(t[:800])
    except Exception as e:
        print(url, "GREŠKA", repr(e)[:300])

sekcija("ARHIVE cijene.dev: Studenac i poslovnice bez koordinata")
popis = json.loads(get("https://api.cijene.dev/v0/list", 60)[2])
arhive = sorted([a for a in popis.get("archives", popis if isinstance(popis, list) else []) if a.get("url")],
                key=lambda a: a["date"], reverse=True)
print("zadnje arhive:", [(a["date"], a.get("size")) for a in arhive[:6]])
st, h, enr = get("https://raw.githubusercontent.com/senko/cijene-api/main/enrichment/stores.csv")
enr = list(csv.DictReader(io.StringIO(enr.decode())))
s_koord = {(r["chain_code"].lower(), r["code"].strip().lower().lstrip("0")) for r in enr if r["lat"]}
for a in arhive[:3]:
    put = D / f"{a['date']}.zip"
    t0 = time.time()
    urllib.request.urlretrieve(a["url"], put)
    zf = zipfile.ZipFile(put)
    print(f"\n{a['date']}: {put.stat().st_size // 1_000_000} MB ({time.time() - t0:.0f} s)")
    for ime in sorted(zf.namelist()):
        if not ime.endswith("stores.csv"):
            continue
        lanac = ime.rstrip("/").split("/")[-2].lower()
        redovi = list(csv.DictReader(io.TextIOWrapper(zf.open(ime), encoding="utf-8-sig")))
        bez = [r for r in redovi if (lanac, (r.get("store_id") or "").strip().lower().lstrip("0")) not in s_koord]
        print(f"  {lanac:20} poslovnica {len(redovi):4}  bez koordinata po šifri {len(bez):4}  stupci {list(redovi[0].keys()) if redovi else []}")
        if a is arhive[0] and lanac in ("ntl", "studenac", "gavranovic", "ribola"):
            for r in redovi[:3]: print("     ", dict(r))
    if a is not arhive[0]:
        put.unlink()

sekcija("NOMINATIM (strukturirano, 1/s)")
zf = zipfile.ZipFile(D / f"{arhive[0]['date']}.zip")
uzorci = []
for ime in zf.namelist():
    if ime.endswith("stores.csv"):
        lanac = ime.rstrip("/").split("/")[-2].lower()
        if lanac in ("ntl", "gavranovic", "ribola", "stridon", "studenac"):
            for r in list(csv.DictReader(io.TextIOWrapper(zf.open(ime), encoding="utf-8-sig")))[:4]:
                uzorci.append((lanac, r))
for lanac, r in uzorci:
    q = {"street": r.get("address", ""), "city": r.get("city", ""), "postalcode": r.get("zipcode", ""),
         "country": "hr", "format": "jsonv2", "addressdetails": "1", "limit": "1"}
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({k: v for k, v in q.items() if v})
    try:
        rez = json.loads(get(url, 30)[2])
        if rez:
            x = rez[0]
            print(f"  {lanac:10} {r.get('address')!r:35} {r.get('city')!r:18} -> rank {x.get('place_rank')} {x.get('category')}/{x.get('type')} {x['lat'][:9]},{x['lon'][:9]} | {x.get('display_name','')[:90]}")
        else:
            print(f"  {lanac:10} {r.get('address')!r:35} {r.get('city')!r:18} -> NEMA")
    except Exception as e:
        print(f"  {lanac:10} GREŠKA {repr(e)[:200]}")
    time.sleep(1.1)
print("\nGOTOVO")
