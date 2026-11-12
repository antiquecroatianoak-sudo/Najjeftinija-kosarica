"""Planiranje potrošnje i skladištenja za sljedećih 24–48 h.

1. Fleksibilna trošila (bojler, pumpa) smještaju se u sate najniže granične cijene:
   višak sunca vrijedi koliko i izvozna cijena (to je propuštena zarada), inače kupovna cijena.
2. Baterija: dinamičko programiranje po razinama napunjenosti (41 razina) – minimizira
   trošak mreže + trošenje baterije (€/kWh protoka) + kaznu za neisporučenu energiju
   (otočni rad) + kaznu za pad ispod naučene noćne rezerve u 20 h.
   Punjenje iz mreže događa se samo kad se isplati i nakon trošenja baterije.
3. `osnovni_scenarij` računa isto razdoblje "bez pametnog upravljanja" (zadana vremena
   trošila, izmjenjivač u običnom vlastitom načinu rada) – to je usporedna osnovica za
   izvještaj o uštedi. Ušteda je zato procjena prema modelu, i tako je i označena.
"""
from __future__ import annotations

import time

RAZINE = 41
KAZNA_NEISPORUCENO = 2.0  # €/kWh – jače od svake tarife: otočni sustav prvo čuva opskrbu
KAZNA_REZERVA = 1.0       # €/kWh ispod rezerve u 20 h


def smjesti_fleksibilna(potrosnja_w: list[float], pv_w: list[float], cijene: list[dict],
                        zadaci: list[dict], soc0: float = 0.5, cfg: dict | None = None
                        ) -> tuple[list[float], dict[str, list[int]]]:
    """zadaci: {"id", "snaga_w", "energija_kwh", "od_h", "do_h"} (pomak od sada, do_h isključivo).

    Granični trošak sata h računa se simulacijom cijelog razdoblja s baterijom u vlastitom
    načinu rada: dodatnih 1 h trošila u satu h stoji koliko poraste ukupni trošak. Tako se
    vidi da energija iz baterije koju bi sunce ionako ponovno napunilo vrijedi samo
    izvoznu cijenu, a ne kupovnu. Bez cfg-a: jednostavno pravilo viška sunca.
    """
    ukupno = list(potrosnja_w)
    raspored: dict[str, list[int]] = {}

    def trosak(p: list[float]) -> float:
        return osnovni_scenarij(p, pv_w, cijene, soc0, cfg)["trosak_eur"] if cfg else 0.0

    for z in sorted(zadaci, key=lambda z: z["do_h"] - z["od_h"]):  # najuži prozor prvi
        sati_potrebno = max(0, round(z["energija_kwh"] * 1000 / max(1.0, z["snaga_w"])))
        odabrani: list[int] = []
        prozor = range(max(0, z["od_h"]), min(len(ukupno), z["do_h"]))
        for _ in range(sati_potrebno):
            baza = trosak(ukupno)
            najbolji = None
            for h in prozor:
                if h in odabrani:
                    continue
                if cfg:
                    ukupno[h] += z["snaga_w"]
                    granicni = trosak(ukupno) - baza
                    ukupno[h] -= z["snaga_w"]
                else:
                    visak = pv_w[h] - ukupno[h]
                    udio = min(1.0, max(0.0, visak / z["snaga_w"]))
                    granicni = udio * cijene[h]["prodaja"] + (1 - udio) * cijene[h]["kupnja"]
                if najbolji is None or granicni < najbolji[0] - 1e-9:
                    najbolji = (granicni, h)
            if najbolji is None:
                break
            odabrani.append(najbolji[1])
            ukupno[najbolji[1]] += z["snaga_w"]
        raspored[z["id"]] = sorted(odabrani)
    return ukupno, raspored


