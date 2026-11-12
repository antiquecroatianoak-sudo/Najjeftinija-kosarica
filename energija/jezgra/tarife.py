"""Dinamičke tarife električne energije – preuzimanje, predmemorija i offline zamjena.

Izvori (redom pokušaja):
1. JSON izvor (`tarifa.izvor_url`), npr. vlastiti posrednik koji preuzima burzovne cijene
   dan-unaprijed (CROPEX / ENTSO-E) ili cjenik opskrbljivača s dinamičkom tarifom.
   Format: {"cijene": [{"od": ISO8601 ili unix, "do": ..., "eur_kwh": 0.12, "izvoz_eur_kwh": 0.05}, ...]}
2. Zadnje uspješno preuzete cijene (predmemorija na disku) dok pokrivaju razdoblje.
3. Ugovorni dvotarifni model VT/NT (radi bez interneta).

Pretpostavka: kućanstva u Hrvatskoj uglavnom imaju VT/NT; burzovna cijena nije nužno
cijena koju kupac plaća. Zato je izvor uvijek naveden uz svaku cijenu (`izvor`).
"""
from __future__ import annotations

import datetime as dt
import json
import time
import urllib.request
from pathlib import Path


def _ts(v) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    return dt.datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp()


def je_ljetno(ts: float) -> bool:
    """Ljetno računanje vremena po lokalnom vremenu uređaja."""
    return bool(time.localtime(ts).tm_isdst)


def vt_nt(ts: float, cfg: dict) -> tuple[float, str]:
    h = time.localtime(ts).tm_hour
    od, do = (22, 8) if je_ljetno(ts) else (21, 7)
    nt = h >= od or h < do
    return (cfg["nt_eur_kwh"], "NT") if nt else (cfg["vt_eur_kwh"], "VT")


class Tarife:
    def __init__(self, cfg: dict, mapa: Path):
        self.cfg = cfg["tarifa"]
        self.p = Path(mapa) / "tarife.json"
        self.cijene: list[dict] = []
        self.zadnje_preuzimanje = 0.0
        self.greska: str | None = None
        if self.p.exists():
            try:
                v = json.loads(self.p.read_text())
                self.cijene, self.zadnje_preuzimanje = v["cijene"], v["vrijeme"]
            except (ValueError, KeyError, OSError):
                pass

    def osvjezi(self, sada: float | None = None, dohvati=None) -> bool:
        sada = sada or time.time()
        url = self.cfg.get("izvor_url")
        if not url and dohvati is None:
            return False
        if sada - self.zadnje_preuzimanje < self.cfg["osvjezi_sati"] * 3600 and self.cijene:
            return True
        try:
            if dohvati:
                sirovo = dohvati()
            else:
                with urllib.request.urlopen(url, timeout=15) as r:
                    sirovo = json.loads(r.read())
            nove = [{"od": _ts(c["od"]), "do": _ts(c["do"]), "eur_kwh": float(c["eur_kwh"]),
                     "izvoz_eur_kwh": float(c.get("izvoz_eur_kwh", self.cfg["izvoz_eur_kwh"]))}
                    for c in sirovo["cijene"]]
            nove = [c for c in nove if c["do"] > c["od"] and -1.0 < c["eur_kwh"] < 5.0]  # odbaci besmislene
            if not nove:
                raise ValueError("izvor nema valjanih cijena")
            self.cijene = sorted(nove, key=lambda c: c["od"])
            self.zadnje_preuzimanje = sada
            self.greska = None
            tmp = self.p.with_suffix(".tmp")
            tmp.write_text(json.dumps({"cijene": self.cijene, "vrijeme": sada}))
            tmp.replace(self.p)
            return True
        except Exception as e:  # offline ili neispravan izvor -> zadnje poznate / VT-NT
            self.greska = f"{type(e).__name__}: {e}"
            return False

    def cijena(self, ts: float) -> dict:
        for c in self.cijene:
            if c["od"] <= ts < c["do"]:
                return {"kupnja": c["eur_kwh"], "prodaja": c["izvoz_eur_kwh"], "izvor": "dinamicka"}
        v, naziv = vt_nt(ts, self.cfg)
        return {"kupnja": v, "prodaja": self.cfg["izvoz_eur_kwh"], "izvor": naziv}

    def niz(self, od_ts: float, sati: int = 48) -> list[dict]:
        pocetak = od_ts - od_ts % 3600
        return [self.cijena(pocetak + i * 3600 + 1800) for i in range(sati)]
