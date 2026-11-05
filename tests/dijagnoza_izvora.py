"""PRIVREMENO: koje strategije pronalaze adrese koje Nominatim nije našao. Samo čita i ispisuje."""
import csv, io, json, sys, time, urllib.parse, urllib.request, zipfile, random, re
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "uvoz"))
from lokacije import kljuc, ocisti_adresu, prihvati  # noqa: E402

UA = "NajjeftinijaKosarica-dijagnoza/1.0 (+https://github.com/antiquecroatianoak-sudo/Najjeftinija-kosarica)"
D = Path(sys.argv[1]); D.mkdir(parents=True, exist_ok=True)
BAZA = "https://antiquecroatianoak-sudo.github.io/Najjeftinija-kosarica/data/hr/"


def get(url, timeout=120):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=timeout).read()


lok = json.loads(get(BAZA + "lokacije.json"))["a"]
neusp = {k for k, v in lok.items() if v[0] is None}
print("spremljeno", len(lok), "neuspjelih", len(neusp), Counter(v[2] for v in lok.values()))

popis = json.loads(get("https://api.cijene.dev/v0/list", 60))
arhive = sorted([a for a in popis.get("archives", popis if isinstance(popis, list) else []) if a.get("url")],
                key=lambda a: a["date"], reverse=True)
put = D / "a.zip"
urllib.request.urlretrieve(arhive[0]["url"], put)
zf = zipfile.ZipFile(put)
redovi = []
for ime in zf.namelist():
    if ime.endswith("stores.csv"):
        lanac = ime.rstrip("/").split("/")[-2].lower()
        for r in csv.DictReader(io.TextIOWrapper(zf.open(ime), encoding="utf-8-sig")):
            if kljuc(r.get("address", ""), r.get("city", "")) in neusp:
                redovi.append((lanac, r))
print("neuspjelih u današnjoj arhivi:", len(redovi), Counter(l for l, _ in redovi))
print("\nPRIMJERI NEUSPJELIH ADRESA:")
random.seed(3)
for l, r in random.sample(redovi, min(60, len(redovi))):
    print(f"  {l:12} {r.get('address')!r:45} {r.get('city')!r:22} {r.get('zipcode')!r}")

zadnji = [0.0]


def nom(p):
    cekaj = 1.1 - (time.monotonic() - zadnji[0])
    if cekaj > 0: time.sleep(cekaj)
    zadnji[0] = time.monotonic()
    p = {**p, "format": "jsonv2", "addressdetails": "1", "limit": "3", "countrycodes": "hr"}
    try:
        return json.loads(get("https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({k: v for k, v in p.items() if v}), 30))
    except Exception as e:
        print("   GREŠKA", e); return []


def bez_broja(a):
    a = ocisti_adresu(a).split(",")[0]
    return re.sub(r"\s+(\d+\s*[a-zA-Z]?(\s*[-/]\s*\d+[a-zA-Z]?)?|bb|b\.b\.)\s*$", "", a, flags=re.I).strip()


def strategije(r):
    a, g = ocisti_adresu(r.get("address", "")), (r.get("city") or "").strip()
    dijelovi = [x.strip() for x in a.split(",") if x.strip()]
    s = bez_broja(a)
    yield "ulica_bez_broja_strukt", {"street": s, "city": g}
    yield "ulica_bez_broja_slob", {"q": f"{s}, {g}"}
    if len(dijelovi) > 1:
        yield "naselje_iz_adrese", {"street": dijelovi[0], "city": dijelovi[-1]}
    yield "lanac_u_gradu", {"q": f"{IME.get(r['_l'], r['_l'])}, {g}"}


IME = {"ntl": "NTL", "gavranovic": "Gavranović", "ribola": "Ribola", "stridon": "Stridon", "boso": "Boso",
       "roto": "Roto", "trgovina-krk": "Trgovina Krk", "tommy": "Tommy", "plodine": "Plodine"}
print("\nSTRATEGIJE na uzorku od 45:")
uspjeh = Counter()
for l, r in random.sample(redovi, min(45, len(redovi))):
    r = dict(r, _l=l)
    print(f"- {l} {r.get('address')!r} {r.get('city')!r}")
    for ime, p in strategije(r):
        rez = nom(p)
        dobri = [(prihvati(x), x.get('category'), x.get('type'), x.get('display_name', '')[:70]) for x in rez]
        ok = [d for d in dobri if d[0]]
        if ime == "lanac_u_gradu":
            ok = [d for d in dobri if d[1] == "shop"]
        print(f"    {ime:24} {'DA' if ok else 'ne'} {ok[:1] or dobri[:1]}")
        if ok: uspjeh[ime] += 1
print("\nUSPJEH po strategiji:", uspjeh)
