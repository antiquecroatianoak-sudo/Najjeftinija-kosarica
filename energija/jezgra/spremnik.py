"""Prediktivno upravljanje spremnikom tople vode (MPC): dizalica topline, električni grijač, legionela.

Model spremnika (jedan čvor, dovoljan za planiranje po satima):
    C · dT/dt = Q_dizalica + Q_grijač − UA · (T − T_prostorije) − Q_potrošnja
- C = volumen · 4,186 kJ/(L·K); UA (toplinski gubici, W/K) jezgra UČI iz mjerenja: kad nitko ne troši vodu i ništa
  ne grije, pad temperature je čisti gubitak,
- dizalica topline: električna snaga P, toplinska P · COP(T_vode, T_zraka); radi samo do `dt_max_c` (kompresor),
- električni grijač: COP = 1, do `grijac_max_c` (termostat); jedini može dosegnuti temperaturu protiv legionele.

Planer (dinamičko programiranje po temperaturi, 36 h):
- trošak = električna energija × granična cijena sata (višak sunca vrijedi samo izvoznu cijenu),
- udobnost: dok su stanari prisutni ili stižu, temperatura ne smije pasti ispod `t_min_c` (jaka kazna),
- prednost dizalici topline dolazi iz same cijene topline (cijena / COP); grijač se bira samo kad je nužan
  (legionela, iznad granice dizalice) ili kad je struja besplatna/negativna,
- predgrijavanje: spremnik se grije u jeftinim satima unaprijed, a model gubitaka kaže koliko se toga izgubi
  do trenutka potrošnje – zato se predgrijava samo kad se uz gubitke isplati,
- legionela: ciklus mora jedan sat držati vodu ≥ 60 °C najkasnije do roka; planer bira najjeftiniji sat.

Legionela (ciklički režim): svakih `period_dana` dana voda se zagrije na `cilj_c` (> 60 °C) i drži ≥ 60 °C barem
`drzanje_min` minuta. Ako potrošnja vode tijekom ciklusa spusti temperaturu ispod 60 °C, to NIJE kvar sustava:
pad se mjeri kao gubitak energije (kWh), bilježi se, a sljedeći ciklus nadoknađuje (viši cilj, novi rok unutar
24 h). Pad temperature nakon uspješnog ciklusa također se samo mjeri kao potrošena/izgubljena energija.
"""
from __future__ import annotations

import time

C_VODA_KWH_L_K = 4.186 / 3600  # kWh po litri i kelvinu
PRAG_LEGIONELE_C = 60.0
KAZNA_GRIJACA = 0.05  # €/kWh: prednost dizalici topline pred grijačem (osim za legionelu i besplatnu struju)


def cop(t_voda: float, t_zrak: float) -> float:
    """Približan COP dizalice topline za PTV (zrak–voda): pada s temperaturom vode, raste s temperaturom zraka."""
    return max(1.3, min(5.0, 4.2 - 0.055 * (t_voda - 30.0) + 0.04 * (t_zrak - 15.0)))


def zadano() -> dict:
    return {"volumen_l": 150.0, "ua_w_k": 1.5, "t_prostorije_c": 18.0, "t_min_c": 45.0,
            "dizalica_kw": 0.5, "dt_max_c": 55.0, "grijac_kw": 2.0, "grijac_max_c": 65.0,
            "legionela": {"period_dana": 7.0, "cilj_c": 62.0, "drzanje_min": 30.0, "nadoknada_max_c": 3.0}}


