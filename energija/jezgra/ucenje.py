"""Lokalno kontinuirano učenje navika stanara (bez oblaka, bez ručnog programiranja).

Model je namjerno jednostavan i objašnjiv: za svaki dan u tjednu i sat (7 × 24) pamti se
EWMA potrošnje i vjerojatnost prisutnosti (potrošnja iznad osnovnog opterećenja). Stari
obrasci postupno blijede (zaboravljanje), pa se model sam prilagodi npr. ljetnom rasporedu
ili novom stanaru. Iz modela se izvode parametri automatizacije:

- prognoza potrošnje za sljedećih 48 h (ulaz optimizatoru),
- očekivani dolazak -> kada zagrijati bojler (topla voda spremna, bez grijanja prazne kuće),
- noćna rezerva baterije (90. percentil noćne potrošnje + pastir), da se baterija ne
  prazni ispod potrebnog, ali ni ne drži nepotrebno puna,
- osnovno opterećenje (za otkrivanje "zaboravljenih" trošila).
"""
from __future__ import annotations

import time

DANI, SATI = 7, 24


def _indeks(ts: float) -> tuple[int, int]:
    t = time.localtime(ts)
    return t.tm_wday, t.tm_hour


class Navike:
    def __init__(self, stanje: dict | None = None, alfa: float = 0.15):
        s = stanje or {}
        self.alfa = alfa
        self.potrosnja = s.get("potrosnja") or [[None] * SATI for _ in range(DANI)]
        self.prisutnost = s.get("prisutnost") or [[0.0] * SATI for _ in range(DANI)]
        self.osnova_w = s.get("osnova_w", 60.0)
        self.noci = s.get("noci", [])  # kWh potrošnje 20–7 h zadnjih noći
        self.uzoraka = s.get("uzoraka", 0)
        self.n_sati = s.get("n_sati") or [[0] * SATI for _ in range(DANI)]
        self._sat: dict | None = None
        self._noc_kwh = 0.0

    def stanje(self) -> dict:
        return {"potrosnja": self.potrosnja, "prisutnost": self.prisutnost, "osnova_w": self.osnova_w,
                "noci": self.noci, "uzoraka": self.uzoraka, "n_sati": self.n_sati}

    def dodaj(self, ts: float, potrosnja_w: float, dt_s: float) -> None:
        """Dodaj uzorak; satni prosjek se upisuje u model kad sat završi."""
        d, h = _indeks(ts)
        if self._sat is None or self._sat["kljuc"] != (d, h):
            if self._sat and self._sat["n"]:
                self._zakljuci_sat(*self._sat["kljuc"], self._sat["zbroj"] / self._sat["n"])
            self._sat = {"kljuc": (d, h), "zbroj": 0.0, "n": 0}
        self._sat["zbroj"] += potrosnja_w
        self._sat["n"] += 1
        # osnovno opterećenje: spori donji kvantil
        if potrosnja_w < self.osnova_w:
            self.osnova_w += 0.05 * (potrosnja_w - self.osnova_w)
        else:
            self.osnova_w += 0.0005 * (potrosnja_w - self.osnova_w)
        if h >= 20 or h < 7:
            self._noc_kwh += potrosnja_w * dt_s / 3.6e6
        elif h == 7 and self._noc_kwh > 0:
            self.noci.append(round(self._noc_kwh, 3))
            del self.noci[:-28]
            self._noc_kwh = 0.0
        self.uzoraka += 1

    def _zakljuci_sat(self, d: int, h: int, prosjek_w: float) -> None:
        self.n_sati[d][h] += 1
        a = max(self.alfa, 1.0 / self.n_sati[d][h])  # prva opažanja vrijede punom težinom
        staro = self.potrosnja[d][h]
        self.potrosnja[d][h] = prosjek_w if staro is None else staro + a * (prosjek_w - staro)
        prisutan = 1.0 if prosjek_w > max(150.0, 2.5 * self.osnova_w) else 0.0
        self.prisutnost[d][h] += a * (prisutan - self.prisutnost[d][h])

    # ------------------------------------------------------------------ izvedeni parametri
    def prognoza(self, od_ts: float, sati: int = 48) -> list[float]:
        out = []
        for i in range(sati):
            d, h = _indeks(od_ts + i * 3600)
            v = self.potrosnja[d][h]
            out.append(v if v is not None else max(self.osnova_w, 80.0))
        return out

    def dolasci(self, od_ts: float, sati: int = 48, prag: float = 0.5) -> list[int]:
        """Sati (pomak od sada) u kojima vjerojatnost prisutnosti prelazi prag nakon odsutnosti."""
        out, prije = [], None
        for i in range(sati):
            d, h = _indeks(od_ts + i * 3600)
            p = self.prisutnost[d][h] >= prag
            if prije is False and p:
                out.append(i)
            prije = p
        return out

    def parametri(self, od_ts: float, cfg: dict) -> dict:
        noc = sorted(self.noci)
        noc_p90 = noc[int(0.9 * (len(noc) - 1))] if noc else 1.5
        pastir_kwh = next((t["snaga_w"] for t in cfg["trosila"] if t["id"] == "pastir"), 8) * 11 / 1000
        kap = cfg["baterija"]["kapacitet_kwh"]
        rezerva = min(0.6, max(cfg["baterija"]["soc_min"], cfg["baterija"]["soc_min"] + (noc_p90 + pastir_kwh) / kap))
        dol = self.dolasci(od_ts)
        return {
            "rezerva_soc": round(rezerva, 3),
            "osnova_w": round(self.osnova_w, 1),
            "sljedeci_dolazak_h": dol[0] if dol else None,
            "bojler_spreman_do_h": dol[0] if dol else None,
            "prisutnost_sada": self.prisutnost[_indeks(od_ts)[0]][_indeks(od_ts)[1]],
            "naucenih_sati": sum(1 for d in self.potrosnja for v in d if v is not None),
        }
