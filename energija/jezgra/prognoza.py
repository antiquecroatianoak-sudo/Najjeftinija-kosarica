"""Lokalna vremenska prognoza za optimizaciju panela, baterije i navodnjavanja.

Izvor: Open-Meteo (bez ključa) – zračenje, temperatura, oborine, naoblaka po satu za 48 h.
Bez interneta: zadnja prognoza dok vrijedi, zatim model vedrog neba (položaj Sunca) ×
klimatski faktor naoblake koji jezgra uči iz omjera stvarne i vedre proizvodnje panela.
Svaka vrijednost nosi `izvor`, pa izvještaj razlikuje prognozu od procjene.
"""
from __future__ import annotations

import json
import math
import time
import urllib.parse
import urllib.request
from pathlib import Path

URL = "https://api.open-meteo.com/v1/forecast"


def zracenje_vedro(ts: float, sirina: float, duzina: float) -> float:
    """Približno globalno zračenje vedrog neba (W/m²) – Haurwitzov model."""
    t = time.gmtime(ts)
    dan = t.tm_yday
    sat_utc = t.tm_hour + t.tm_min / 60
    deklinacija = 23.45 * math.sin(math.radians(360 / 365 * (284 + dan)))
    sunceno = sat_utc + duzina / 15.0
    kut = 15.0 * (sunceno - 12.0)
    fi, de = math.radians(sirina), math.radians(deklinacija)
    cos_z = math.sin(fi) * math.sin(de) + math.cos(fi) * math.cos(de) * math.cos(math.radians(kut))
    if cos_z <= 0:
        return 0.0
    return 1098.0 * cos_z * math.exp(-0.057 / cos_z)


def pv_snaga_w(zracenje: float, temp_c: float, cfg: dict) -> float:
    f = cfg["fotonapon"]
    t_celije = temp_c + zracenje * 0.03
    return max(0.0, f["kwp"] * 1000 * zracenje / 1000 * f["faktor_ucinka"] * (1 + f["temp_koef"] * (t_celije - 25)))


class Prognoza:
    def __init__(self, cfg: dict, mapa: Path):
        self.cfg = cfg
        self.p = Path(mapa) / "prognoza.json"
        self.sati: list[dict] = []
        self.vrijeme = 0.0
        self.faktor_naoblake = 0.65  # uči se iz stvarne proizvodnje
        self.greska: str | None = None
        if self.p.exists():
            try:
                v = json.loads(self.p.read_text())
                self.sati, self.vrijeme = v["sati"], v["vrijeme"]
                self.faktor_naoblake = v.get("faktor", self.faktor_naoblake)
            except (ValueError, KeyError, OSError):
                pass

    def osvjezi(self, sada: float | None = None, dohvati=None) -> bool:
        sada = sada or time.time()
        if sada - self.vrijeme < 3 * 3600 and self.sati:
            return True
        lok = self.cfg["lokacija"]
        try:
            if dohvati:
                v = dohvati()
            else:
                upit = urllib.parse.urlencode({
                    "latitude": lok["sirina"], "longitude": lok["duzina"], "forecast_days": 2,
                    "hourly": "shortwave_radiation,temperature_2m,precipitation,cloud_cover", "timeformat": "unixtime"})
                with urllib.request.urlopen(f"{URL}?{upit}", timeout=15) as r:
                    v = json.loads(r.read())
            h = v["hourly"]
            self.sati = [{"ts": float(t), "zracenje": float(g or 0), "temp": float(tc or 10),
                          "oborine_mm": float(p or 0), "naoblaka": float(c or 0)}
                         for t, g, tc, p, c in zip(h["time"], h["shortwave_radiation"], h["temperature_2m"],
                                                   h["precipitation"], h["cloud_cover"])]
            self.vrijeme = sada
            self.greska = None
            self._spremi()
            return True
        except Exception as e:
            self.greska = f"{type(e).__name__}: {e}"
            return False

    def _spremi(self) -> None:
        tmp = self.p.with_suffix(".tmp")
        tmp.write_text(json.dumps({"sati": self.sati, "vrijeme": self.vrijeme, "faktor": self.faktor_naoblake}))
        tmp.replace(self.p)

    def uci_naoblaku(self, stvarno_w: float, ts: float) -> None:
        vedro = pv_snaga_w(zracenje_vedro(ts, self.cfg["lokacija"]["sirina"], self.cfg["lokacija"]["duzina"]), 15,
                           self.cfg)
        if vedro > 500:
            omjer = min(1.2, stvarno_w / vedro)
            self.faktor_naoblake += 0.002 * (omjer - self.faktor_naoblake)

    def niz(self, od_ts: float, sati: int = 48) -> list[dict]:
        lok = self.cfg["lokacija"]
        pocetak = od_ts - od_ts % 3600
        po_satu = {int(s["ts"] // 3600): s for s in self.sati}
        out = []
        for i in range(sati):
            ts = pocetak + i * 3600
            s = po_satu.get(int(ts // 3600))
            if s:
                out.append({"ts": ts, "pv_w": pv_snaga_w(s["zracenje"], s["temp"], self.cfg),
                            "oborine_mm": s["oborine_mm"], "temp": s["temp"], "izvor": "prognoza"})
            else:
                g = zracenje_vedro(ts + 1800, lok["sirina"], lok["duzina"]) * self.faktor_naoblake
                out.append({"ts": ts, "pv_w": pv_snaga_w(g, 15, self.cfg), "oborine_mm": None, "temp": None,
                            "izvor": "procjena"})
        return out

    def kisa_sljedecih(self, od_ts: float, sati: int = 12) -> float | None:
        v = [s["oborine_mm"] for s in self.niz(od_ts, sati)]
        return None if any(x is None for x in v) else sum(v)