def planiraj_bateriju(potrosnja_w: list[float], pv_w: list[float], cijene: list[dict], soc0: float,
                      cfg: dict, rezerva_soc: float, od_ts: float, mreza: bool | None = None) -> list[dict]:
    b = cfg["baterija"]
    kap = b["kapacitet_kwh"]
    mreza = cfg["mreza"]["dostupna"] if mreza is None else mreza
    lo, hi = b["soc_min"], b["soc_max"]
    korak = (hi - lo) / (RAZINE - 1)
    razine = [lo + i * korak for i in range(RAZINE)]
    eta = 0.95
    max_k = b["max_punjenje_kw"] / kap / korak
    max_p = b["max_praznjenje_kw"] / kap / korak
    trosenje = b["trosak_ciklusa_eur_kwh"]
    H = len(potrosnja_w)
    INF = float("inf")
    sat_20 = [time.localtime(od_ts + h * 3600).tm_hour == 20 for h in range(H)]

    def trosak_sata(h: int, i: int, j: int) -> tuple[float, float]:
        de = (razine[j] - razine[i]) * kap  # kWh u bateriju (+) / iz baterije (-)
        neto = (potrosnja_w[h] - pv_w[h]) / 1000.0
        m = neto + (de / eta if de > 0 else de * eta)
        if mreza:
            c = m * cijene[h]["kupnja"] if m > 0 else m * cijene[h]["prodaja"]
            if m > cfg["mreza"]["max_uvoz_kw"]:
                c += (m - cfg["mreza"]["max_uvoz_kw"]) * KAZNA_NEISPORUCENO
        else:
            c = m * KAZNA_NEISPORUCENO if m > 0 else 0.0  # višak se ograničava
            if de > 0 and neto + de / eta > 1e-6 and m > 0:
                c += 10.0  # otočno: ne puniti bateriju energijom koje nema
        c += abs(de) * trosenje
        if sat_20[h] and razine[j] < rezerva_soc:
            c += (rezerva_soc - razine[j]) * kap * KAZNA_REZERVA
        return c, m

    start = min(range(RAZINE), key=lambda i: abs(razine[i] - min(hi, max(lo, soc0))))
    trosak = [[INF] * RAZINE for _ in range(H + 1)]
    prethodni = [[-1] * RAZINE for _ in range(H + 1)]
    trosak[0][start] = 0.0
    for h in range(H):
        for i in range(RAZINE):
            if trosak[h][i] == INF:
                continue
            for j in range(max(0, i - int(max_p)), min(RAZINE, i + int(max_k) + 1)):
                c, _ = trosak_sata(h, i, j)
                if trosak[h][i] + c < trosak[h + 1][j]:
                    trosak[h + 1][j] = trosak[h][i] + c
                    prethodni[h + 1][j] = i
    j = min(range(RAZINE), key=lambda k: trosak[H][k] - razine[k] * kap * 0.05)  # mala vrijednost ostatka
    put = [j]
    for h in range(H, 0, -1):
        j = prethodni[h][j]
        put.append(j)
    put.reverse()
    plan = []
    for h in range(H):
        c, m = trosak_sata(h, put[h], put[h + 1])
        de = (razine[put[h + 1]] - razine[put[h]]) * kap
        plan.append({"h": h, "ts": od_ts - od_ts % 3600 + h * 3600, "soc_cilj": round(razine[put[h + 1]], 3),
                     "baterija_kw": round(de, 3), "mreza_kw": round(m, 3), "trosak_eur": round(c, 4)})
    return plan


def osnovni_scenarij(potrosnja_w: list[float], pv_w: list[float], cijene: list[dict], soc0: float,
                     cfg: dict, mreza: bool | None = None) -> dict:
    """Bez pametnog upravljanja: baterija puni samo iz viška i prazni se do soc_min (obični način)."""
    b = cfg["baterija"]
    kap, eta = b["kapacitet_kwh"], 0.95
    mreza = cfg["mreza"]["dostupna"] if mreza is None else mreza
    soc, trosak, protok, neisporuceno = soc0, 0.0, 0.0, 0.0
    for h in range(len(potrosnja_w)):
        neto = (potrosnja_w[h] - pv_w[h]) / 1000.0
        if neto < 0:
            u = min(-neto * eta, (b["soc_max"] - soc) * kap, b["max_punjenje_kw"])
            soc += u / kap
            m = neto + u / eta
        else:
            iz = min(neto / eta, (soc - b["soc_min"]) * kap, b["max_praznjenje_kw"])
            soc -= iz / kap
            m = neto - iz * eta
            u = iz
        protok += u
        if mreza:
            trosak += m * cijene[h]["kupnja"] if m > 0 else m * cijene[h]["prodaja"]
        elif m > 0:
            neisporuceno += m
    return {"trosak_eur": trosak + protok * b["trosak_ciklusa_eur_kwh"], "neisporuceno_kwh": neisporuceno,
            "soc_kraj": soc}
