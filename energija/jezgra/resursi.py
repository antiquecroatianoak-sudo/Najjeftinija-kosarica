"""Dinamičko upravljanje resursima: CPU, memorija, SD kartica i – najvažnije – baterija.

Način rada bira se iz stanja baterije i opterećenja uređaja:
- NORMALNO: puni intervali.
- STEDNO (baterija nisko ili CPU zauzet): rjeđe uzorkovanje nekritičnih kanala, rjeđa
  sinkronizacija i otkrivanje, bez teških poslova.
- KRITICNO (baterija na rezervi): samo zaštita, pastir i dnevnik kvarova; mreža/radio
  minimalno.
- PRILIKA: višak sunca i slobodan CPU -> teški poslovi (učenje, izvještaji, provjera
  kopija) odrađuju se tada, kad je energija besplatna.
"""
from __future__ import annotations

import os

INTERVALI = {  # sekunde
    "NORMALNO": {"ocitanje": 10, "sinkronizacija": 900, "otkrivanje": 300, "kopija": 3600, "plan": 900},
    "PRILIKA": {"ocitanje": 10, "sinkronizacija": 600, "otkrivanje": 300, "kopija": 1800, "plan": 600},
    "STEDNO": {"ocitanje": 30, "sinkronizacija": 3600, "otkrivanje": 1800, "kopija": 6 * 3600, "plan": 1800},
    "KRITICNO": {"ocitanje": 60, "sinkronizacija": 6 * 3600, "otkrivanje": 6 * 3600, "kopija": 24 * 3600, "plan": 3600},
}


def opterecenje() -> dict:
    out = {"jezgri": os.cpu_count() or 1, "load1": None, "mem_slobodno_mb": None, "rss_mb": None}
    try:
        out["load1"] = os.getloadavg()[0]
    except OSError:
        pass
    try:
        with open("/proc/meminfo") as f:
            m = {l.split(":")[0]: int(l.split()[1]) for l in f if ":" in l}
        out["mem_slobodno_mb"] = m.get("MemAvailable", 0) // 1024
        with open("/proc/self/status") as f:
            for l in f:
                if l.startswith("VmRSS:"):
                    out["rss_mb"] = int(l.split()[1]) // 1024
    except (OSError, ValueError):
        pass
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            out["cpu_temp_c"] = int(f.read()) / 1000
    except (OSError, ValueError):
        pass
    return out


def odaberi_nacin(soc: float | None, rezerva: float, visak_sunca_w: float, load1: float | None,
                  jezgri: int, cpu_temp: float | None = None) -> str:
    if soc is not None and soc <= rezerva:
        return "KRITICNO"
    zauzeto = load1 is not None and load1 > 0.8 * jezgri
    vruce = cpu_temp is not None and cpu_temp > 75
    if (soc is not None and soc < rezerva + 0.10) or zauzeto or vruce:
        return "STEDNO"
    if visak_sunca_w > 300 and not zauzeto:
        return "PRILIKA"
    return "NORMALNO"


def radnika(nacin: str, jezgri: int) -> int:
    """Broj paralelnih radnika za teške poslove (npr. generiranje izvještaja, provjera kopija)."""
    return {"PRILIKA": max(1, jezgri - 1), "NORMALNO": max(1, jezgri // 2)}.get(nacin, 1)