class ModelSpremnika:
    def __init__(self, cfg: dict, stanje: dict | None = None):
        self.p = cfg
        s = stanje or {}
        self.ua = s.get("ua_w_k", cfg["ua_w_k"])
        self.ua_uzoraka = s.get("ua_uzoraka", 0)
        self.potrosnja = s.get("potrosnja") or [[None] * 24 for _ in range(7)]  # kWh topline po satu (naučeno)
        self._zadnje: float | None = None
        self._sat: list | None = None
        self._mirno: list | None = None  # [početak, T na početku, ∫(T − T_prostorije) dt]

    @property
    def c_kwh_k(self) -> float:
        return self.p["volumen_l"] * C_VODA_KWH_L_K

    def stanje(self) -> dict:
        return {"ua_w_k": round(self.ua, 4), "ua_uzoraka": self.ua_uzoraka, "potrosnja": self.potrosnja}

    def gubitak_kw(self, t: float) -> float:
        return max(0.0, self.ua * (t - self.p["t_prostorije_c"]) / 1000.0)

    def korak(self, t: float, sati: float, dizalica: bool, grijac: bool, potrosnja_kwh: float,
              t_zrak: float) -> tuple[float, float]:
        """Temperatura nakon `sati` i utrošena električna energija (kWh). Termostati ograničavaju grijanje."""
        p = self.p
        c = p["volumen_l"] * C_VODA_KWH_L_K
        el = 0.0
        q = -potrosnja_kwh - max(0.0, self.ua * (t - p["t_prostorije_c"]) / 1000.0) * sati
        if dizalica and t < self.p["dt_max_c"]:
            k = cop(t, t_zrak)
            q_dt = self.p["dizalica_kw"] * k * sati
            q_dt = min(q_dt, max(0.0, (self.p["dt_max_c"] - t) * c + max(0.0, -q)))
            q += q_dt
            el += q_dt / k
        if grijac and t < self.p["grijac_max_c"]:
            q_g = min(self.p["grijac_kw"] * sati, max(0.0, (self.p["grijac_max_c"] - t) * c - q))
            q += q_g
            el += q_g
        return t + q / c, el

    # ------------------------------------------------------------------ učenje iz mjerenja
    def uci(self, ts: float, t: float | None, grije_kwh: float, dt_s: float, mirno: bool) -> None:
        """Gubici (UA) iz hlađenja bez grijanja i bez potrošnje; profil potrošnje iz energetske bilance.

        grije_kwh: toplina koju su dizalica i grijač predali vodi u ovom koraku; mirno: nitko nije prisutan."""
        if t is None:
            return
        if self._zadnje is not None and dt_s > 0:
            t0 = self._zadnje
            sati = dt_s / 3600
            dq = (t - t0) * self.c_kwh_k  # promjena topline u spremniku
            # gubici: hlađenje kroz mirno razdoblje (bez grijanja i bez potrošnje) od barem 3 h – osjetnik
            # zaokružuje na 0,1 °C, a gubitak u minuti je ~0,01 °C, pa kratki koraci ne nose informaciju
            if mirno and grije_kwh <= 0:
                if self._mirno is None:
                    self._mirno = [ts - dt_s, t0, 0.0]
                self._mirno[2] += (t - self.p["t_prostorije_c"]) * sati
                trajanje_h = (ts - self._mirno[0]) / 3600
                pad = self._mirno[1] - t
                if trajanje_h >= 3.0:
                    if 0.2 <= pad and self._mirno[2] > 0:
                        ua = pad * self.c_kwh_k * 1000 / self._mirno[2]  # W/K
                        if 0.2 < ua < 8.0:  # veći pad = netko je trošio vodu, ne gubitak
                            self.ua_uzoraka += 1
                            a = 1.0 / self.ua_uzoraka if self.ua_uzoraka < 20 else 0.05
                            self.ua += a * (ua - self.ua)
                    if trajanje_h >= 6.0 or pad >= 0.2:
                        self._mirno = None
            else:
                self._mirno = None
            potroseno = max(0.0, grije_kwh - self.gubitak_kw(t0) * sati - dq)  # toplina koju je odnijela voda
            lt = time.localtime(ts)
            kljuc = (lt.tm_wday, lt.tm_hour)
            if self._sat is None or self._sat[0] != kljuc:
                if self._sat is not None:
                    d, h = self._sat[0]
                    staro = self.potrosnja[d][h]
                    self.potrosnja[d][h] = self._sat[1] if staro is None else staro + 0.3 * (self._sat[1] - staro)
                self._sat = [kljuc, 0.0]
            self._sat[1] += potroseno
        self._zadnje = t

    def prognoza_potrosnje(self, od_ts: float, sati: int, prisutnost: list[bool]) -> list[float]:
        out = []
        for i in range(sati):
            lt = time.localtime(od_ts + i * 3600)
            v = self.potrosnja[lt.tm_wday][lt.tm_hour]
            if v is None:  # dok ne nauči: tipična potrošnja dok su stanari tu (~0,25 kWh topline po satu)
                v = 0.25 if prisutnost[i] else 0.0
            out.append(v)
        return out


