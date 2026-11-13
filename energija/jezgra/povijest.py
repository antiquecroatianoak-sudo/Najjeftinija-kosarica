"""Vremenske serije za grafikone (API /api/v1/povijest).

- Zadnjih 48 h u minutnoj razlučivosti (prsten u memoriji, ~2880 točaka × ~20 serija ≈ nekoliko stotina kB).
- Dulja razdoblja iz satnih zapisa jezgre (energija, cijena, baterija, bojler).
- Nakon ponovnog pokretanja prsten se puni iz šifriranog dnevnika telemetrije (samo zadnji segmenti).

Imena serija su dio javnog API-ja (vidi SERIJE); ne mijenjati ih bez nove verzije API-ja.
"""
from __future__ import annotations

import threading
from collections import deque

MINUTA = 60
KAPACITET = 48 * 60

# ime -> (jedinica, opis, dostupno i za dulja razdoblja iz satnih zapisa)
SERIJE: dict[str, tuple[str, str, bool]] = {
    "pv_w": ("W", "Proizvodnja sunčanih panela", True),
    "pv_prognoza_w": ("W", "Prognozirana proizvodnja panela", False),
    "potrosnja_w": ("W", "Ukupna potrošnja", True),
    "mreza_w": ("W", "Mreža (+ uvoz, − izvoz)", True),
    "baterija_w": ("W", "Baterija (+ punjenje, − pražnjenje)", True),
    "baterija_soc": ("%", "Napunjenost baterije", True),
    "cijena_eur_kwh": ("€/kWh", "Kupovna cijena", True),
    "bojler_w": ("W", "Snaga grijača bojlera", True),
    "bojler_temp_c": ("°C", "Temperatura vode u bojleru", False),
    "okolina_temp_c": ("°C", "Vanjska temperatura", True),
    "pumpa_w": ("W", "Pumpa za navodnjavanje", True),
}
# dinamičke serije (po uređaju): pastir_v{k}_kv, tlo_{zona}_vlaga
DINAMICKE_PREFIKSI = ("pastir_v", "tlo_")


def je_poznata(ime: str) -> bool:
    return ime in SERIJE or ime.startswith(DINAMICKE_PREFIKSI)


class Povijest:
    def __init__(self):
        self._prsten: deque[dict] = deque(maxlen=KAPACITET)
        self._tekuca: dict | None = None
        self._lock = threading.Lock()

    def dodaj(self, ts: float, vrijednosti: dict[str, float | None]) -> None:
        minuta = ts - ts % MINUTA
        with self._lock:
            if self._tekuca and self._tekuca["t"] != minuta:
                self._zakljuci()
            if not self._tekuca:
                self._tekuca = {"t": minuta, "zbroj": {}, "n": {}}
            for k, v in vrijednosti.items():
                if v is None:
                    continue
                self._tekuca["zbroj"][k] = self._tekuca["zbroj"].get(k, 0.0) + float(v)
                self._tekuca["n"][k] = self._tekuca["n"].get(k, 0) + 1

    def _zakljuci(self) -> None:
        t = self._tekuca
        self._prsten.append({"t": t["t"], **{k: t["zbroj"][k] / t["n"][k] for k in t["zbroj"]}})
        self._tekuca = None

    def imena(self) -> list[str]:
        with self._lock:
            zadnje = list(self._prsten)[-1:] + ([{"t": 0, **self._tekuca["zbroj"]}] if self._tekuca else [])
        imena = set(SERIJE)
        for z in zadnje:
            imena |= {k for k in z if k.startswith(DINAMICKE_PREFIKSI)}
        return sorted(imena)

    def serija(self, imena: list[str], od: float, do: float, korak_s: int, sati: list[dict] | None = None) -> dict:
        """Vrati {"t": [...], "serije": {ime: [...]}}, srednje vrijednosti po koraku (None gdje nema podataka)."""
        korak_s = max(MINUTA, int(korak_s))
        pocetak = od - od % korak_s
        n = max(1, min(2000, int((do - pocetak) // korak_s) + 1))
        zbroj = {i: [0.0] * n for i in imena}
        broj = {i: [0] * n for i in imena}
        with self._lock:
            tocke = list(self._prsten)
        najstarija = tocke[0]["t"] if tocke else do
        for p in tocke:
            if od <= p["t"] <= do:
                i = int((p["t"] - pocetak) // korak_s)
                if 0 <= i < n:
                    for ime in imena:
                        if ime in p:
                            zbroj[ime][i] += p[ime]
                            broj[ime][i] += 1
        # stariji dio razdoblja iz satnih zapisa (samo serije dostupne u satnoj razlučivosti)
        if sati and od < najstarija:
            for s in sati:
                if not (od <= s["ts"] < min(do, najstarija)):
                    continue
                i = int((s["ts"] - pocetak) // korak_s)
                if not 0 <= i < n:
                    continue
                vr = _iz_sata(s)
                for ime in imena:
                    if ime in vr and vr[ime] is not None:
                        zbroj[ime][i] += vr[ime]
                        broj[ime][i] += 1
        return {"t": [pocetak + i * korak_s for i in range(n)], "korak_s": korak_s,
                "serije": {ime: [round(zbroj[ime][i] / broj[ime][i], 4) if broj[ime][i] else None for i in range(n)]
                           for ime in imena}}


def _iz_sata(s: dict) -> dict:
    """Satni zapis jezgre -> prosječne snage u W (kWh u satu = prosječni kW)."""
    return {
        "pv_w": s["pv_kwh"] * 1000, "potrosnja_w": s["potrosnja_kwh"] * 1000,
        "mreza_w": (s["uvoz_kwh"] - s["izvoz_kwh"]) * 1000, "baterija_w": s.get("bat_neto_kwh", 0.0) * 1000,
        "baterija_soc": None if s.get("soc_kraj") is None else s["soc_kraj"] * 100,
        "cijena_eur_kwh": s.get("cijena_kupnja"), "bojler_w": s.get("bojler_kwh", 0.0) * 1000,
        "pumpa_w": s.get("pumpa_kwh", 0.0) * 1000, "okolina_temp_c": s.get("temp"),
    }
