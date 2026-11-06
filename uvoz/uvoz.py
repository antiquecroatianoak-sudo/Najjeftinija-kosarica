"""Dnevni uvoz cijena za aplikaciju Najjeftinija košarica (Hrvatska).

Izvor: dnevne ZIP arhive javnih cjenika svih lanaca (obveza po NN 75/2025) koje projekt cijene.dev skuplja
sa službenih stranica trgovina. Arhiva ima mapu po lancu sa stores.csv, products.csv i prices.csv.

Što radi:
  1. preuzme najnoviju arhivu (s ponovnim pokušajima); lanac koji danas nedostaje ili je bitno slabiji od
     jučerašnjeg uzme se iz starije arhive (do 3 dana) i označi kao "stari podaci";
  2. odbaci loše cijene (0, negativne, apsurdne, >4× odstupanje od uobičajene);
  3. spoji isti proizvod iz različitih lanaca (barkod, inače marka + naziv + količina);
  4. razvrsta proizvode u grupe i podgrupe (grupe.json);
  5. zapiše podatke za aplikaciju: proizvode s cijenama po lancu, poslovnice s koordinatama i cijene
     svake stvarne poslovnice (datoteke po sadržaju, iste se dijele), te status podataka.

Pokretanje:  python uvoz/uvoz.py --izlaz app/data/hr
Lokalni test bez interneta:  python uvoz/uvoz.py --arhiva primjer.zip --izlaz /tmp/x --bez-dopune
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import statistics
import sys
import time
import traceback
import urllib.request
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kolicina import (barkod, broj, iz_polja, iz_teksta, lijep_naziv, naziv_bez_kolicine, norm,  # noqa: E402
                      norm_pojam, odaberi_kolicinu, sadrzi, vrsta_jedinice)
from lokacije import Lokacije  # noqa: E402

csv.field_size_limit(10_000_000)

POPIS_ARHIVA = "https://api.cijene.dev/v0/list"
DOPUNA_PROIZVODA = "https://raw.githubusercontent.com/senko/cijene-api/main/enrichment/products.csv"
DOPUNA_POSLOVNICA = "https://raw.githubusercontent.com/senko/cijene-api/main/enrichment/stores.csv"
KORISNIK = "NajjeftinijaKosarica-uvoz/1.0 (+https://github.com/antiquecroatianoak-sudo/Najjeftinija-kosarica)"

GRUPE = Path(__file__).resolve().parent / "grupe.json"

# Lanci koji se uopće ne uvoze (ne pojavljuju se nigdje u aplikaciji):
#  - metro: veleprodaja (potrebna poslovna kartica);
#  - stridon: odluka vlasnika 6.11.2026. („Delete Stridon”).
PRESKOCI = {"metro", "stridon"}
IMENA = {
    "konzum": "Konzum", "lidl": "Lidl", "kaufland": "Kaufland", "plodine": "Plodine", "tommy": "Tommy",
    "studenac": "Studenac", "spar": "Spar", "interspar": "Interspar", "eurospin": "Eurospin", "ntl": "NTL",
    "ktc": "KTC", "dm": "dm", "zabac": "Žabac", "vrutak": "Vrutak", "ribola": "Ribola", "boso": "Boso",
    "brodokomerc": "Brodokomerc", "lorenco": "Lorenco", "trgovina-krk": "Trgovina Krk", "trgovina_krk": "Trgovina Krk",
    "roto": "Roto", "jadranka_trgovina": "Jadranka", "jadranka": "Jadranka", "gavranovic": "Gavranović",
    "branka": "Branka", "djelo_vodice": "Djelo Vodice", "bure": "Bure", "dukat": "Dukat", "stanic": "Stanić",
    "stridon": "Stridon", "trgocentar": "Trgocentar", "metro": "Metro",
}
# Lanci koji službeno objavljuju cjenik samo za dio poslovnica (provjereno 5.11.2026.: službeni ZIP Studenca
# www.studenac.hr/cjenici/PROIZVODI-<datum>.zip ima 20 datoteka poslovnica, kao i arhiva cijene.dev).
DJELOMICNO_OBJAVLJUJU = {
    "studenac": "Studenac javno objavljuje cjenik samo za {n} poslovnica; za ostale poslovnice službene cijene nisu dostupne.",
}
# Odluka vlasnika 6.11.2026.: lanci s manje od 19 poslovnica ne prikazuju se (broj poslovnica s cijenama u cjeniku).
# Iznimka: dm objavljuje jedan cjenik za sve svoje poslovnice (100+ u Hrvatskoj), pa u podacima ima „1 poslovnicu”.
NAJMANJE_POSLOVNICA = 19
JEDAN_CJENIK_ZA_SVE = {"dm"}
# Glavni lanci: njihov izostanak je upozorenje u izvješću.
GLAVNI = ["konzum", "lidl", "kaufland", "plodine", "tommy", "studenac", "spar", "eurospin", "ntl", "ktc"]

NAJMANJA_CIJENA = 0.02      # EUR; 0,00 i 0,01 su greške u cjeniku
NAJVECA_CIJENA = 3000.0     # EUR; prehrana i kućanstvo
ODSTUPANJE = 4.0            # cijena >4× ili <1/4 uobičajene smatra se pogreškom
SLABIJI_OD = 0.5            # lanac s manje od 50 % jučerašnjih proizvoda smatra se nepotpunim


def log(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------- preuzimanje
def preuzmi(url: str, odrediste: Path | None = None, pokusaja: int = 5, timeout: int = 180) -> bytes | Path:
    """Preuzimanje s ponovnim pokušajima (2, 4, 8, 16 s)."""
    zadnja = None
    for i in range(pokusaja):
        try:
            zahtjev = urllib.request.Request(url, headers={"User-Agent": KORISNIK})
            with urllib.request.urlopen(zahtjev, timeout=timeout) as r:
                if odrediste is None:
                    return r.read()
                with open(odrediste, "wb") as f:
                    while True:
                        dio = r.read(1 << 20)
                        if not dio:
                            break
                        f.write(dio)
                return odrediste
        except Exception as e:  # noqa: BLE001 - svaka mrežna greška je razlog za novi pokušaj
            zadnja = e
            if i < pokusaja - 1:
                cekaj = 2 ** (i + 1)
                log(f"  Preuzimanje nije uspjelo ({e}); novi pokušaj za {cekaj} s")
                time.sleep(cekaj)
    raise RuntimeError(f"Preuzimanje nije uspjelo nakon {pokusaja} pokušaja: {url}: {zadnji_opis(zadnja)}")


def zadnji_opis(e) -> str:
    return f"{type(e).__name__}: {e}" if e else "nepoznato"


def popis_arhiva() -> list[dict]:
    podaci = json.loads(preuzmi(POPIS_ARHIVA))
    arhive = podaci.get("archives", podaci if isinstance(podaci, list) else [])
    arhive = [a for a in arhive if a.get("date") and a.get("url")]
    return sorted(arhive, key=lambda a: a["date"], reverse=True)


# ---------------------------------------------------------------- dopune
def citaj_dopunu_proizvoda(tekst: str) -> dict[str, dict]:
    out = {}
    for red in csv.DictReader(io.StringIO(tekst)):
        b = barkod(red.get("barcode"))
        if not b:
            continue
        kol = iz_polja(red.get("quantity"), red.get("unit"))
        out[b] = {"naziv": (red.get("name") or "").strip(), "marka": (red.get("brand") or "").strip(), "kol": kol}
    return out


def citaj_dopunu_poslovnica(tekst: str) -> dict[tuple[str, str], tuple[float, float]]:
    out = {}
    for red in csv.DictReader(io.StringIO(tekst)):
        lat, lon = broj(red.get("lat")), broj(red.get("lon"))
        if lat is None or lon is None or not (42.0 < lat < 46.7 and 13.0 < lon < 19.6):
            continue
        lanac = (red.get("chain_code") or "").strip().lower()
        out[(lanac, kljuc_poslovnice(red.get("code")))] = (round(lat, 6), round(lon, 6))
        adresa = norm(f"{red.get('address', '')} {red.get('city', '')}")
        if adresa:
            out.setdefault((lanac, "a:" + adresa), (round(lat, 6), round(lon, 6)))
    return out


def kljuc_poslovnice(kod) -> str:
    s = str(kod or "").strip().lower()
    return s.lstrip("0") or s


# ---------------------------------------------------------------- grupe
class Razvrstavanje:
    """Razvrstavanje proizvoda u grupe po nazivu – jednaka pravila za sve grupe.

    1. Vrsta proizvoda je PRVA riječ vrste u nazivu ("Jogurt s mlijekom" je jogurt, "Mlijeko čokoladno" mlijeko).
    2. Riječ iza "za", "s", "sa", "od", "i", "u", "na", "bez", "okus"... (i iza "&" ili "/") opisuje nešto drugo i ne
       određuje vrstu: "Posuda za mlijeko", "Gel med i mlijeko", "Čaj bez šećera".
    3. Neprehrambena riječ (posuda, gel za tuširanje, SPF, šampon...) isključuje sve prehrambene grupe, pa kozmetika ili
       posuđe nikad ne postanu mlijeko, med ili kruh (grupe s "hrana": false ostaju dopuštene).
    4. Riječi iz "marke" vrijede tek kad u nazivu nema riječi vrste ("Milka čokolada" je čokolada, "Milka Oreo" slatkiš).
    5. "isk" isključuje grupu, "pocetak" traži riječ na početku naziva; jednak položaj odlučuje redoslijed u grupe.json.
    """

    OVISNE = {"za", "s", "sa", "od", "i", "u", "na", "uz", "bez", "okus", "okusom", "aroma", "aromom", "punjen", "punjeni",
              "punjena", "punjene", "punjenjem", "nadjev", "nadjevom", "preljev", "preljevom", "with", "ili"}

    def __init__(self, put: Path = GRUPE):
        podaci = json.loads(put.read_text(encoding="utf-8"))
        self.grupe = podaci["grupe"]
        self.neprehrambeno = [norm_pojam(t) for t in podaci.get("neprehrambeno", [])]
        self.pravila = []
        for gi, g in enumerate(self.grupe):
            pod = [(pi, [norm_pojam(t) for t in p.get("uk", [])]) for pi, p in enumerate(g.get("pod", []))]
            self.pravila.append((gi, self._uzorak([norm_pojam(t) for t in g["uk"]]),
                                 [norm_pojam(t) for t in g.get("isk", [])], pod, bool(g.get("pocetak")),
                                 g.get("hrana", True), self._uzorak([norm_pojam(t) for t in g.get("marke", [])])))

    def razvrstaj(self, naziv: str, marka: str = "") -> tuple[int, int]:
        """Prvo po nazivu; marka se dodaje samo ako sam naziv ne odgovara nijednoj grupi."""
        g = self._razvrstaj(naziv)
        if g[0] < 0 and marka and norm(marka) not in norm(naziv):
            g = self._razvrstaj(f"{naziv} {marka}")
        return g

    @staticmethod
    def _stog(naziv: str) -> str:
        # "med&mlijeko", "pilet./mlijeko" -> "med i mlijeko"; "1/2" ostaje
        n = re.sub(r"(?<=[^\W\d_])\.?\s*[&/]\s*(?=[^\W\d_])", " i ", naziv or "")
        n = re.sub(r"(?<=[^\W\d_])[\u2019'`]s\b", "s", n)          # "Frank's" -> "Franks", ne "Frank s"
        return " " + norm(n) + " "

    @staticmethod
    def _uzorak(termini: list[str]):
        termini = [t for t in termini if t]
        if not termini:
            return None
        # (?= ...) dopušta preklapanje; najdulji termin prvi
        return re.compile(r"(?= (?:" + "|".join(re.escape(t) for t in sorted(termini, key=len, reverse=True)) + "))")

    def _polozaj(self, stog: str, uzorak, pocetak: bool) -> int | None:
        """Indeks riječi prvog valjanog pogotka (ne iza ovisne riječi) ili None."""
        if uzorak is None:
            return None
        for m in uzorak.finditer(stog):
            k = m.start()
            rijec = stog.count(" ", 1, k + 1) if k else 0       # 0 = prva riječ
            if pocetak and rijec:
                return None
            prije = stog[:k].rsplit(" ", 1)[-1] if k else ""
            # ovisna riječ na samom početku naziva je kratica ("S.kruh", "I.krafna"), ne "s"/"i"
            if prije not in self.OVISNE or rijec == 1:
                return rijec
        return None

    def _razvrstaj(self, naziv: str) -> tuple[int, int]:
        stog = self._stog(naziv)
        neprehrambeno = any(sadrzi(stog, t) for t in self.neprehrambeno)
        najbolje = None      # (prioritet, položaj, redoslijed)
        for gi, uk, isk, pod, pocetak, hrana, marke in self.pravila:
            if (neprehrambeno and hrana) or any(sadrzi(stog, t) for t in isk):
                continue
            p = self._polozaj(stog, uk, pocetak)
            kljuc = (0, p, gi) if p is not None else None
            if kljuc is None and marke is not None:
                pm = self._polozaj(stog, marke, False)
                kljuc = (1, pm, gi) if pm is not None else None
            if kljuc and (najbolje is None or kljuc < najbolje):
                najbolje = kljuc
        if najbolje is None:
            return -1, -1
        gi = najbolje[2]
        for pi, puk in self.pravila[gi][3]:
            if any(sadrzi(stog, t) for t in puk):
                return gi, pi
        return gi, -1

    def za_aplikaciju(self) -> list[dict]:
        out = []
        for g in self.grupe:
            out.append({"id": g["id"], "naziv": g["naziv"], "ikona": g.get("ikona", ""), "zadano": g["zadano"],
                        "rijeci": g.get("rijeci", []),
                        "pod": [{"id": p["id"], "naziv": p["naziv"], "rijeci": p.get("rijeci", [])} for p in g.get("pod", [])]})
        return out


# ---------------------------------------------------------------- čitanje arhive
def lanci_u_arhivi(zf: zipfile.ZipFile) -> dict[str, str]:
    """lanac -> prefiks mape u arhivi (podržava i arhivu s mapom datuma na vrhu)."""
    out = {}
    for ime in zf.namelist():
        if ime.endswith("/prices.csv"):
            prefiks = ime[: -len("prices.csv")]
            lanac = prefiks.rstrip("/").split("/")[-1].strip().lower()
            if lanac and lanac not in PRESKOCI:
                out[lanac] = prefiks
    return out


def citaj_csv(zf: zipfile.ZipFile, ime: str):
    with zf.open(ime) as f:
        tekst = io.TextIOWrapper(f, encoding="utf-8-sig", errors="replace", newline="")
        yield from csv.DictReader(tekst)


def podlanac(lanac: str, poslovnica: dict) -> str:
    """Spar i Interspar dijele cjenik; Interspar su hipermarketi (pretpostavka iz vrste poslovnice)."""
    if lanac == "spar":
        vrsta = norm(f"{poslovnica.get('type', '')} {poslovnica.get('address', '')}")
        if "interspar" in vrsta or "hiper" in vrsta:
            return "interspar"
    return lanac


def cent(v) -> int | None:
    b = broj(v)
    if b is None or not (NAJMANJA_CIJENA <= b <= NAJVECA_CIJENA):
        return None
    return int(round(b * 100))


class Lanac:
    """Podaci jednog izvornog lanca iz jedne arhive (prvi prolaz: uobičajene cijene)."""

    def __init__(self, zf: zipfile.ZipFile, ime_zip: str, lanac: str, prefiks: str, datum: str):
        self.zf, self.ime_zip, self.lanac, self.prefiks, self.datum = zf, ime_zip, lanac, prefiks, datum
        self.poslovnice: dict[str, dict] = {}
        self.proizvodi: dict[str, dict] = {}
        self.preskoceno = Counter()
        # (podlanac, pid) -> brojači cijena
        self.efektivne: dict[tuple[str, str], Counter] = defaultdict(Counter)
        self.redovne: dict[tuple[str, str], Counter] = defaultdict(Counter)
        self.naj30: dict[tuple[str, str], Counter] = defaultdict(Counter)
        self.sidrene: dict[tuple[str, str], Counter] = defaultdict(Counter)
        self.omjeri: dict[str, list[float]] = defaultdict(list)   # pid -> cijena / jedinična cijena
        self.po_pid = Counter()                                    # pid -> broj poslovnica s cijenom
        self.trgovine: dict[str, set] = defaultdict(set)           # podlanac -> poslovnice s barem jednom cijenom

    def ucitaj(self):
        p = self.prefiks
        imena = set(self.zf.namelist())
        if p + "stores.csv" in imena:
            for r in citaj_csv(self.zf, p + "stores.csv"):
                sid = (r.get("store_id") or "").strip()
                if sid:
                    self.poslovnice[sid] = r
        if p + "products.csv" in imena:
            for r in citaj_csv(self.zf, p + "products.csv"):
                pid = (r.get("product_id") or "").strip()
                if pid and (r.get("name") or "").strip():
                    self.proizvodi[pid] = r
        for sid, pid, eff, red, up, naj30, sidrena in self._cijene():
            pl = podlanac(self.lanac, self.poslovnice.get(sid, {}))
            self.trgovine[pl].add(sid)
            self.efektivne[(pl, pid)][eff] += 1
            self.redovne[(pl, pid)][red] += 1
            if naj30:
                self.naj30[(pl, pid)][naj30] += 1
            if sidrena:
                self.sidrene[(pl, pid)][sidrena] += 1
            self.po_pid[pid] += 1
            if up and len(self.omjeri[pid]) < 25:
                self.omjeri[pid].append(red / up)
        return self

    def _cijene(self):
        """(poslovnica, proizvod, efektivna cijena, redovna cijena, jedinična cijena, najniža u 30 dana, sidrena) – u centima."""
        for r in citaj_csv(self.zf, self.prefiks + "prices.csv"):
            sid = (r.get("store_id") or "").strip()
            pid = (r.get("product_id") or "").strip()
            if not sid or not pid or pid not in self.proizvodi:
                self.preskoceno["nepoznat proizvod ili poslovnica"] += 1
                continue
            if (r.get("available") or "").strip() == "0":
                self.preskoceno["nije dostupno"] += 1
                continue
            redovna = cent(r.get("price"))
            akcija = cent(r.get("special_price"))
            if redovna is None and akcija is None:
                self.preskoceno["neispravna cijena"] += 1
                continue
            if redovna is None:
                redovna = akcija
            eff = akcija if akcija is not None and akcija < redovna else redovna
            up = broj(r.get("unit_price"))
            up = int(round(up * 100)) if up and up > 0 else None
            # NN 75/2025: najniža cijena u zadnjih 30 dana i sidrena cijena (2.5.2025.) – samo ako su objavljene
            naj30 = cent(r.get("best_price_30"))
            sidrena = cent(r.get("anchor_price"))
            yield sid, pid, eff, redovna, up, naj30, sidrena

    def cijene_po_poslovnici(self, u_memoriji: bool = False):
        """Drugi prolaz: za svaku poslovnicu rječnik pid -> efektivna cijena.

        Cjenici su složeni po poslovnici, pa se čita poslovnica po poslovnica (malo memorije). Ako nisu,
        baca NijeSlozeno, a pozivatelj ponovi čitanje s u_memoriji=True.
        """
        if u_memoriji:
            sve = defaultdict(dict)
            for sid, pid, eff, *_ in self._cijene():
                sve[sid][pid] = min(eff, sve[sid].get(pid, eff))
            yield from sve.items()
            return
        trenutna, cijene, gotove = None, {}, set()
        for sid, pid, eff, *_ in self._cijene():
            if sid != trenutna:
                if trenutna is not None:
                    gotove.add(trenutna)
                    yield trenutna, cijene
                if sid in gotove:
                    raise NijeSlozeno(self.lanac)
                trenutna, cijene = sid, {}
            cijene[pid] = min(eff, cijene.get(pid, eff))
        if trenutna is not None:
            yield trenutna, cijene


class NijeSlozeno(Exception):
    pass


def uobicajena(brojac: Counter) -> int:
    """Najčešća cijena; kod izjednačenja niža."""
    najvise = max(brojac.values())
    return min(c for c, n in brojac.items() if n == najvise)


# ---------------------------------------------------------------- glavna obrada
class Uvoz:
    def __init__(self, dopuna_proizvoda: dict, dopuna_poslovnica: dict, razvrstavanje: Razvrstavanje,
                 najmanje_poslovnica: int = NAJMANJE_POSLOVNICA):
        self.dp, self.dpo, self.raz = dopuna_proizvoda, dopuna_poslovnica, razvrstavanje
        self.najmanje = najmanje_poslovnica
        self.izostavljeni: dict[str, int] = {}
        self.lanci: list[Lanac] = []
        self.status: dict[str, dict] = {}
        self.upozorenja: list[str] = []
        self.lok: Lokacije | None = None

    def dodaj(self, lanac: Lanac, status: str, napomena: str = ""):
        self.lanci.append(lanac)
        podlanci = {pl for pl, _ in lanac.efektivne}
        for pl in podlanci or {lanac.lanac}:
            self.status[pl] = {"status": status, "datum": lanac.datum, "napomena": napomena}

    def izgradi(self, izlaz: Path, datum_arhive: str) -> dict:
        izlaz.mkdir(parents=True, exist_ok=True)
        mapa_s = izlaz / "s"
        mapa_s.mkdir(exist_ok=True)
        self._ukloni_male_lance()

        # 1) globalni proizvodi
        globalni: dict[str, int] = {}
        info: list[dict] = []
        veza: dict[tuple[str, str], int] = {}      # (izvorni lanac, pid) -> globalni indeks
        statistika = Counter()
        for L in self.lanci:
            for pid, r in L.proizvodi.items():
                b = barkod(r.get("barcode"))
                naziv = (r.get("name") or "").strip()
                marka = (r.get("brand") or "").strip()
                polje = iz_polja(r.get("quantity"), r.get("unit"))
                iz_naziva = iz_teksta(naziv)
                dop = self.dp.get(b) if b else None
                vrsta = vrsta_jedinice(r.get("unit")) or (polje[1] if polje else None)
                omjeri = L.omjeri.get(pid) or []
                impl = (statistics.median(omjeri), vrsta) if omjeri and vrsta else None
                kol, izvor = odaberi_kolicinu(polje, iz_naziva, dop["kol"] if dop else None, impl)
                statistika["količina: " + izvor] += 1
                if b:
                    kljuc = "b:" + b
                elif kol and marka:
                    kljuc = f"n:{norm(marka)}|{naziv_bez_kolicine(naziv, kol)}|{kol[0]:g}{kol[1]}"
                else:
                    kljuc = f"l:{L.lanac}:{pid}"
                gi = globalni.get(kljuc)
                if gi is None:
                    gi = globalni[kljuc] = len(info)
                    info.append({"b": b or "", "imena": Counter(), "marke": Counter(), "kol": Counter(),
                                 "dop": dop, "kat": Counter()})
                p = info[gi]
                p["imena"][naziv] += L.po_pid.get(pid, 0) + 1
                if marka:
                    p["marke"][marka] += 1
                if kol:
                    p["kol"][kol] += 1
                veza[(L.lanac, pid)] = gi

        # 1b) isti proizvod pod više barkodova (nova ambalaža, uvoznik): ista marka, isti naziv bez količine i ista
        #     količina -> jedan proizvod; svi barkodovi ostaju za skener
        kanonski: dict[str, int] = {}
        spoj: dict[int, int] = {}
        for gi, p in enumerate(info):
            kol = p["kol"].most_common(1)[0][0] if p["kol"] else None
            marka = p["marke"].most_common(1)[0][0] if p["marke"] else ""
            if not kol or not marka:
                continue
            naziv = p["imena"].most_common(1)[0][0]
            k = f"{norm(marka)}|{naziv_bez_kolicine(naziv, kol)}|{kol[0]:g}{kol[1]}"
            if k in kanonski:
                spoj[gi] = kanonski[k]
            else:
                kanonski[k] = gi
        for gi, cilj in spoj.items():
            p, c = info[gi], info[cilj]
            for polje in ("imena", "marke", "kol", "kat"):
                c[polje].update(p[polje])
            c.setdefault("barkodovi", set())
            if p["b"]:
                c["barkodovi"].add(p["b"])
            if c["dop"] is None:
                c["dop"] = p["dop"]
        if spoj:
            veza = {k: spoj.get(gi, gi) for k, gi in veza.items()}
            statistika["spojeno: isti proizvod pod više barkodova"] += len(spoj)

        # 2) uobičajene cijene po lancu (podlancu)
        ponude: dict[str, dict[int, list]] = defaultdict(dict)    # lanac -> gi -> [t, min, max, redovna, broj]
        broj_poslovnica = Counter()
        for L in self.lanci:
            for (pl, pid), brojac in L.efektivne.items():
                gi = veza.get((L.lanac, pid))
                if gi is None:
                    continue
                t = uobicajena(brojac)
                valjane = {c: n for c, n in brojac.items() if t / ODSTUPANJE <= c <= t * ODSTUPANJE}
                odbacene = sum(brojac.values()) - sum(valjane.values())
                if odbacene:
                    L.preskoceno["cijena odstupa od uobičajene"] += odbacene
                red = uobicajena(L.redovne[(pl, pid)])
                b30 = L.naj30.get((pl, pid))
                sid = L.sidrene.get((pl, pid))
                zapis = [t, min(valjane), max(valjane), red if red > t else 0, sum(valjane.values()),
                         uobicajena(b30) if b30 else 0, uobicajena(sid) if sid else 0]
                staro = ponude[pl].get(gi)
                if staro is None or zapis[0] < staro[0]:
                    ponude[pl][gi] = zapis
        # odstupanje među lancima: ako je ≥3 lanca, cijena >4× ili <1/4 medijana je greška
        po_proizvodu = defaultdict(list)
        for pl, pp in ponude.items():
            for gi, z in pp.items():
                po_proizvodu[gi].append(z[0])
        odbaceno_lanci = 0
        for pl, pp in ponude.items():
            for gi in list(pp):
                sve = po_proizvodu[gi]
                if len(sve) >= 3:
                    med = statistics.median(sve)
                    if not (med / ODSTUPANJE <= pp[gi][0] <= med * ODSTUPANJE):
                        del pp[gi]
                        odbaceno_lanci += 1

        # 3) konačni popis proizvoda (samo oni s barem jednom ponudom)
        koristeni = sorted({gi for pp in ponude.values() for gi in pp})
        novi = {gi: i for i, gi in enumerate(koristeni)}
        proizvodi = []
        grupirano = Counter()
        for gi in koristeni:
            p = info[gi]
            dop = p["dop"]
            naziv = dop["naziv"] if dop and dop["naziv"] else p["imena"].most_common(1)[0][0]
            marka = dop["marka"] if dop and dop["marka"] else (p["marke"].most_common(1)[0][0] if p["marke"] else "")
            kol = dop["kol"] if dop and dop["kol"] else (p["kol"].most_common(1)[0][0] if p["kol"] else None)
            # isti barkod s bitno različitim količinama u lancima: količina je nesigurna
            if not (dop and dop["kol"]) and len({k for k in p["kol"]}) > 1:
                vrijednosti = list(p["kol"])
                if any(k[1] != kol[1] or abs(k[0] - kol[0]) / kol[0] > 0.04 for k in vrijednosti):
                    kol = None
                    statistika["količina: neslaganje lanaca"] += 1
            naziv = lijep_naziv(naziv)
            g, pg = self.raz.razvrstaj(naziv, marka)
            grupirano["s grupom" if g >= 0 else "bez grupe"] += 1
            ostali = sorted(p.get("barkodovi", set()) - {p["b"]})
            proizvodi.append([naziv, marka, round(kol[0], 4) if kol else 0, kol[1] if kol else "", g, pg, p["b"] or
                              (ostali.pop(0) if ostali else "")] + ([",".join(ostali)] if ostali else []))

        lanci_izlaz = {}
        for pl in sorted(ponude):
            redovi = sorted((novi[gi], z) for gi, z in ponude[pl].items())
            if not redovi:
                continue
            idx = [r[0] for r in redovi]
            lanci_izlaz[pl] = {
                "i": delta(idx),
                "t": [r[1][0] for r in redovi],
                "n": [r[1][0] - r[1][1] for r in redovi],
                "x": [r[1][2] - r[1][0] for r in redovi],
                "r": [r[1][3] for r in redovi],
                "s": [r[1][4] for r in redovi],
            }
            # najniža cijena u 30 dana ("b") i sidrena cijena ("a"), samo ako ih lanac objavljuje
            if any(r[1][5] for r in redovi):
                lanci_izlaz[pl]["b"] = [r[1][5] for r in redovi]
            if any(r[1][6] for r in redovi):
                lanci_izlaz[pl]["a"] = [r[1][6] for r in redovi]

        s30 = sorted(pl for pl, d in lanci_izlaz.items() if "b" in d)
        log(f"Najniža cijena u 30 dana objavljena za {len(s30)} od {len(lanci_izlaz)} lanaca: {', '.join(s30)}")

        # 4) poslovnice i cijene po poslovnici
        poslovnice = []
        datoteke = set()
        for L in self.lanci:
            try:
                parovi = list(self._poslovnice_lanca(L, False, lanci_izlaz, ponude, veza, novi))
            except NijeSlozeno:
                log(f"  {L.lanac}: cijene nisu složene po poslovnici, čitam sve u memoriju")
                parovi = list(self._poslovnice_lanca(L, True, lanci_izlaz, ponude, veza, novi))
            for pl, sid, r, lokalni in parovi:
                broj_poslovnica[pl] += 1
                sadrzaj = datoteka_poslovnice(lanci_izlaz[pl], lokalni)
                ime = hashlib.sha1(sadrzaj.encode()).hexdigest()[:14]
                if ime not in datoteke:
                    (mapa_s / f"{ime}.json").write_text(sadrzaj, encoding="utf-8")
                    datoteke.add(ime)
                adresa = " ".join((r.get("address") or "").split())
                grad = " ".join((r.get("city") or "").split())
                pbr = (r.get("zipcode") or "").strip()
                koord = self.dpo.get((L.lanac, kljuc_poslovnice(sid))) or self.dpo.get((L.lanac, "a:" + norm(f"{adresa} {grad}")))
                if koord is None and self.lok is not None:
                    koord = self.lok.trazi(adresa, grad, pbr, IMENA.get(L.lanac, L.lanac))
                poslovnice.append([pl, sid, adresa, grad, pbr,
                                   koord[0] if koord else None, koord[1] if koord else None, ime, len(lokalni)])
        for stara in mapa_s.glob("*.json"):
            if stara.stem not in datoteke:
                stara.unlink()
        self._nastavak(izlaz, datum_arhive, proizvodi, lanci_izlaz, ponude, poslovnice, odbaceno_lanci, statistika, grupirano)
        return self.meta

    def _ukloni_male_lance(self):
        """Lanci (podlanci) s manje od NAJMANJE_POSLOVNICA poslovnica ispadaju prije svake obrade:
        njihove cijene ne ulaze u proizvode, usporedbu, poslovnice ni status."""
        broj: dict[str, set] = defaultdict(set)
        for L in self.lanci:
            for pl, sidovi in L.trgovine.items():
                broj[pl] |= {(L.lanac, s) for s in sidovi}
        mali = {pl: len(s) for pl, s in broj.items() if len(s) < self.najmanje and pl not in JEDAN_CJENIK_ZA_SVE}
        for L in self.lanci:
            for rjecnik in (L.efektivne, L.redovne, L.naj30, L.sidrene):
                for kljuc in [k for k in rjecnik if k[0] in mali]:
                    del rjecnik[kljuc]
        for pl in mali:
            self.status.pop(pl, None)
        self.izostavljeni = dict(sorted(mali.items()))
        if mali:
            log(f"Izostavljeni lanci s manje od {self.najmanje} poslovnica: "
                + ", ".join(f"{IMENA.get(pl, pl)} ({n})" for pl, n in sorted(mali.items(), key=lambda x: -x[1])))

    @staticmethod
    def _poslovnice_lanca(L, u_memoriji, lanci_izlaz, ponude, veza, novi):
        """Za svaku poslovnicu: (podlanac, id, redak poslovnice, {indeks proizvoda: cijena u centima})."""
        for sid, cijene in L.cijene_po_poslovnici(u_memoriji):
                r = L.poslovnice.get(sid, {})
                pl = podlanac(L.lanac, r)
                if pl not in lanci_izlaz:
                    continue
                lokalni = {}
                for pid, c in cijene.items():
                    gi = veza.get((L.lanac, pid))
                    if gi is None or gi not in ponude[pl]:
                        continue
                    t = ponude[pl][gi][0]
                    if not (t / ODSTUPANJE <= c <= t * ODSTUPANJE):
                        continue
                    lokalni[novi[gi]] = min(c, lokalni.get(novi[gi], c))
                if lokalni:
                    yield pl, sid, r, lokalni

    def _nastavak(self, izlaz, datum_arhive, proizvodi, lanci_izlaz, ponude, poslovnice, odbaceno_lanci, statistika, grupirano):
        # 5) status, izvješće, zapis
        preskoceno = Counter()
        for L in self.lanci:
            preskoceno.update(L.preskoceno)
        preskoceno["cijena odstupa od drugih lanaca"] += odbaceno_lanci
        lanci_meta = []
        for pl in sorted(set(self.status) | set(lanci_izlaz), key=lambda x: (x not in GLAVNI, IMENA.get(x, x))):
            st = self.status.get(pl, {"status": "ok", "datum": datum_arhive, "napomena": ""})
            pos = [p for p in poslovnice if p[0] == pl]
            if st["status"] == "ok" and not st["napomena"] and pl in DJELOMICNO_OBJAVLJUJU:
                st = dict(st, napomena=DJELOMICNO_OBJAVLJUJU[pl].format(n=len(pos)))
            lanci_meta.append({
                "id": pl, "naziv": IMENA.get(pl, pl.replace("_", " ").title()),
                "status": st["status"] if pl in lanci_izlaz else "nema",
                "datum": st["datum"], "napomena": st["napomena"] if pl in lanci_izlaz else "Nema valjanih cijena u cjeniku.",
                "proizvoda": len(ponude.get(pl, {})), "poslovnica": len(pos),
                "s_koordinatama": sum(1 for p in pos if p[5] is not None),
                "jedan_cjenik": pl in JEDAN_CJENIK_ZA_SVE,      # aplikacija ga uz lokaciju uključuje kao lanac
            })
        for g in GLAVNI:
            if g not in lanci_izlaz:
                self.upozorenja.append(f"Glavni lanac {IMENA.get(g, g)} nema podataka u ovom uvozu.")

        sad = datetime.now(timezone.utc).isoformat(timespec="seconds")
        verzija = hashlib.sha1(json.dumps([datum_arhive, len(proizvodi), [l["proizvoda"] for l in lanci_meta],
                                        [l["s_koordinatama"] for l in lanci_meta]]).encode()).hexdigest()[:10]
        meta = {
            "format": 1, "drzava": "HR", "verzija": verzija, "datum": datum_arhive, "generirano": sad,
            "izvor": "Javni cjenici trgovačkih lanaca (NN 75/2025), preuzeti preko arhive cijene.dev",
            "proizvoda": len(proizvodi), "poslovnica": len(poslovnice), "lanci": lanci_meta,
            "preskoceno": dict(preskoceno), "kolicine": dict(statistika), "grupirano": dict(grupirano),
            "izostavljeni_lanci": {"najmanje_poslovnica": self.najmanje, "lanci": self.izostavljeni},
            "upozorenja": self.upozorenja,
        }
        zapisi_json(izlaz / "proizvodi.json", {"verzija": verzija, "p": proizvodi, "l": lanci_izlaz})
        zapisi_json(izlaz / "poslovnice.json", {"verzija": verzija, "polja": ["lanac", "id", "adresa", "grad", "pbr", "lat", "lon", "datoteka", "proizvoda"], "p": poslovnice})
        zapisi_json(izlaz / "grupe.json", {"verzija": verzija, "grupe": self.raz.za_aplikaciju()})
        if self.lok is not None:
            zapisi_json(izlaz / "lokacije.json", self.lok.za_objavu())
            meta["lokacije"] = dict(self.lok.stat, upita=self.lok.upita)
            log(f"Lokacije poslovnica (OpenStreetMap): {meta['lokacije']}")
        zapisi_json(izlaz / "meta.json", meta, lijepo=True)
        self.meta = meta


def delta(niz: list[int]) -> list[int]:
    out, prije = [], 0
    for x in niz:
        out.append(x - prije)
        prije = x
    return out


def datoteka_poslovnice(lanac: dict, lokalni: dict[int, int]) -> str:
    """Cijene jedne poslovnice kao razlika od uobičajenih cijena lanca.

    Položaji su redni brojevi u popisu proizvoda lanca. 'u' = proizvodi koje poslovnica ima (ili 'o' = koje
    nema, što je kraće), 'd'/'c' = položaji i cijene koje se razlikuju od uobičajene cijene lanca.
    """
    idx, prije = [], 0
    for d in lanac["i"]:
        prije += d
        idx.append(prije)
    ima, nema, razlike_i, razlike_c = [], [], [], []
    for poz, (gi, t) in enumerate(zip(idx, lanac["t"])):
        c = lokalni.get(gi)
        if c is None:
            nema.append(poz)
        else:
            ima.append(poz)
            if c != t:
                razlike_i.append(poz)
                razlike_c.append(c)
    zapis = {"o": delta(nema)} if len(nema) <= len(ima) else {"u": delta(ima)}
    zapis["d"] = delta(razlike_i)
    zapis["c"] = razlike_c
    return json.dumps(zapis, separators=(",", ":"))


def zapisi_json(put: Path, podaci, lijepo=False):
    privremena = put.with_suffix(".tmp")
    with open(privremena, "w", encoding="utf-8") as f:
        if lijepo:
            json.dump(podaci, f, ensure_ascii=False, indent=1)
        else:
            json.dump(podaci, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(privremena, put)


# ---------------------------------------------------------------- tijek
def broj_proizvoda_lanca(L: Lanac) -> dict[str, int]:
    out = Counter()
    for (pl, _pid) in L.efektivne:
        out[pl] += 1
    return out


def pokreni(argumenti) -> dict:
    izlaz = Path(argumenti.izlaz)
    raz = Razvrstavanje()

    # --bez-dopune isključuje samo mrežne (zadane) izvore dopune; datoteka navedena izričito uvijek se koristi
    # (prije je --bez-dopune tiho odbacivao i --dopuna-poslovnica, pa testovi u pregledniku nisu imali koordinate).
    dp, dpo = {}, {}
    def tekst(izvor):
        return (preuzmi(izvor) if izvor.startswith("http") else Path(izvor).read_bytes()).decode("utf-8", "replace")
    def koristi(izvor, zadano):
        return not (argumenti.bez_dopune and (izvor == zadano or str(izvor).startswith("http")))
    if koristi(argumenti.dopuna_proizvoda, DOPUNA_PROIZVODA):
        try:
            dp = citaj_dopunu_proizvoda(tekst(argumenti.dopuna_proizvoda))
            log(f"Dopuna proizvoda: {len(dp)}")
        except Exception as e:  # noqa: BLE001 - dopuna nije obavezna
            log(f"Dopuna proizvoda nedostupna ({e}); nastavljam bez nje")
    if koristi(argumenti.dopuna_poslovnica, DOPUNA_POSLOVNICA):
        try:
            dpo = citaj_dopunu_poslovnica(tekst(argumenti.dopuna_poslovnica))
            log(f"Koordinate poslovnica: {len(dpo)}")
        except Exception as e:  # noqa: BLE001
            log(f"Koordinate poslovnica nedostupne ({e}); karta će biti bez njih")

    prethodno = {}
    if argumenti.prethodni:
        try:
            izvor = argumenti.prethodni
            tekst = preuzmi(izvor, pokusaja=2, timeout=30) if izvor.startswith("http") else Path(izvor).read_bytes()
            stari = json.loads(tekst)
            prethodno = {l["id"]: l for l in stari.get("lanci", [])}
            prethodno["__ukupno__"] = stari.get("proizvoda", 0)
            log(f"Prethodno objavljeno: {stari.get('datum')} ({stari.get('proizvoda')} proizvoda)")
        except Exception as e:  # noqa: BLE001
            log(f"Prethodno objavljeni podaci nisu dostupni ({e}); usporedba se preskače")

    # popis arhiva: lokalne datoteke (test) ili preuzimanje
    if argumenti.arhiva:
        arhive = [{"date": Path(a).stem[-10:], "put": Path(a)} for a in argumenti.arhiva]
    else:
        arhive = popis_arhiva()[:4]
        if not arhive:
            raise RuntimeError("Popis arhiva cjenika je prazan.")

    uvoz = Uvoz(dp, dpo, raz, argumenti.najmanje_poslovnica)
    if not argumenti.bez_dopune and not argumenti.bez_lokacija:
        predmemorija = {}
        if argumenti.lokacije:
            try:
                izvor = argumenti.lokacije
                predmemorija = json.loads(preuzmi(izvor, pokusaja=2, timeout=30) if izvor.startswith("http")
                                          else Path(izvor).read_bytes())
                log(f"Spremljene lokacije poslovnica: {len(predmemorija.get('a', {}))}")
            except Exception as e:  # noqa: BLE001 - prvi put ili stranica nedostupna: kreće se od nule
                log(f"Spremljene lokacije nisu dostupne ({e}); tražim ispočetka")
        uvoz.lok = Lokacije(predmemorija, KORISNIK)
    privremeno = Path(argumenti.privremeno)
    privremeno.mkdir(parents=True, exist_ok=True)
    otvorene = []

    def otvori(a):
        put = a.get("put")
        if put is None:
            put = privremeno / f"{a['date']}.zip"
            if not put.exists() or put.stat().st_size == 0:
                log(f"Preuzimam arhivu {a['date']} ({int(a.get('size', 0)) // 1_000_000} MB)")
                preuzmi(a["url"], put, timeout=600)
        zf = zipfile.ZipFile(put)
        otvorene.append(zf)
        return zf

    najnovija = arhive[0]
    zf = otvori(najnovija)
    datum = najnovija["date"]
    log(f"Arhiva: {datum}")
    dobri = set()
    for lanac, prefiks in sorted(lanci_u_arhivi(zf).items()):
        try:
            L = Lanac(zf, najnovija["date"], lanac, prefiks, datum).ucitaj()
        except Exception as e:  # noqa: BLE001 - jedan pokvaren lanac ne ruši cijeli uvoz
            uvoz.upozorenja.append(f"{IMENA.get(lanac, lanac)}: cjenik se ne može pročitati ({type(e).__name__}: {e}).")
            log(f"  {lanac}: GREŠKA {e}")
            continue
        brojevi = broj_proizvoda_lanca(L)
        ukupno = sum(brojevi.values())
        jucer = sum(prethodno.get(pl, {}).get("proizvoda", 0) for pl in brojevi) or prethodno.get(lanac, {}).get("proizvoda", 0)
        if ukupno == 0 or (jucer and ukupno < jucer * SLABIJI_OD):
            uvoz.upozorenja.append(f"{IMENA.get(lanac, lanac)}: danas samo {ukupno} proizvoda (prije {jucer}); tražim stariji cjenik.")
            log(f"  {lanac}: slab cjenik ({ukupno} prema {jucer})")
            continue
        uvoz.dodaj(L, "ok")
        dobri.add(lanac)
        log(f"  {lanac}: {len(L.poslovnice)} poslovnica, {ukupno} ponuda")

    # nedostaje li lanac koji je prije postojao? potraži ga u starijim arhivama
    ocekivani = {l for l in prethodno if not l.startswith("__") and l != "interspar"} | set(lanci_u_arhivi(zf)) | set(GLAVNI)
    if "interspar" in prethodno:
        ocekivani.add("spar")
    nedostaju = sorted(ocekivani - dobri - PRESKOCI)
    for a in arhive[1:]:
        if not nedostaju or argumenti.arhiva and len(arhive) == 1:
            break
        try:
            starija = otvori(a)
        except Exception as e:  # noqa: BLE001
            uvoz.upozorenja.append(f"Starija arhiva {a['date']} nije dostupna ({e}).")
            continue
        u_arhivi = lanci_u_arhivi(starija)
        for lanac in list(nedostaju):
            if lanac not in u_arhivi:
                continue
            try:
                L = Lanac(starija, a["date"], lanac, u_arhivi[lanac], a["date"]).ucitaj()
            except Exception:  # noqa: BLE001
                continue
            if sum(broj_proizvoda_lanca(L).values()) == 0:
                continue
            uvoz.dodaj(L, "stari", f"Današnji cjenik nije dostupan ili je nepotpun; prikazane su cijene od {a['date']}.")
            nedostaju.remove(lanac)
            log(f"  {lanac}: koristim stariji cjenik {a['date']}")
    for lanac in nedostaju:
        uvoz.status[lanac] = {"status": "nema", "datum": "", "napomena": "Cjenik nije dostupan ni u zadnja 3 dana."}

    meta = uvoz.izgradi(izlaz, datum)
    for z in otvorene:
        z.close()

    stari_ukupno = prethodno.get("__ukupno__", 0)
    if stari_ukupno and meta["proizvoda"] < stari_ukupno * 0.6 and not argumenti.prisilno:
        raise ZastitaObjave(f"Novi cjenik ima {meta['proizvoda']} proizvoda, a objavljeni {stari_ukupno}. "
                            "Objava je zaustavljena da ostanu zadnji dobri podaci.")
    log(f"Gotovo: {meta['proizvoda']} proizvoda, {meta['poslovnica']} poslovnica, {len(meta['lanci'])} lanaca")
    for u in meta["upozorenja"]:
        log("UPOZORENJE: " + u)
    return meta


class ZastitaObjave(RuntimeError):
    pass


def izvjesce_greske(e: BaseException, argumenti) -> str:
    return "\n".join([
        "## Izvješće o grešci – dnevni uvoz cijena (Najjeftinija košarica)",
        "",
        "Kopiraj cijeli ovaj tekst i zalijepi ga u Claude Code s porukom: \"Popravi ovu grešku u uvozu cijena\".",
        "",
        f"- Vrijeme (UTC): {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"- Vrsta: {type(e).__name__}",
        f"- Poruka: {e}",
        f"- Zaštita objave: {'da – aplikacija i dalje prikazuje zadnje dobre cijene' if isinstance(e, ZastitaObjave) else 'ne'}",
        f"- Argumenti: {vars(argumenti)}",
        "",
        "```",
        traceback.format_exc()[-6000:],
        "```",
    ])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--izlaz", default="app/data/hr")
    ap.add_argument("--arhiva", nargs="*", help="lokalne ZIP arhive (najnovija prva) umjesto preuzimanja")
    ap.add_argument("--prethodni", help="URL ili put do prethodno objavljenog meta.json")
    ap.add_argument("--privremeno", default=os.environ.get("RUNNER_TEMP", "/tmp") + "/kosarica-arhive")
    ap.add_argument("--bez-dopune", action="store_true")
    ap.add_argument("--dopuna-proizvoda", default=DOPUNA_PROIZVODA, help="URL ili put do provjerenih količina")
    ap.add_argument("--dopuna-poslovnica", default=DOPUNA_POSLOVNICA, help="URL ili put do koordinata poslovnica")
    ap.add_argument("--lokacije", help="URL ili put do prethodno objavljenog lokacije.json (spremljene koordinate)")
    ap.add_argument("--bez-lokacija", action="store_true", help="ne traži koordinate poslovnica na OpenStreetMapu")
    ap.add_argument("--najmanje-poslovnica", type=int, default=NAJMANJE_POSLOVNICA,
                    help="lanci s manje poslovnica se ne prikazuju (odluka vlasnika: 19; testni primjer koristi 1)")
    ap.add_argument("--prisilno", action="store_true", help="objavi i ako je novi cjenik bitno slabiji")
    ap.add_argument("--izvjesce", default="izvjesce-greske.md")
    argumenti = ap.parse_args(argv)
    try:
        pokreni(argumenti)
    except Exception as e:  # noqa: BLE001
        tekst = izvjesce_greske(e, argumenti)
        Path(argumenti.izvjesce).write_text(tekst, encoding="utf-8")
        print(tekst, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
