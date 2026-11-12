"""Rubni AI: kvantizirani (int8) model za prognozu opterećenja – ulaz optimizatoru baterije.

Namjerno malen i ograničen:
- samo ključni parametri: doba dana/tjedna, vikend, opterećenje prije 1 h / 24 h / 168 h,
  naučeni profil navika, temperatura i stupnjevi grijanja × aktivnost (10 ulaza),
- mreža 10 -> 8 (ReLU) -> 1 uči samo ISPRAVAK naučenog profila navika (rezidual), pa
  ne može "odlutati" daleko od provjerljive osnove; izlaz je ograničen,
- težine i aktivacije su int8, zbrojevi int32 (97 B težina); zaključivanje = 88 množenja,
- učenje (float, SGD) radi samo u načinu PRILIKA/NORMALNO, s vremenskim proračunom po
  pozivu, pa nikad ne zadržava upravljački ciklus; nakon učenja model se ponovno kvantizira,
- model se koristi SAMO ako je na zadnjih ≥48 h stvarno bolji (MAE) od profila navika,
  inače jezgra koristi profil. Ishod usporedbe vidljiv je u sučelju.

Odluke o bateriji i dalje donosi provjerljivi optimizator (dinamičko programiranje) uz sve
sigurnosne granice; AI samo poboljšava prognozu potrošnje koju optimizator dobiva.
"""
from __future__ import annotations

import math
import os
import time
from array import array

ULAZA, SKRIVENIH = 10, 8
MJERILO_W = 2000.0  # normalizacija snage
MAX_ISPRAVAK_W = 1500.0


# ------------------------------------------------------------------ resursi uređaja
def procijeni_resurse() -> dict:
    """Trenutačno zauzeće memorije i CPU-a na uređaju (proces, sustav i cgroup kontejnera)."""
    r = {"mem_dostupno_mb": None, "mem_ukupno_mb": None, "rss_mb": None, "cgroup_limit_mb": None,
         "cgroup_zauzeto_mb": None, "load1": None, "jezgri": os.cpu_count() or 1}
    try:
        with open("/proc/meminfo") as f:
            m = {l.split(":")[0]: int(l.split()[1]) for l in f if ":" in l}
        r["mem_dostupno_mb"] = m.get("MemAvailable", 0) / 1024
        r["mem_ukupno_mb"] = m.get("MemTotal", 0) / 1024
        with open("/proc/self/status") as f:
            for l in f:
                if l.startswith("VmRSS:"):
                    r["rss_mb"] = int(l.split()[1]) / 1024
    except (OSError, ValueError):
        pass
    for lim, upot in (("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory.current"),
                      ("/sys/fs/cgroup/memory/memory.limit_in_bytes", "/sys/fs/cgroup/memory/memory.usage_in_bytes")):
        try:
            with open(lim) as f:
                v = f.read().strip()
            with open(upot) as f:
                zauzeto = int(f.read())
            if v != "max" and int(v) < 1 << 50:
                r["cgroup_limit_mb"] = int(v) / 2 ** 20
            r["cgroup_zauzeto_mb"] = zauzeto / 2 ** 20
            break
        except (OSError, ValueError):
            continue
    try:
        r["load1"] = os.getloadavg()[0]
    except OSError:
        pass
    return r


def provjera_profila(r: dict | None = None, min_slobodno_mb: float = 32.0) -> dict:
    """Smije li se AI profil primijeniti? Uvijek s razlogom (prikazuje se korisniku)."""
    r = r or procijeni_resurse()
    razlozi = []
    slobodno = r["mem_dostupno_mb"]
    if r.get("cgroup_limit_mb") and r.get("cgroup_zauzeto_mb") is not None:
        cg = r["cgroup_limit_mb"] - r["cgroup_zauzeto_mb"]
        slobodno = cg if slobodno is None else min(slobodno, cg)
    if slobodno is None:
        razlozi.append("zauzeće memorije nije moguće izmjeriti")
    elif slobodno < min_slobodno_mb:
        razlozi.append(f"premalo slobodne memorije ({slobodno:.0f} MB < {min_slobodno_mb:.0f} MB)")
    if r["load1"] is not None and r["load1"] > 0.8 * r["jezgri"]:
        razlozi.append(f"procesor je zauzet (opterećenje {r['load1']:.2f} na {r['jezgri']} jezgre)")
    return {"dopusteno": not razlozi, "razlozi": razlozi, "slobodno_mb": None if slobodno is None else round(slobodno, 1),
            "resursi": {k: (round(v, 1) if isinstance(v, float) else v) for k, v in r.items()}, "vrijeme": time.time()}


