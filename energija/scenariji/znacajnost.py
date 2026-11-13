"""Primjena unaprijed zadanog kriterija značajnosti (KRITERIJ_ZNACAJNOSTI.md) na rezultate usporedbe.

    python -m scenariji.znacajnost rezultati/usporedba.json
"""
from __future__ import annotations

import json
import statistics
import sys
from math import comb
from pathlib import Path

MIN_RASPON = 0.50
IZJEDNACENO = 0.02
PRAGOVI_K2 = {"neisporuceno_kwh": 0.01, "bez_tople_vode_min": 15, "stres_biljaka_h": 1.0}


def test_predznaka(bolje: int, losije: int) -> float:
    """Jednostrani egzaktni binomni test: P(X ≥ bolje | p = 0,5)."""
    n = bolje + losije
    if n == 0:
        return 1.0
    return sum(comb(n, k) for k in range(bolje, n + 1)) / 2 ** n


def analiziraj(r: dict) -> dict:
    redovi, delte, k2_krsenja = [], [], []
    for ime, x in r.items():
        v = x["strategije"]
        p = v["pametna"]
        konk = {k: s for k, s in v.items() if k != "pametna"}
        najbolji = min(konk, key=lambda k: konk[k]["trosak_eur"])
        b = konk[najbolji]
        # K2: usporedba s najboljim konkurentom (i sa svima za ogradu)
        for m, t in PRAGOVI_K2.items():
            if p[m] > b[m] + t:
                k2_krsenja.append(f"{ime}: {m} {p[m]} prema {b[m]} ({najbolji})")
        if (p["pastir"] or 0) < (b["pastir"] or 0) - 0.002:
            k2_krsenja.append(f"{ime}: ograda {p['pastir']:.3f} prema {b['pastir']:.3f}")
        if p["krsenja"] or p["iznimke"]:
            k2_krsenja.append(f"{ime}: sigurnosno kršenje/iznimka")
        # K1
        g, vl = p["granica_eur"], v["vlastita"]["trosak_eur"]
        red = {"scenarij": ime, "najbolji_konkurent": najbolji, "pametna_eur": p["trosak_eur"],
               "konkurent_eur": b["trosak_eur"], "razlika_eur": round(b["trosak_eur"] - p["trosak_eur"], 3)}
        if g is not None and vl - g >= MIN_RASPON:
            u_p = (vl - p["trosak_eur"]) / (vl - g)
            u_k = (vl - b["trosak_eur"]) / (vl - g)
            red.update({"U_pametna": round(u_p, 3), "U_konkurent": round(u_k, 3), "delta": round(u_p - u_k, 3)})
            delte.append(u_p - u_k)
        redovi.append(red)
    bolje = sum(1 for d in delte if d >= IZJEDNACENO)
    losije = sum(1 for d in delte if d <= -IZJEDNACENO)
    med = statistics.median(delte) if delte else None
    p_vr = test_predznaka(bolje, losije)
    k1 = med is not None and med >= 0.10 and p_vr < 0.05
    k2 = not k2_krsenja
    odluka = "USPJEŠNA" if k1 and k2 else "DJELOMIČNA" if (k1 or k2) else "NEUSPJEŠNA"
    return {"redovi": redovi, "K1": {"scenarija": len(delte), "medijan_delta": None if med is None else round(med, 3),
                                     "bolje": bolje, "losije": losije, "izjednaceno": len(delte) - bolje - losije,
                                     "p_vrijednost": round(p_vr, 4), "ispunjen": k1},
            "K2": {"krsenja": k2_krsenja, "ispunjen": k2}, "odluka": odluka}


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    put = Path(argv[0] if argv else "rezultati/usporedba.json")
    a = analiziraj(json.loads(put.read_text()))
    for red in a["redovi"]:
        d = red.get("delta")
        print(f"{red['scenarij']:28} vs {red['najbolji_konkurent']:14} razlika {red['razlika_eur']:+.2f} €"
              + (f"  ostvarivo {red['U_pametna']:.0%} prema {red['U_konkurent']:.0%}  Δ {d:+.0%}" if d is not None else
                 "  (izvan K1: bez granice ili raspon < 0,50 €)"))
    k1, k2 = a["K1"], a["K2"]
    print(f"\nK1: {k1['scenarija']} scenarija, medijan Δ = {k1['medijan_delta']:+.1%}, bolje {k1['bolje']} / lošije "
          f"{k1['losije']} / izjednačeno {k1['izjednaceno']}, p = {k1['p_vrijednost']} → "
          f"{'ISPUNJEN' if k1['ispunjen'] else 'NIJE ISPUNJEN'} (traži medijan ≥ +10 p.b. i p < 0,05)")
    print(f"K2: {'ISPUNJEN' if k2['ispunjen'] else 'NIJE ISPUNJEN'}" +
          ("" if k2["ispunjen"] else "\n  - " + "\n  - ".join(k2["krsenja"])))
    print(f"\nODLUKA: optimizacija {a['odluka']}")
    if len(argv) > 1:
        Path(argv[1]).write_text(json.dumps(a, indent=1, ensure_ascii=False))
    return 0 if a["odluka"] == "USPJEŠNA" else 1


if __name__ == "__main__":
    raise SystemExit(main())
