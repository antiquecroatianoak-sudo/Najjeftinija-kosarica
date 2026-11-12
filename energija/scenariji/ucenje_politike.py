"""Učenje politike upravljanja na simulatorima (bez stvarne lokacije).

Što se uči: nekoliko parametara politike koje jezgra ne može sama naučiti iz navika jedne
lokacije, jer ovise o ekonomiji i rizicima koji se rijetko pojavljuju:
  - cuvanje_faktor:      koliko agresivno kupovati iz mreže i "čuvati" bateriju za skuplje sate
                         (0 = nikad; 1 = točno na granici isplativosti),
  - rezerva_dodatak:     sigurnosni dodatak na naučenu noćnu rezervu baterije,
  - trosak_ciklusa_plan: trošenje baterije koje vidi planer (mjerilo ostaje stvarna procjena).

Kako: koordinatni spust po mreži vrijednosti na skupu za učenje (scenariji s oznakom "ucenje"),
grubim korakom simulacije radi brzine. Rezultat se zatim potvrđuje na ODVOJENIM tjednima
(drugo vrijeme, druge tarife) finim korakom. Naučena politika predlaže se samo ako je na
skupu za provjeru bolja od zadane I bez ijednog sigurnosnog kršenja. Ishod se zapisuje s
podrijetlom (scenariji, rezultati, datum), da se može ponoviti i provjeriti.

Ograničenje: politika je optimalna u simulatoru. Na stvarnoj lokaciji vrijede njezini
stvarni podaci – zato jezgra i dalje mjeri uštedu prema osnovici i to prikazuje.

    python -m scenariji.ucenje_politike --izlaz naucena_politika.json
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import time
from pathlib import Path

from .katalog import KATALOG, PROVJERA_UCENJA
from .pokretac import pokreni

PROSTOR = {
    "cuvanje_faktor": [0.0, 0.8, 0.9, 1.0, 1.1],
    "rezerva_dodatak": [0.0, 0.05, 0.10],
    "trosak_ciklusa_plan": [0.01, 0.03, 0.06],
}
ZADANO = {"cuvanje_faktor": 1.0, "rezerva_dodatak": 0.0, "trosak_ciklusa_plan": 0.03}


def ocjena(rezultati: list[dict]) -> tuple[float, dict]:
    """Prosječna ušteda kao udio osnovice; sigurnost ima apsolutnu prednost (velika kazna)."""
    udjeli, kazna = [], 0.0
    for r in rezultati:
        k = r["kpi"]
        udjeli.append(k["usteda_udio"] if k["usteda_udio"] is not None else 0.0)
        kazna += 10.0 * k["krsenja"] + 10.0 * k["iznimke"] + 2.0 * k["neisporuceno_kwh"]
        if k["pastir_dostupnost"] is not None and k["pastir_dostupnost"] < 0.95:
            kazna += 5.0
    prosjek = sum(udjeli) / len(udjeli)
    return prosjek - kazna, {"prosjecna_usteda_udio": round(prosjek, 4), "kazna": kazna,
                             "po_scenariju": {r["scenarij"]: r["kpi"]["usteda_udio"] for r in rezultati}}


def procijeni(politika: dict, scenariji, korak_s: float | None = None) -> tuple[float, dict, list[dict]]:
    sc = [dataclasses.replace(s, korak_s=korak_s) if korak_s else s for s in scenariji]
    rez = [pokreni(s, {"politika": dict(politika)}) for s in sc]
    o, d = ocjena(rez)
    return o, d, rez


def uci(korak_ucenja: float = 300.0, prolaza: int = 2, ispis: bool = True) -> dict:
    ucenje = [s for s in KATALOG if "ucenje" in s.oznake]
    t0 = time.time()
    najbolja = dict(ZADANO)
    najbolja_ocjena, _, _ = procijeni(najbolja, ucenje, korak_ucenja)
    povijest = [{"politika": dict(najbolja), "ocjena": round(najbolja_ocjena, 4)}]
    if ispis:
        print(f"zadano: {najbolja_ocjena:+.4f}", flush=True)
    for prolaz in range(prolaza):
        promjena = False
        for param, vrijednosti in PROSTOR.items():
            for v in vrijednosti:
                if v == najbolja[param]:
                    continue
                kandidat = dict(najbolja, **{param: v})
                o, _, _ = procijeni(kandidat, ucenje, korak_ucenja)
                povijest.append({"politika": kandidat, "ocjena": round(o, 4)})
                if ispis:
                    print(f"  prolaz {prolaz + 1} {param}={v}: {o:+.4f}", flush=True)
                if o > najbolja_ocjena + 0.002:  # mali prag: ne mijenjaj zbog šuma
                    najbolja, najbolja_ocjena, promjena = kandidat, o, True
        if not promjena:
            break

    # potvrda na odvojenim tjednima, finim korakom
    o_zad, d_zad, rez_zad = procijeni(ZADANO, PROVJERA_UCENJA)
    o_nau, d_nau, rez_nau = procijeni(najbolja, PROVJERA_UCENJA)
    krsenja = sum(r["kpi"]["krsenja"] + r["kpi"]["iznimke"] for r in rez_nau)
    prihvaceno = o_nau > o_zad and krsenja == 0
    return {
        "postavke": {"politika": najbolja if prihvaceno else dict(ZADANO)},
        "prihvaceno": prihvaceno,
        "razlog": ("bolja od zadane na odvojenim tjednima, bez sigurnosnih kršenja" if prihvaceno else
                   "nije bolja od zadane na odvojenim tjednima (ili ima kršenja) – zadržana zadana politika"),
        "ucenje": {"scenariji": [s.ime for s in ucenje], "korak_s": korak_ucenja,
                   "najbolja": najbolja, "ocjena": round(najbolja_ocjena, 4), "povijest": povijest},
        "provjera": {"scenariji": [s.ime for s in PROVJERA_UCENJA], "zadano": d_zad, "naucena": d_nau,
                     "krsenja_naucene": krsenja},
        "napomena": "Optimalno u simulatoru; na stvarnoj lokaciji potvrditi izvještajem uštede prema osnovici.",
        "izradjeno": time.strftime("%Y-%m-%d %H:%M"), "trajanje_s": round(time.time() - t0),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Učenje politike upravljanja na simulatorima")
    ap.add_argument("--izlaz", type=Path, default=Path("naucena_politika.json"))
    ap.add_argument("--korak", type=float, default=300.0, help="korak simulacije pri učenju (s)")
    ap.add_argument("--prolaza", type=int, default=2)
    a = ap.parse_args(argv)
    r = uci(a.korak, a.prolaza)
    a.izlaz.write_text(json.dumps(r, indent=1, ensure_ascii=False))
    print(json.dumps({k: r[k] for k in ("postavke", "prihvaceno", "razlog")}, ensure_ascii=False))
    print("provjera zadano:", r["provjera"]["zadano"]["prosjecna_usteda_udio"],
          "naučena:", r["provjera"]["naucena"]["prosjecna_usteda_udio"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