# ------------------------------------------------------------------ kvantizacija
def _kvantiziraj(v: list[float]) -> tuple[array, float]:
    m = max((abs(x) for x in v), default=0.0) or 1e-6
    s = m / 127.0
    return array("b", [max(-127, min(127, round(x / s))) for x in v]), s


class RubniModel:
    """Kvantizirana (int8) ridge regresija ostatka profila navika – 10 ulaza + pomak = 11 B težina.

    Zašto linearni model, a ne mreža: na samo 7 dana satnih uzoraka (168) zatvoreno rješenje
    ridge regresije bilo je u provjeri na tjednu koji nije korišten za učenje točnije od male
    neuronske mreže učene SGD-om, a deterministično je, uči u mikrosekundama i ne može divergirati.
    Jačina regularizacije (λ) bira se na zadnjih 48 h koji nisu korišteni za učenje.
    """

    LAMBDE = (0.003, 0.01, 0.03, 0.1, 0.3, 1.0)

    def __init__(self, stanje: dict | None = None):
        s = stanje or {}
        self.w = s.get("w") or [0.0] * (ULAZA + 1)  # kreće točno od profila navika
        self.lam = s.get("lam")
        self.uzorci: list[list[float]] = s.get("uzorci", [])   # zadnjih 336 h: ulazi + cilj
        self.greske_ai: list[float] = s.get("greske_ai", [])
        self.greske_profil: list[float] = s.get("greske_profil", [])
        self.treniranja = s.get("treniranja", 0)
        self.temp_ref: float | None = s.get("temp_ref")  # EWMA temperature (~3 dana)
        self.zakljucivanja_ms: list[float] = []
        self._kvantiziraj_sve()

    def osvjezi_temp(self, temp: float | None) -> None:
        if temp is not None:
            self.temp_ref = temp if self.temp_ref is None else self.temp_ref + (temp - self.temp_ref) / 72

    def stanje(self) -> dict:
        return {"w": self.w, "lam": self.lam, "uzorci": self.uzorci[-336:], "greske_ai": self.greske_ai[-168:],
                "greske_profil": self.greske_profil[-168:], "treniranja": self.treniranja, "temp_ref": self.temp_ref}

    def _kvantiziraj_sve(self) -> None:
        self.q_w, self.s_w = _kvantiziraj(self.w[:ULAZA])
        self.q_b = round(self.w[ULAZA] / (self.s_w / 127.0))  # pomak u int32 na skali umnoška

    @staticmethod
    def kvantiziraj_ulaz(x: list[float]) -> array:
        return array("b", [max(-127, min(127, round(v * 127))) for v in x])

    def zakljuci(self, x: list[float]) -> float:
        """int8 × int8 -> int32 zbroj (10 množenja); vraća ispravak u W (ograničen)."""
        t0 = time.perf_counter()
        qx = self.kvantiziraj_ulaz(x)
        acc = self.q_b
        for i in range(ULAZA):
            acc += self.q_w[i] * qx[i]
        y = acc * self.s_w / 127.0 * MJERILO_W
        self.zakljucivanja_ms.append((time.perf_counter() - t0) * 1000)
        del self.zakljucivanja_ms[:-200]
        return max(-MAX_ISPRAVAK_W, min(MAX_ISPRAVAK_W, y))

    def _float(self, x: list[float]) -> tuple[float, None]:
        return self.w[ULAZA] + sum(self.w[i] * max(-1.0, min(1.0, x[i])) for i in range(ULAZA)), None

    def dodaj_uzorak(self, x: list[float], stvarno_w: float, profil_w: float) -> None:
        """Prije učenja: zapiši izvan-uzoračku pogrešku AI-ja i profila (pošteni test)."""
        pred_ai = profil_w + self.zakljuci(x)
        self.greske_ai.append(abs(pred_ai - stvarno_w))
        self.greske_profil.append(abs(profil_w - stvarno_w))
        del self.greske_ai[:-168], self.greske_profil[:-168]
        self.uzorci.append(list(x) + [(stvarno_w - profil_w) / MJERILO_W])
        del self.uzorci[:-336]

    @staticmethod
    def _ridge(uz: list[list[float]], lam: float) -> list[float] | None:
        n = ULAZA + 1
        X = [[max(-1.0, min(1.0, v)) for v in u[:ULAZA]] + [1.0] for u in uz]
        Y = [max(-0.75, min(0.75, u[ULAZA])) for u in uz]
        A = [[sum(x[i] * x[j] for x in X) + (lam * len(X) if i == j and i < ULAZA else 0.0) for j in range(n)]
             for i in range(n)]
        b = [sum(x[i] * y for x, y in zip(X, Y)) for i in range(n)]
        for i in range(n):  # Gauss s djelomičnim pivotiranjem (11×11)
            p = max(range(i, n), key=lambda r: abs(A[r][i]))
            if abs(A[p][i]) < 1e-12:
                return None
            A[i], A[p], b[i], b[p] = A[p], A[i], b[p], b[i]
            for r in range(i + 1, n):
                f = A[r][i] / A[i][i]
                A[r] = [a - f * c for a, c in zip(A[r], A[i])]
                b[r] -= f * b[i]
        w = [0.0] * n
        for i in reversed(range(n)):
            w[i] = (b[i] - sum(A[i][j] * w[j] for j in range(i + 1, n))) / A[i][i]
        return w

    def treniraj(self, proracun_ms: float = 40.0) -> int:
        """Zatvoreno rješenje na zadnjih 7 dana; λ po provjeri na zadnjih 48 h. Vraća broj uzoraka."""
        uz = self.uzorci[-168:]  # profil navika se mijenja: stariji ostaci su zastarjeli
        if len(uz) < 72:
            return 0
        t0 = time.perf_counter()
        uci, prov = uz[:-48], uz[-48:]
        najbolja = None
        for lam in self.LAMBDE:
            w = self._ridge(uci, lam)
            if w is None:
                continue
            mae = sum(abs(w[ULAZA] + sum(w[i] * max(-1.0, min(1.0, u[i])) for i in range(ULAZA)) - u[ULAZA])
                      for u in prov)
            if najbolja is None or mae < najbolja[0]:
                najbolja = (mae, lam)
            if (time.perf_counter() - t0) * 1000 > proracun_ms:
                break  # nikad ne zadržavaj upravljački ciklus
        if najbolja is None:
            return 0
        w = self._ridge(uz, najbolja[1])
        if w is not None:
            self.w, self.lam = w, najbolja[1]
            self.treniranja += 1
            self._kvantiziraj_sve()
        return len(uz)

    def kvaliteta(self) -> dict:
        n = len(self.greske_ai)
        mae_ai = sum(self.greske_ai) / n if n else None
        mae_p = sum(self.greske_profil) / n if n else None
        bolji = n >= 48 and mae_ai is not None and mae_p is not None and mae_ai < 0.95 * mae_p
        return {"sati_provjere": n, "mae_ai_w": None if mae_ai is None else round(mae_ai, 1),
                "mae_profil_w": None if mae_p is None else round(mae_p, 1), "koristi_se": bolji,
                "zakljucivanje_ms": round(sum(self.zakljucivanja_ms) / len(self.zakljucivanja_ms), 4)
                if self.zakljucivanja_ms else None,
                "tezine_bajtova": len(self.q_w) + 1, "lambda": self.lam, "uzoraka": len(self.uzorci)}


def ulazi(ts: float, lag1: float | None, lag24: float | None, lag168: float | None, profil: float,
          temp: float | None, temp_ref: float | None = None) -> list[float]:
    lt = time.localtime(ts)
    h, d = lt.tm_hour, lt.tm_wday
    k = lambda v: max(-1.0, min(1.0, (profil if v is None else v) / MJERILO_W))  # noqa: E731
    return [math.sin(2 * math.pi * h / 24), math.cos(2 * math.pi * h / 24),
            math.sin(2 * math.pi * d / 7), 1.0 if d >= 5 else -1.0,
            k(lag1), k(lag24), k(lag168), k(profil),
            max(-1.0, min(1.0, (temp if temp is not None else 12) / 30)),
            # (prosjek zadnjih dana − temperatura sada) × očekivana aktivnost: profil navika sadrži
            # PROSJEČNO grijanje, a ovo opisuje koliko je danas hladnije/toplije od tog prosjeka
            max(-1.0, min(1.0, ((temp_ref if temp_ref is not None else 12) - (temp if temp is not None else 12)) / 10
                          * min(1.0, max(0.0, k(profil)) * 3)))]
