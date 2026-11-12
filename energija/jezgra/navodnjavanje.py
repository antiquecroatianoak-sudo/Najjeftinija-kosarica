"""Pametno navodnjavanje po zonama: vlaga tla + prognoza kiše + višak sunca.

Pravila (sva lokalna):
- zona se zalijeva kad vlaga padne ispod praga i u sljedećih 12 h ne očekuje se ≥3 mm kiše,
- prednost imaju sati s viškom sunca ili niskom cijenom; inače rano jutro (manje isparavanja),
- zalijevanje traje do ciljne vlage ili najviše `max_minuta`; jedna zona u isto vrijeme
  (pumpa i baterija nisu preopterećene),
- neispravan senzor (izvan raspona / zaglavljen) -> sigurni vremenski raspored (kratko,
  svaki drugi dan ujutro) umjesto zalijevanja "naslijepo" do iscrpljenja baterije,
- jezgra uči brzinu sušenja i brzinu vlaženja svake zone za procjenu sljedeće potrebe.
"""
from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class Zona:
    id: str
    prag: float = 30.0   # % volumetrijske vlage
    cilj: float = 42.0
    susenje_po_h: float = 0.25
    vlazenje_po_min: float = 0.5
    zadnja_vlaga: float | None = None
    zadnje_vrijeme: float | None = None
    zadnje_zalijevanje: float = 0.0
    nepromijenjeno_s: float = 0.0
    preskoceno: bool = False


class Navodnjavanje:
    def __init__(self, cfg: dict, stanje: dict | None = None):
        self.cfg = cfg["navodnjavanje"]
        self.zone: dict[str, Zona] = {k: Zona(**v) for k, v in (stanje or {}).get("zone", {}).items()}
        self.aktivna: str | None = None
        self.pocetak = 0.0
        self.pocetna_vlaga = 0.0
        self.dnevnik: list[dict] = []
        self.ustedjeno_min = 0.0  # preskočeno zbog kiše/vlage u odnosu na fiksni raspored

    def stanje(self) -> dict:
        return {"zone": {k: v.__dict__ for k, v in self.zone.items()}}

    def _senzor_ispravan(self, z: Zona, v: float | None) -> bool:
        return v is not None and 2.0 <= v <= 70.0 and z.nepromijenjeno_s < 6 * 3600

    def korak(self, ts: float, vlage: dict[str, float | None], kisa_12h: float | None,
              povoljno_sada: bool, pumpa_dopustena: bool) -> dict:
        """Vrati {"pumpa": bool, "ventil": zona|None, "razlog": str}."""
        for zid, v in vlage.items():
            z = self.zone.setdefault(zid, Zona(zid))
            if v is not None and z.zadnja_vlaga is not None and z.zadnje_vrijeme:
                dt_h = (ts - z.zadnje_vrijeme) / 3600
                z.nepromijenjeno_s = z.nepromijenjeno_s + dt_h * 3600 if abs(v - z.zadnja_vlaga) < 1e-6 else 0.0
                if self.aktivna != zid and v < z.zadnja_vlaga and dt_h > 0:
                    z.susenje_po_h += 0.05 * ((z.zadnja_vlaga - v) / dt_h - z.susenje_po_h)
            if v is not None:
                z.zadnja_vlaga, z.zadnje_vrijeme = v, ts

        sat = time.localtime(ts).tm_hour
        if self.aktivna:
            z = self.zone[self.aktivna]
            v = vlage.get(self.aktivna)
            trajanje = (ts - self.pocetak) / 60
            gotovo = (not pumpa_dopustena or trajanje >= self.cfg["max_minuta"]
                      or (self._senzor_ispravan(z, v) and v >= z.cilj)
                      or (not self._senzor_ispravan(z, v) and trajanje >= 10))
            if gotovo:
                if v is not None and trajanje > 1:
                    z.vlazenje_po_min += 0.2 * ((v - self.pocetna_vlaga) / trajanje - z.vlazenje_po_min)
                self.dnevnik.append({"zona": self.aktivna, "od": self.pocetak, "minuta": round(trajanje, 1),
                                     "vlaga_prije": self.pocetna_vlaga, "vlaga_poslije": v})
                del self.dnevnik[:-100]
                z.zadnje_zalijevanje = ts
                z.preskoceno = False
                self.aktivna = None
                return {"pumpa": False, "ventil": None, "razlog": "zalijevanje završeno"}
            return {"pumpa": True, "ventil": self.aktivna, "razlog": f"zalijevanje {trajanje:.0f} min"}

        if not pumpa_dopustena:
            return {"pumpa": False, "ventil": None, "razlog": "pumpa nije dopuštena (zaštita/baterija)"}
        kisa = kisa_12h if kisa_12h is not None else 0.0
        for zid, z in sorted(self.zone.items(), key=lambda kv: (kv[1].zadnja_vlaga or 99)):
            v = vlage.get(zid)
            ispravan = self._senzor_ispravan(z, v)
            if ispravan and v >= z.prag:
                z.preskoceno = False
            if ispravan and v < z.prag:
                if kisa >= self.cfg["kisa_preskoci_mm"]:
                    if not z.preskoceno:  # jednom po sušnoj epizodi
                        self.ustedjeno_min += min(self.cfg["max_minuta"], (z.cilj - v) / max(0.1, z.vlazenje_po_min))
                        z.preskoceno = True
                    return {"pumpa": False, "ventil": None, "razlog": f"{zid}: suho, ali stiže {kisa:.1f} mm kiše"}
                hitno = v < z.prag - 8
                jutro = 5 <= sat <= 8
                if povoljno_sada or jutro or hitno:
                    return self._pokreni(zid, ts, v)
            elif not ispravan and ts - z.zadnje_zalijevanje > 44 * 3600 and 5 <= sat <= 7 and kisa < 1:
                return self._pokreni(zid, ts, v or 0.0) | {"razlog": f"{zid}: senzor neispravan – sigurni raspored"}
        return {"pumpa": False, "ventil": None, "razlog": "vlaga u redu"}

    def _pokreni(self, zid: str, ts: float, v: float) -> dict:
        self.aktivna, self.pocetak, self.pocetna_vlaga = zid, ts, v
        return {"pumpa": True, "ventil": zid, "razlog": f"{zid}: vlaga {v:.0f} % – zalijevam"}

    def potrebna_energija_kwh(self, sati: int = 24) -> float:
        """Procjena energije pumpe za sljedećih `sati` (ulaz optimizatoru)."""
        min_ukupno = 0.0
        for z in self.zone.values():
            if z.zadnja_vlaga is None:
                continue
            buduca = z.zadnja_vlaga - z.susenje_po_h * sati
            if buduca < z.prag:
                min_ukupno += min(self.cfg["max_minuta"], (z.cilj - buduca) / max(0.1, z.vlazenje_po_min))
        return min_ukupno / 60 * self.cfg["pumpa_kw"]
