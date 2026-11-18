"""Provjera vjerodostojnosti očitanja s uređaja, prije nego što ih vide planer, zaštita i učenje.

Uređaji ponekad šalju vrijednosti koje nisu mjerenja: NaN/beskonačno preko MQTT-a, oznake „nije dostupno”
SunSpec uređaja (rješavaju se već u `otkrivanje.py`) ili fizikalno nemoguće brojeve (napunjenost 6553 %).
Takvo očitanje se odbacuje, kao da kanal nije javljen: jezgra tada radi s posljednjim poznatim stanjem i
zadanim ponašanjem, a odbačeni kanali vide se u dijagnostici. Granice su namjerno široke – stvarne anomalije
(pregrijana baterija, kratki spoj ograde) ostaju unutar njih i obrađuje ih detektor anomalija.
"""
from __future__ import annotations

import math

# (završetak ili točno ime kanala) -> (najmanje, najviše); prvo pravilo koje odgovara vrijedi
GRANICE: list[tuple[str, float, float]] = [
    ("pv_snaga_w", -200.0, 200_000.0),
    ("mreza_prisutna", 0.0, 1.0),
    ("_soc", 0.0, 1.05),
    ("_temp_c", -50.0, 130.0),
    ("_napon_v", 0.0, 1500.0),
    ("_kv", 0.0, 25.0),
    ("_vlaga", 0.0, 100.0),
    ("_snaga_w", -200_000.0, 200_000.0),
    ("_struja_a", -2000.0, 2000.0),
    ("_kwh", 0.0, 1e9),
]


def granice(kanal: str) -> tuple[float, float] | None:
    for kraj, mn, mx in GRANICE:
        if kanal == kraj or kanal.endswith(kraj):
            return mn, mx
    return None


def ocisti(o: dict) -> tuple[dict[str, float], dict[str, str]]:
    """Vraća (vjerodostojna očitanja, {kanal: razlog odbacivanja})."""
    cisto: dict[str, float] = {}
    odbaceno: dict[str, str] = {}
    for k, v in o.items():
        if isinstance(v, bool):
            v = float(v)
        if not isinstance(v, (int, float)):
            odbaceno[k] = f"nije broj: {v!r}"[:80]
            continue
        if not math.isfinite(v):
            odbaceno[k] = f"nije konačan broj: {v}"
            continue
        g = granice(k)
        if g and not g[0] <= v <= g[1]:
            odbaceno[k] = f"{v:g} izvan fizikalnog raspona {g[0]:g}–{g[1]:g}"
            continue
        cisto[k] = v
    return cisto, odbaceno


def broj(v, ime: str, mn: float, mx: float, cijeli: bool = False) -> float:
    """Broj iz vanjskog zahtjeva (API, naredbe, zahtjevi mreže): konačan i unutar [mn, mx], inače ValueError
    s porukom za korisnika. NaN i beskonačno se nikad ne propuštaju (min/max ih ne bi zaustavili)."""
    if isinstance(v, (list, tuple)) and len(v) == 1:  # parametar upita (?dana=7 -> ["7"])
        v = v[0]
    if isinstance(v, bool):
        raise ValueError(f"{ime}: očekivan broj")
    try:
        x = float(str(v).replace(",", ".")) if isinstance(v, str) else float(v)
    except (TypeError, ValueError):
        raise ValueError(f"{ime}: očekivan broj, dobiveno {v!r}"[:120]) from None
    if not math.isfinite(x) or not mn <= x <= mx:
        raise ValueError(f"{ime}: dopušteno {mn:g}–{mx:g}")
    if cijeli:
        if x != int(x):
            raise ValueError(f"{ime}: očekivan cijeli broj")
        return int(x)
    return x
