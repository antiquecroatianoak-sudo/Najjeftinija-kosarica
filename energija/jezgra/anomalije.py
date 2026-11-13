"""Autonomna detekcija anomalija i prediktivno održavanje (bez oblaka, malo memorije).

Detektori po kanalu (O(1) memorija):
- statistički skok: EWMA srednja vrijednost/varijanca, |z| > prag nakon zagrijavanja,
- zaglavljen senzor: vrijednost se ne mijenja predugo na kanalu koji inače šumi,
- tvrde granice: sigurnosni pragovi baterije, pumpe, ograde (odmah, bez učenja),
- nefunkcionalni obrasci: pumpa radi na suho / blokirana, trošilo troši kad je isključeno,
  punjenje baterije na smrzavanju.

Prediktivno održavanje: dnevni pokazatelji zdravlja (unutarnji otpor baterije, omjer
proizvodnje panela i prognoze, struja pumpe, napon ograde) prate se linearnim trendom;
procjenjuje se broj dana do praga i otvara se zadatak održavanja.

Zaštita: kritična anomalija vraća popis trošila za preventivno isključenje – po
prioritetu, a električni pastir (prioritet 0) se nikad ne isključuje zbog štednje.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class Anomalija:
    kanal: str
    vrsta: str
    ozbiljnost: str  # "info" | "upozorenje" | "kriticno"
    poruka: str
    vrijednost: float | None = None
    trosila: list[str] = field(default_factory=list)  # što isključiti preventivno

    def kao_dict(self) -> dict:
        return self.__dict__.copy()


class StatKanal:
    __slots__ = ("alfa", "sredina", "var", "n", "zadnja", "nepromijenjeno_s", "raspon_sum")

    def __init__(self, alfa: float = 0.05):
        self.alfa = alfa
        self.sredina = 0.0
        self.var = 0.0
        self.n = 0
        self.zadnja: float | None = None
        self.nepromijenjeno_s = 0.0
        self.raspon_sum = 0.0

    def dodaj(self, x: float, dt: float) -> float:
        """Vrati z-vrijednost prije ažuriranja (da skok ne "proguta" sam sebe)."""
        if self.n == 0:
            self.sredina, self.n, self.zadnja = x, 1, x
            return 0.0
        z = (x - self.sredina) / math.sqrt(self.var) if self.var > 1e-9 else 0.0
        d = x - self.sredina
        self.sredina += self.alfa * d
        self.var = (1 - self.alfa) * (self.var + self.alfa * d * d)
        if self.zadnja is not None and abs(x - self.zadnja) < 1e-9:
            self.nepromijenjeno_s += dt
        else:
            self.raspon_sum += abs(x - (self.zadnja or x))
            self.nepromijenjeno_s = 0.0
        self.zadnja = x
        self.n += 1
        return z

    def stanje(self) -> dict:
        return {"s": self.sredina, "v": self.var, "n": self.n}

    @classmethod
    def iz_stanja(cls, d: dict) -> "StatKanal":
        k = cls()
        k.sredina, k.var, k.n = d["s"], d["v"], d["n"]
        return k


class Trend:
    """Linearni trend dnevnih vrijednosti (zadnjih ≤60 dana) -> dani do praga."""

    def __init__(self, tocke: list[list[float]] | None = None):
        self.tocke = tocke or []

    def dodaj(self, dan: float, v: float) -> None:
        self.tocke.append([dan, v])
        del self.tocke[:-60]

    def nagib(self) -> tuple[float, float] | None:
        """Theil–Sen: medijan nagiba svih parova točaka – otporan na šum i pojedinačne stršeće dane.
        Najmanje 7 dnevnih točaka, inače nema predviđanja (bolje šutjeti nego lažno uzbuniti)."""
        if len(self.tocke) < 7:
            return None
        nagibi = sorted((b[1] - a[1]) / (b[0] - a[0]) for i, a in enumerate(self.tocke)
                        for b in self.tocke[i + 1:] if abs(b[0] - a[0]) > 1e-9)
        if not nagibi:
            return None
        k = nagibi[len(nagibi) // 2]
        odsjecci = sorted(t[1] - k * t[0] for t in self.tocke)
        return k, odsjecci[len(odsjecci) // 2]

    def dana_do(self, prag: float, raste: bool) -> float | None:
        r = self.nagib()
        if r is None:
            return None
        k, l = r
        if (raste and k <= 0) or (not raste and k >= 0):
            return None
        zadnji = self.tocke[-1][0]
        dan = (prag - l) / k
        return max(0.0, dan - zadnji)


# kanali za koje "zaglavljen" ima smisla -> pratilac koji se u isto vrijeme mora mijenjati
# (mirna baterija smije imati stalan napon; senzor je zaglavljen tek ako struja teče, a napon stoji)
ZIVI_KANALI = {"baterija_napon_v": "baterija_struja_a", "baterija_temp_c": "baterija_struja_a",
               "pv_snaga_w": None, "potrosnja_w": None}


class Detektor:
    def __init__(self, cfg: dict, stanje: dict | None = None):
        self.cfg = cfg
        a = cfg["anomalije"]
        self.z_prag, self.zagrijavanje = a["z_prag"], a["zagrijavanje"]
        self.zaglavljen_s = a["zaglavljen_min"] * 60
        s = stanje or {}
        self.kanali: dict[str, StatKanal] = {k: StatKanal.iz_stanja(v) for k, v in s.get("kanali", {}).items()}
        self.trendovi: dict[str, Trend] = {k: Trend(v) for k, v in s.get("trendovi", {}).items()}
        self._r_uzorci: list[float] = []
        self._zadnje_v_i: tuple[float, float] | None = None
        self.aktivne: dict[str, Anomalija] = {}

    def stanje(self) -> dict:
        return {"kanali": {k: v.stanje() for k, v in self.kanali.items()},
                "trendovi": {k: v.tocke for k, v in self.trendovi.items()}}

    # ------------------------------------------------------------------ obrada
    def obradi(self, o: dict[str, float], dt: float, aktivni_releji: dict[str, bool] | None = None,
               temp_okolina: float | None = None) -> list[Anomalija]:
        nalazi: list[Anomalija] = []
        releji = aktivni_releji or {}
        for kanal, v in o.items():
            if v is None or not isinstance(v, (int, float)) or math.isnan(v):
                nalazi.append(Anomalija(kanal, "nema_ocitanja", "upozorenje", f"{kanal}: nema valjanog očitanja"))
                continue
            st = self.kanali.setdefault(kanal, StatKanal())
            z = st.dodaj(float(v), dt)
            if st.n > self.zagrijavanje and abs(z) > self.z_prag and not kanal.startswith(("rele_", "pastir_")):
                nalazi.append(Anomalija(kanal, "skok", "info", f"{kanal}: neuobičajena vrijednost (z={z:.1f})", v))
            pratilac = self.kanali.get(ZIVI_KANALI.get(kanal) or "")
            if (kanal in ZIVI_KANALI and st.nepromijenjeno_s > self.zaglavljen_s and st.raspon_sum > 0
                    and not (kanal == "pv_snaga_w" and v == 0)
                    and (ZIVI_KANALI[kanal] is None or (pratilac is not None and pratilac.nepromijenjeno_s < 600
                                                        and abs(o.get(ZIVI_KANALI[kanal], 0) or 0) > 1.0))):
                nalazi.append(Anomalija(kanal, "zaglavljen", "upozorenje",
                                        f"{kanal}: senzor se ne mijenja {st.nepromijenjeno_s / 60:.0f} min", v))
        nalazi += self._granice(o, releji, temp_okolina)
        self._otpor_baterije(o)
        self.aktivne = {f"{n.kanal}:{n.vrsta}": n for n in nalazi if n.ozbiljnost != "info"}
        return nalazi

    def _granice(self, o: dict, releji: dict, temp_okolina: float | None) -> list[Anomalija]:
        b = self.cfg["baterija"]
        out: list[Anomalija] = []
        t = o.get("baterija_temp_c")
        struja = o.get("baterija_struja_a", 0.0) or 0.0
        if t is not None:
            if t > b["temp_max_c"]:
                out.append(Anomalija("baterija_temp_c", "pregrijavanje", "kriticno",
                                     f"Baterija {t:.0f} °C – smanjujem opterećenje", t,
                                     trosila=["bojler", "pumpa", "uticnice"]))
            elif t < b["temp_punjenje_min_c"] and struja > 0.5:
                out.append(Anomalija("baterija_temp_c", "punjenje_na_hladnom", "kriticno",
                                     f"Punjenje na {t:.0f} °C oštećuje LiFePO4 – punjenje zaustavljeno", t))
        v = o.get("baterija_napon_v")
        if v is not None:
            n = b["celija_serija"]
            if v / n < b["celija_min_v"] - 0.1:
                out.append(Anomalija("baterija_napon_v", "podnapon", "kriticno",
                                     f"Napon ćelije {v / n:.2f} V – isključujem nekritična trošila", v,
                                     trosila=["bojler", "pumpa", "uticnice", "hladnjak"]))
            elif v / n > b["celija_max_v"] + 0.1:
                out.append(Anomalija("baterija_napon_v", "prenapon", "kriticno",
                                     f"Napon ćelije {v / n:.2f} V – punjenje zaustavljeno", v))
        # pumpa: radi na suho (premala struja) ili blokirana (prevelika)
        if releji.get("pumpa") and "pumpa_struja_a" in o:
            i = o["pumpa_struja_a"]
            nominal = self.kanali.get("pumpa_nominal", StatKanal()).sredina or 3.4
            if i < 0.45 * nominal:
                out.append(Anomalija("pumpa_struja_a", "rad_na_suho", "kriticno",
                                     f"Pumpa troši {i:.1f} A (očekivano ~{nominal:.1f} A) – nema vode? Isključena.",
                                     i, trosila=["pumpa"]))
            elif i > 1.6 * nominal:
                out.append(Anomalija("pumpa_struja_a", "blokada", "kriticno",
                                     f"Pumpa troši {i:.1f} A – moguća blokada. Isključena.", i, trosila=["pumpa"]))
            else:
                self.kanali.setdefault("pumpa_nominal", StatKanal(0.02)).dodaj(i, 0)
        # trošilo troši iako je relej isključen (kvar releja / curenje)
        for ime in ("bojler", "pumpa"):
            snaga = o.get(f"{ime}_snaga_w")
            if snaga is not None and not releji.get(ime, False) and snaga > 50:
                out.append(Anomalija(f"{ime}_snaga_w", "trosi_iskljuceno", "upozorenje",
                                     f"{ime}: troši {snaga:.0f} W iako je isključen – provjeriti relej", snaga))
        return out

    def _otpor_baterije(self, o: dict) -> None:
        """Procjena unutarnjeg otpora iz skokova struje (ΔV/ΔI) – pokazatelj starenja."""
        v, i = o.get("baterija_napon_v"), o.get("baterija_struja_a")
        if v is None or i is None:
            return
        if self._zadnje_v_i is not None:
            v0, i0 = self._zadnje_v_i
            di = i - i0
            if abs(di) > 10:
                r = abs((v - v0) / di)  # neovisno o konvenciji predznaka struje (BMS-ovi se razlikuju)
                if 0.0005 < r < 1:
                    self._r_uzorci.append(r)
                    del self._r_uzorci[:-200]
        self._zadnje_v_i = (v, i)

    # ------------------------------------------------------------------ prediktivno
    def dnevni_pokazatelji(self, dan: float, pokazatelji: dict[str, float]) -> None:
        if len(self._r_uzorci) >= 3:  # premalo skokova struje u danu = nepouzdana procjena, preskoči
            srt = sorted(self._r_uzorci)
            pokazatelji = dict(pokazatelji, baterija_otpor_mohm=srt[len(srt) // 2] * 1000)
        self._r_uzorci.clear()
        for k, v in pokazatelji.items():
            if v is not None:
                self.trendovi.setdefault(k, Trend()).dodaj(dan, v)

    PRAGOVI = {  # pokazatelj: (prag, raste, poruka)
        "baterija_otpor_mohm": (60.0, True, "Baterija stari (unutarnji otpor raste) – planirati provjeru/zamjenu"),
        "pv_omjer": (0.70, False, "Paneli daju manje od očekivanog – očistiti ili provjeriti zasjenjenje"),
        "pumpa_struja_a": (5.0, True, "Struja pumpe raste – provjeriti filtar/ležajeve"),
        "pastir_min_kv": (4.0, False, "Napon ograde polako pada – raste vegetacija ili slab izolator"),
    }

    def predvidi(self, horizont_dana: float = 60.0) -> list[dict]:
        zadaci = []
        for k, (prag, raste, poruka) in self.PRAGOVI.items():
            t = self.trendovi.get(k)
            if not t:
                continue
            d = t.dana_do(prag, raste)
            if d is not None and d <= horizont_dana:
                zadaci.append({"pokazatelj": k, "dana_do_praga": round(d, 1), "poruka": poruka,
                               "zadnja": round(t.tocke[-1][1], 3), "prag": prag,
                               "hitno": d <= 7})
        return sorted(zadaci, key=lambda z: z["dana_do_praga"])