class Legionela:
    """Ciklički režim > 60 °C; pad temperature zbog potrošnje = mjerljiv gubitak, nadoknađuje se sljedeći put."""

    def __init__(self, cfg: dict, stanje: dict | None = None, sada: float | None = None):
        self.p = cfg
        s = stanje or {}
        # novi sustav: prvi ciklus u prva 24 h (ne čeka cijeli period)
        self.zadnja = s.get("zadnja", (sada or time.time()) - (cfg["period_dana"] - 1.0) * 86400)
        self.drzanje_s = s.get("drzanje_s", 0.0)
        self.nadoknada_c = s.get("nadoknada_c", 0.0)
        self.gubitak_kwh = s.get("gubitak_kwh", 0.0)
        self.ciklusa = s.get("ciklusa", 0)
        self.prekinutih = s.get("prekinutih", 0)
        self.vrh_c: float | None = s.get("vrh_c")
        self.dogadjaji: list[dict] = []

    def stanje(self) -> dict:
        return {"zadnja": self.zadnja, "drzanje_s": self.drzanje_s, "nadoknada_c": self.nadoknada_c,
                "gubitak_kwh": round(self.gubitak_kwh, 3), "ciklusa": self.ciklusa, "prekinutih": self.prekinutih,
                "vrh_c": self.vrh_c}

    @property
    def cilj_c(self) -> float:
        return self.p["cilj_c"] + self.nadoknada_c

    def rok_h(self, ts: float) -> float:
        return max(0.0, (self.zadnja + self.p["period_dana"] * 86400 - ts) / 3600)

    def aktivno(self, ts: float) -> bool:
        """Ciklus u tijeku: rok je istekao (ili voda se upravo drži iznad 60 °C), a držanje nije dovršeno."""
        return self.rok_h(ts) <= 0 or self.drzanje_s > 0

    def korak(self, ts: float, dt: float, t: float | None, c_kwh_k: float) -> None:
        if t is None:
            return
        if t >= PRAG_LEGIONELE_C:
            self.vrh_c = max(self.vrh_c or t, t)
            if self.aktivno(ts) or self.drzanje_s > 0:
                self.drzanje_s += dt
                if self.drzanje_s >= self.p["drzanje_min"] * 60:
                    self.ciklusa += 1
                    self.zadnja = ts
                    self.dogadjaji.append({"vrsta": "legionela_ok", "poruka":
                                           f"Zaštita od legionele: voda ≥ 60 °C {self.p['drzanje_min']:.0f} min "
                                           f"(vrh {self.vrh_c:.1f} °C)"})
                    self.drzanje_s, self.nadoknada_c = 0.0, 0.0
        elif self.drzanje_s > 0:
            # potrošnja je spustila temperaturu prije kraja držanja: mjerljiv gubitak, ne kvar
            gubitak = (PRAG_LEGIONELE_C - t) * c_kwh_k + max(0.0, (self.vrh_c or PRAG_LEGIONELE_C) - PRAG_LEGIONELE_C) * c_kwh_k
            self.gubitak_kwh += gubitak
            self.prekinutih += 1
            self.nadoknada_c = min(self.p["nadoknada_max_c"], self.nadoknada_c + (PRAG_LEGIONELE_C - t))
            self.dogadjaji.append({"vrsta": "legionela_gubitak", "ozbiljnost": "info", "poruka":
                                   f"Ciklus legionele prekinut potrošnjom vode ({t:.1f} °C nakon "
                                   f"{self.drzanje_s / 60:.0f} min): izmjereni gubitak {gubitak:.2f} kWh, "
                                   f"nadoknada u sljedećem ciklusu (cilj {self.cilj_c:.1f} °C)"})
            self.drzanje_s = 0.0
            self.vrh_c = None
        elif self.vrh_c is not None and t < self.vrh_c - 5:
            # nakon uspješnog ciklusa: pad zbog potrošnje je potrošena/izgubljena toplina, ne greška
            self.gubitak_kwh += (self.vrh_c - t) * c_kwh_k
            self.vrh_c = None


