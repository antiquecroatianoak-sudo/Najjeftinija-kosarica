"""Stres testovi s POVIJESNIM podacima o vremenu i cijenama.

Izvori (oba besplatna, licencija CC BY 4.0 – navesti izvor):
- vrijeme: Open-Meteo arhiva (ERA5/ERA5-Land), satno: zračenje, temperatura, oborine, naoblaka,
- cijene: Energy-Charts (Fraunhofer ISE), burzovne cijene dan-unaprijed po zoni (EUR/MWh; od 10/2025 i 15-min,
  ovdje usrednjeno po satu). Pokušava se zona HR, zatim SI, pa HU (koja je stvarno korištena, piše u podacima).

Maloprodajna cijena = burzovna + `DODATAK_EUR_KWH` (mrežnina, naknade i PDV – PRETPOSTAVKA, mijenja se
parametrom); izvoz = burzovna cijena (smije biti negativna). Prognoza u stres testu = stvarno vrijeme
(optimistično; bez pogreške prognoze – pogreške prognoze pokrivaju zasebni scenariji).

    python -m stres.povijest preuzmi --od 2024-01-01 --do 2025-12-31 --izlaz podaci/povijest.json
    python -m stres.povijest pokreni --podaci podaci/povijest.json --izlaz rezultati/stres
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import random
import statistics
import time
import urllib.parse
import urllib.request
from pathlib import Path

from jezgra.simulacija import Lokacija

LAT, LON = 45.81, 15.98
DODATAK_EUR_KWH = 0.085
ZONE = ("HR", "SI", "HU")


# ------------------------------------------------------------------ preuzimanje
def _json(url: str, timeout: float = 60) -> dict:
    z = urllib.request.Request(url, headers={"User-Agent": "energija-stres-test/1.0"})
    with urllib.request.urlopen(z, timeout=timeout) as r:
        return json.loads(r.read())


def preuzmi_vrijeme(od: str, do: str, lat: float = LAT, lon: float = LON) -> dict:
    upit = urllib.parse.urlencode({"latitude": lat, "longitude": lon, "start_date": od, "end_date": do,
                                   "hourly": "shortwave_radiation,temperature_2m,precipitation,cloud_cover",
                                   "timeformat": "unixtime", "timezone": "GMT"})
    h = _json(f"https://archive-api.open-meteo.com/v1/archive?{upit}")["hourly"]
    return {"t": h["time"], "zracenje": h["shortwave_radiation"], "temp": h["temperature_2m"],
            "oborine": h["precipitation"], "naoblaka": h["cloud_cover"]}


def preuzmi_cijene(od: str, do: str) -> tuple[str, dict[int, float]]:
    zadnja = None
    for zona in ZONE:
        satne: dict[int, list[float]] = {}
        try:
            # po mjesecima: manji odgovori, manje osjetljivo na prekide
            d = dt.date.fromisoformat(od)
            kraj = dt.date.fromisoformat(do)
            while d <= kraj:
                sljedeci = (d.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
                v = _json(f"https://api.energy-charts.info/price?bzn={zona}&start={d.isoformat()}"
                          f"&end={min(kraj, sljedeci - dt.timedelta(days=1)).isoformat()}")
                for t, p in zip(v.get("unix_seconds", []), v.get("price", [])):
                    if p is not None:
                        satne.setdefault(int(t) - int(t) % 3600, []).append(float(p))
                d = sljedeci
                time.sleep(0.5)
            if len(satne) > 24 * 30:
                return zona, {t: sum(v) / len(v) / 1000.0 for t, v in satne.items()}  # EUR/MWh -> EUR/kWh
        except Exception as e:  # zona nije podržana ili servis nedostupan -> sljedeća
            zadnja = e
    raise RuntimeError(f"cijene nisu dostupne ni za jednu zonu {ZONE}: {zadnja}")


def preuzmi(od: str, do: str, izlaz: Path) -> dict:
    vrijeme = preuzmi_vrijeme(od, do)
    zona, cijene = preuzmi_cijene(od, do)
    podaci = {"meta": {"od": od, "do": do, "lokacija": [LAT, LON], "zona_cijena": zona,
                       "izvori": {"vrijeme": "Open-Meteo Historical Weather API (CC BY 4.0), https://open-meteo.com",
                                  "cijene": "Energy-Charts, Fraunhofer ISE (CC BY 4.0), https://energy-charts.info"},
                       "preuzeto": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                       "dodatak_eur_kwh": DODATAK_EUR_KWH},
              "vrijeme": vrijeme, "cijene": {str(k): round(v, 5) for k, v in sorted(cijene.items())}}
    izlaz.parent.mkdir(parents=True, exist_ok=True)
    izlaz.write_text(json.dumps(podaci))
    return podaci["meta"]


# ------------------------------------------------------------------ simulacija na povijesnim podacima
_PREDMEMORIJA: dict[str, dict] = {}


def ucitaj(put: str) -> dict:
    if put not in _PREDMEMORIJA:
        p = json.loads(Path(put).read_text())
        v = p["vrijeme"]
        p["_vrijeme_po_satu"] = {int(t): i for i, t in enumerate(v["t"])}
        p["_cijene"] = {int(k): x for k, x in p["cijene"].items()}
        _PREDMEMORIJA[put] = p
    return _PREDMEMORIJA[put]


class PovijesnaLokacija(Lokacija):
    """Ista fizika kuće, baterije, tla i ograde – ali stvarno vrijeme i stvarne cijene iz povijesti."""

    def __init__(self, cfg: dict, pocetak: float, podaci: dict, **kw):
        self.p = podaci
        super().__init__(cfg, pocetak, **kw)

    def _i(self, ts: float) -> int | None:
        return self.p["_vrijeme_po_satu"].get(int(ts - ts % 3600))

    def _v(self, ime: str, ts: float, zadano: float) -> float:
        i = self._i(ts)
        x = None if i is None else self.p["vrijeme"][ime][i]
        return zadano if x is None else float(x)

    def zracenje(self, ts: float, stvarno: bool = True) -> float:
        return self._v("zracenje", ts, 0.0)

    def okolina_temp(self, ts: float) -> float:
        return self._v("temp", ts, 10.0) + self.temp_pomak

    def kisa_mm_h(self, ts: float) -> float:
        return self._v("oborine", ts, 0.0)

    def naoblaka(self, ts: float, stvarna: bool = True) -> float:
        return self._v("naoblaka", ts, 50.0) / 100.0

    def tarife_api(self, od_ts: float) -> dict:
        pocetak = od_ts - od_ts % 3600
        dodatak = self.p["meta"].get("dodatak_eur_kwh", DODATAK_EUR_KWH)
        out = []
        for i in range(48):
            t = int(pocetak + i * 3600)
            spot = self.p["_cijene"].get(t)
            if spot is None:
                continue  # rupa u podacima: jezgra koristi zadnje poznate / VT-NT, kao u stvarnosti
            out.append({"od": t, "do": t + 3600, "eur_kwh": round(spot + dodatak, 5), "izvoz_eur_kwh": round(spot, 5)})
        return {"cijene": out}


def odaberi_tjedne(podaci: dict, nasumicnih: int = 3, sjeme: int = 11) -> list[tuple[str, float]]:
    """Najteži tjedni iz povijesti (ponedjeljak 00:00 lokalno) + nekoliko nasumičnih (ponovljivo)."""
    v = podaci["vrijeme"]
    cijene = podaci["_cijene"] if "_cijene" in podaci else {int(k): x for k, x in podaci["cijene"].items()}
    tjedni = []
    t0 = int(v["t"][0])
    d = dt.datetime.fromtimestamp(t0)
    d = (d + dt.timedelta(days=(7 - d.weekday()) % 7)).replace(hour=0, minute=0, second=0, microsecond=0)
    kraj = int(v["t"][-1]) - 7 * 86400
    while d.timestamp() <= kraj:
        a = int(d.timestamp())
        idx = [i for i, t in enumerate(v["t"]) if a <= t < a + 7 * 86400]
        cj = [cijene[t] for t in range(a, a + 7 * 86400, 3600) if t in cijene]
        if len(idx) > 150 and len(cj) > 150:
            tjedni.append({"pocetak": a, "temp": statistics.mean(v["temp"][i] for i in idx if v["temp"][i] is not None),
                           "zracenje": sum(v["zracenje"][i] or 0 for i in idx), "cijena": statistics.mean(cj),
                           "volatilnost": statistics.pstdev(cj), "negativnih": sum(1 for c in cj if c < 0)})
        d += dt.timedelta(days=7)
    if not tjedni:
        raise ValueError("u podacima nema nijednog potpunog tjedna")
    izbor: dict[str, dict] = {}
    for ime, kljuc, obrnuto in (("najhladniji", "temp", False), ("najtopliji", "temp", True),
                                ("najtamniji", "zracenje", False), ("najskuplji", "cijena", True),
                                ("najnestabilniji", "volatilnost", True), ("najvise_negativnih", "negativnih", True)):
        t = sorted(tjedni, key=lambda x: x[kljuc], reverse=obrnuto)[0]
        izbor.setdefault(ime, t)
    rng = random.Random(sjeme)
    preostali = [t for t in tjedni if t not in izbor.values()]
    for i, t in enumerate(rng.sample(preostali, min(nasumicnih, len(preostali)))):
        izbor[f"nasumicni_{i + 1}"] = t
    return [(ime, t["pocetak"]) for ime, t in izbor.items()]


def scenariji(put: str):
    """Stres scenariji iz povijesnih podataka (deterministično – isti put => isti scenariji)."""
    from scenariji.katalog import Scenarij
    podaci = ucitaj(put)
    out = []
    for ime, pocetak in odaberi_tjedne(podaci):
        lt = time.localtime(pocetak)
        out.append(Scenarij(f"stres_{ime}_{time.strftime('%Y-%m-%d', lt)}", f"Povijesni tjedan: {ime}",
                            (lt.tm_year, lt.tm_mon, lt.tm_mday), tarifa="dinamicka", povijest=put,
                            ocekivanja={"pastir_dostupnost_min": 0.93}, oznake=("stres",)))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Stres testovi s povijesnim podacima")
    pod = ap.add_subparsers(dest="naredba", required=True)
    a1 = pod.add_parser("preuzmi")
    a1.add_argument("--od", default="2024-01-01")
    a1.add_argument("--do", default="2025-12-31")
    a1.add_argument("--izlaz", type=Path, default=Path("podaci/povijest.json"))
    a2 = pod.add_parser("pokreni")
    a2.add_argument("--podaci", default="podaci/povijest.json")
    a2.add_argument("--izlaz", type=Path, default=Path("rezultati/stres"))
    a = ap.parse_args(argv)
    if a.naredba == "preuzmi":
        print(json.dumps(preuzmi(a.od, a.do, a.izlaz), ensure_ascii=False, indent=1))
        return 0
    os.environ["ENERGIJA_POVIJEST"] = str(Path(a.podaci).resolve())
    from scenariji.usporedba import usporedi, u_markdown
    from scenariji.znacajnost import analiziraj
    sc = scenariji(os.environ["ENERGIJA_POVIJEST"])
    print("Tjedni:", ", ".join(s.ime for s in sc), flush=True)
    r = usporedi([s.ime for s in sc])
    a.izlaz.mkdir(parents=True, exist_ok=True)
    (a.izlaz / "usporedba.json").write_text(json.dumps(r, indent=1, ensure_ascii=False))
    md = u_markdown(r)
    zn = analiziraj(r)
    meta = ucitaj(os.environ["ENERGIJA_POVIJEST"])["meta"]
    zaglavlje = (f"Povijesni podaci: {meta['od']}–{meta['do']}, cijene zona {meta['zona_cijena']} (+{meta['dodatak_eur_kwh']} €/kWh "
                 f"maloprodajni dodatak – pretpostavka). Izvori: {meta['izvori']['vrijeme']}; {meta['izvori']['cijene']}.\n\n")
    (a.izlaz / "usporedba.md").write_text(zaglavlje + md + "\n")
    (a.izlaz / "znacajnost.json").write_text(json.dumps(zn, indent=1, ensure_ascii=False))
    print(zaglavlje + md)
    krsenja = sum(x["strategije"]["pametna"]["krsenja"] + x["strategije"]["pametna"]["iznimke"] for x in r.values())
    print(f"\nSigurnosna kršenja (pametna): {krsenja}. K1 = {zn['K1']}. K2 ispunjen: {zn['K2']['ispunjen']}.")
    return 1 if krsenja else 0  # stres test pada na sigurnosti; trošak se izvještava (K1/K2), ne ruši cjevovod


if __name__ == "__main__":
    raise SystemExit(main())