def planiraj(model: ModelSpremnika, t0: float, cijene: list[dict], pv_visak_w: list[float], t_zraka: list[float],
             prisutnost: list[bool], potrosnja_kwh: list[float], legionela_rok_h: float | None,
             legionela_cilj_c: float = 62.0, mreza: bool = True, korak_c: float = 0.5) -> list[dict]:
    """Optimalan plan grijanja po satima (dinamičko programiranje nad temperaturom spremnika).

    Vraća po satu: {"dizalica": bool, "grijac": bool, "t_kraj": °C, "el_kwh": kWh, "legionela": bool}.
    """
    p = model.p
    H = len(cijene)
    lo, hi = 10.0, p["grijac_max_c"] + 1.0
    n = int((hi - lo) / korak_c) + 1

    def idx(t: float) -> int:
        return max(0, min(n - 1, round((t - lo) / korak_c)))

    def temp(i: int) -> float:
        return lo + i * korak_c

    def granicna(h: int, el_kw: float) -> float:
        c = cijene[h]
        if not mreza:  # otočno: višak sunca je besplatan, baterija je skupa (čuvaj je za kuću)
            return 0.0 if pv_visak_w[h] >= el_kw * 1000 else 0.5
        udio = min(1.0, max(0.0, pv_visak_w[h] / max(1.0, el_kw * 1000)))
        return udio * c["prodaja"] + (1 - udio) * c["kupnja"]

    akcije = [(False, False), (True, False), (False, True), (True, True)]
    INF = float("inf")
    rok = None if legionela_rok_h is None else int(legionela_rok_h)
    # stanje: (indeks temperature, legionela obavljena 0/1)
    trosak = [[[INF, INF] for _ in range(n)] for _ in range(H + 1)]
    put = [[[None, None] for _ in range(n)] for _ in range(H + 1)]
    i0 = idx(t0)
    trosak[0][i0][0] = 0.0
    prosjek = sum(c["kupnja"] for c in cijene) / max(1, H)
    cilj_leg = min(legionela_cilj_c, p["grijac_max_c"]) - 2
    for h in range(H):
        sada, sljedece, prije = trosak[h], trosak[h + 1], put[h + 1]
        kasni = rok is not None and h >= rok
        for i in range(n):
            if sada[i][0] == INF and sada[i][1] == INF:
                continue
            t = temp(i)
            # prijelazi ovise samo o temperaturi i akciji – računaju se jednom za oba stanja legionele
            for a, (dz, gr) in enumerate(akcije):
                if dz and t >= p["dt_max_c"] or gr and t >= p["grijac_max_c"]:
                    continue
                t1, el = model.korak(t, 1.0, dz, gr, potrosnja_kwh[h], t_zraka[h])
                g = granicna(h, el or 0.01)
                c = el * g
                if gr:
                    # prioritet dizalici topline: grijač je za legionelu, za temperature iznad granice dizalice
                    # i za besplatnu/negativnu struju; inače nosi kaznu prednosti (€/kWh)
                    gr_kwh = min(p["grijac_kw"], max(0.0, el - (p["dizalica_kw"] if dz else 0.0)))
                    if g > 0:
                        c += gr_kwh * KAZNA_GRIJACA
                if prisutnost[h] and min(t, t1) < p["t_min_c"]:
                    c += (p["t_min_c"] - min(t, t1)) * 0.25  # udobnost: €/K po satu
                drzi = min(t, t1) >= PRAG_LEGIONELE_C and t1 >= cilj_leg
                j = idx(t1)
                for leg in (0, 1):
                    c0 = sada[i][leg]
                    if c0 == INF:
                        continue
                    leg1 = leg or drzi
                    ck = c + 0.30 if kasni and not leg1 else c  # zakašnjeli ciklus: svaki sat odgode košta
                    if c0 + ck < sljedece[j][int(leg1)]:
                        sljedece[j][int(leg1)] = c0 + ck
                        prije[j][int(leg1)] = (i, leg, a, el)
    # završna vrijednost: toplina u spremniku na kraju vrijedi (oprezno) prosječnu cijenu topline
    najbolje, kraj = INF, None
    for i in range(n):
        for leg in (0, 1):
            c = trosak[H][i][leg]
            if c == INF:
                continue
            c -= (temp(i) - p["t_min_c"]) * model.c_kwh_k * prosjek / 3.0
            if rok is not None and rok < H and not leg:
                c += 5.0
            if c < najbolje:
                najbolje, kraj = c, (i, leg)
    plan: list[dict] = [{}] * H
    i, leg = kraj
    for h in range(H, 0, -1):
        pi, pleg, a, el = put[h][i][leg]
        dz, gr = akcije[a]
        plan[h - 1] = {"dizalica": dz, "grijac": gr, "t_kraj": round(temp(i), 1), "el_kwh": round(el, 3),
                       "legionela": bool(leg and not pleg)}
        i, leg = pi, pleg
    return plan
