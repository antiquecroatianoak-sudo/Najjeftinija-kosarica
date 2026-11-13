"""Usporedba s referentnim strategijama kakve nude tipični sustavi na tržištu + teorijska granica.

Zašto referentne strategije, a ne „aplikacija X”: zatvoreni komercijalni sustavi ne objavljuju
rezultate pod jednakim uvjetima i ne mogu se pokrenuti u ovom simulatoru. Zato se uspoređuje s
ponašanjem koje takvi sustavi tipično nude prema javnoj dokumentaciji – na ISTIM scenarijima,
istom simulatoru i istom mjerilu troška:

  vlastita       – zadani način hibridnog izmjenjivača: baterija pokriva razliku sunca i potrošnje;
                   bojler na NT tajmeru; navodnjavanje na tajmeru u 7 h; bez nadzora ograde i pumpe
  tou            – kao vlastita + prisilno punjenje baterije iz mreže u jeftinoj tarifi (ToU raspored)
  cjenovni_prag  – dinamička tarifa: puni ispod 25. percentila cijena, čuva ispod medijana,
                   bojler u 3 najjeftinija sata
  pametna        – ova jezgra
  granica        – procjena: optimalna baterija uz savršeno znanje budućnosti (satni model, ista
                   potrošnja kao kod pametne) – koliko se uopće moglo postići

Trošak (niže = bolje) = satni neto obračun mreže + trošenje baterije − vrijednost promjene
napunjenosti na kraju. Uz trošak se uspoređuju udobnost (minute bez tople vode dok su stanari
tu, sati stresa biljaka) i pouzdanost (dostupnost pastira, neisporučena energija, kršenja).

    python -m scenariji.usporedba --oznaka ekstremno --izlaz rezultati/
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import time
from pathlib import Path

from .katalog import KATALOG, po_imenu

STRATEGIJE = {
    "pametna": {},
    "vlastita": {"strategija": "vlastita", "nadzor_pastira": False, "zastita_pumpe": False},
    "tou": {"strategija": "tou", "nadzor_pastira": False, "zastita_pumpe": False},
    "cjenovni_prag": {"strategija": "cjenovni_prag", "nadzor_pastira": False, "zastita_pumpe": False},
}


def _posao(arg):
    ime_sc, strategija, politika = arg
    from .pokretac import pokreni
    r = pokreni(po_imenu(ime_sc), {"politika": politika})
    k = r["kpi"]
    return ime_sc, strategija, {
        "trosak_eur": k["trosak_eur"], "granica_eur": k["granica_eur"], "pastir": k["pastir_pokrivenost"],
        "neisporuceno_kwh": k["neisporuceno_kwh"], "krsenja": k["krsenja"], "iznimke": k["iznimke"],
        "bez_tople_vode_min": k["bez_tople_vode_min"], "stres_biljaka_h": k["stres_biljaka_h"],
        "voda_min": k["voda_min"], "suho_koraka": k["suho_koraka_max"], "prosao": r["prosao"],
        "neuspjesi": r["neuspjesi"],
    }


def usporedi(scenariji: list[str], politika_pametne: dict | None = None, procesa: int | None = None) -> dict:
    poslovi = [(s, ime, dict(p, **(politika_pametne or {})) if ime == "pametna" else p)
               for s in scenariji for ime, p in STRATEGIJE.items()]
    with mp.get_context("spawn").Pool(procesa or mp.cpu_count()) as pool:
        rez = pool.map(_posao, poslovi)
    tablica: dict[str, dict] = {}
    for s, ime, k in rez:
        tablica.setdefault(s, {})[ime] = k
    return {s: ocijeni_scenarij(v) for s, v in tablica.items()}


# Mjerila (niže = bolje) i prag ispod kojeg se razlika smatra šumom simulacije
MJERILA = {"trosak_eur": 0.02, "bez_tople_vode_min": 15, "stres_biljaka_h": 1.0, "neisporuceno_kwh": 0.01,
           "ograda_bez_napona": 0.002}


def _vektor(x: dict) -> dict:
    return {"trosak_eur": x["trosak_eur"], "bez_tople_vode_min": x["bez_tople_vode_min"],
            "stres_biljaka_h": x["stres_biljaka_h"], "neisporuceno_kwh": x["neisporuceno_kwh"],
            "ograda_bez_napona": 1.0 - (x["pastir"] or 0.0)}


def _nadmasuje(a: dict, b: dict) -> bool:
    """a nadmašuje b: nije lošija ni po jednom mjerilu (uz prag šuma), a bolja je po barem jednom."""
    va, vb = _vektor(a), _vektor(b)
    nije_losija = all(va[k] <= vb[k] + t for k, t in MJERILA.items())
    bolja = any(va[k] < vb[k] - t for k, t in MJERILA.items())
    return nije_losija and bolja


def ocijeni_scenarij(v: dict) -> dict:
    """Višekriterijski (Pareto): trošak, topla voda, stres biljaka, neisporučeno, ograda pod naponom.

    - "dominira": pametna nadmašuje svaku referentnu strategiju,
    - "nenadmasena": nijedna referentna je ne nadmašuje, ali neka je bolja po nekom mjerilu (kompromis),
    - "nadmasena": neka referentna strategija je bolja ili jednaka po svemu.
    Sigurnosno kršenje ili iznimka uvijek znači neuspjeh.
    """
    p = v["pametna"]
    ref = {k: x for k, x in v.items() if k != "pametna"}
    najbolja_ref = min(ref, key=lambda k: ref[k]["trosak_eur"])
    nadmasuju = [k for k, x in ref.items() if _nadmasuje(x, p)]
    nalazi = []
    if p["krsenja"] or p["iznimke"]:
        nalazi.append("sigurnosno kršenje ili iznimka")
    if nadmasuju:
        nalazi.append(f"nadmašuje je: {', '.join(nadmasuju)}")
    if all(_nadmasuje(p, x) for x in ref.values()):
        ishod = "dominira"
    elif not nadmasuju:
        ishod = "nenadmasena"
    else:
        ishod = "nadmasena"
    kompromisi = []
    if ishod == "nenadmasena":
        for k, x in ref.items():
            vp, vx = _vektor(p), _vektor(x)
            bolje_ref = [m for m, t in MJERILA.items() if vx[m] < vp[m] - t]
            bolje_nas = [m for m, t in MJERILA.items() if vp[m] < vx[m] - t]
            if bolje_ref:
                kompromisi.append(f"{k} bolja u: {', '.join(bolje_ref)}; lošija u: {', '.join(bolje_nas) or '–'}")
    vl = v["vlastita"]["trosak_eur"]
    g = p["granica_eur"]
    udio = None
    if g is not None and vl - g > 0.05:
        udio = round((vl - p["trosak_eur"]) / (vl - g), 3)
    return {"strategije": v, "najbolja_referentna": najbolja_ref, "udio_ostvarivog": udio, "ishod": ishod,
            "kompromisi": kompromisi, "nalazi": nalazi, "pametna_najbolja": ishod != "nadmasena" and not nalazi}


def u_markdown(r: dict) -> str:
    red = ["| Scenarij | Pametna € | Vlastita € | ToU € | Cjenovni prag € | Granica € | Ostvareno od mogućeg | "
           "Ograda pod naponom (pametna / referentne) | Bez tople vode min (P/V) | Stres biljaka h (P/V) | Ishod |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for s, x in r.items():
        v = x["strategije"]
        trosak = {k: f"{v[k]['trosak_eur']:.2f}" for k in v}
        g = v["pametna"]["granica_eur"]
        granica = "–" if g is None else f"{g:.2f}"
        udio = "–" if x["udio_ostvarivog"] is None else f"{x['udio_ostvarivog']:.0%}"
        pastir_p = v["pametna"]["pastir"] or 0
        pastir_ref = min((v[k]["pastir"] or 0) for k in v if k != "pametna")
        oznaka = {"dominira": "✓ dominira", "nenadmasena": "✓ nenadmašena (" + "; ".join(x["kompromisi"]) + ")",
                  "nadmasena": "✗ " + "; ".join(x["nalazi"])}[x["ishod"]]
        ishod = oznaka if not x["nalazi"] or x["ishod"] == "nadmasena" else "✗ " + "; ".join(x["nalazi"])
        red.append(f"| {s} | **{trosak['pametna']}** | {trosak['vlastita']} | {trosak['tou']} | "
                   f"{trosak['cjenovni_prag']} | {granica} | {udio} | {pastir_p:.1%} / {pastir_ref:.1%} | "
                   f"{v['pametna']['bez_tople_vode_min']} / {v['vlastita']['bez_tople_vode_min']} | "
                   f"{v['pametna']['stres_biljaka_h']} / {v['vlastita']['stres_biljaka_h']} | {ishod} |")
    return "\n".join(red)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Usporedba s referentnim strategijama")
    ap.add_argument("--oznaka", default=None)
    ap.add_argument("--skup", choices=["katalog", "evaluacija", "evaluacija2", "razvoj_dinamicka"], default="katalog",
                    help="evaluacija = neovisni skup od 26 tjedana (pokreće se jednom, na kraju)")
    ap.add_argument("--scenarij", action="append")
    ap.add_argument("--postavke", type=Path, help="naučena politika za pametnu strategiju")
    ap.add_argument("--izlaz", type=Path)
    ap.add_argument("--ravnopravno", action="store_true",
                    help="konkurenti dobivaju isto jamstvo tople vode (usporedba samo upravljanja energijom)")
    a = ap.parse_args(argv)
    from .katalog import EVALUACIJA, EVALUACIJA_2, RAZVOJ_DINAMICKA
    skup = {"evaluacija": EVALUACIJA, "evaluacija2": EVALUACIJA_2, "razvoj_dinamicka": RAZVOJ_DINAMICKA}.get(a.skup, KATALOG)
    imena = a.scenarij or [s.ime for s in skup if not a.oznaka or a.oznaka in s.oznake]
    politika = json.loads(a.postavke.read_text())["postavke"]["politika"] if a.postavke else None
    t0 = time.time()
    if a.ravnopravno:
        for k in ("vlastita", "tou", "cjenovni_prag"):
            STRATEGIJE[k] = dict(STRATEGIJE[k], bojler_pravilo="udobnost")
    r = usporedi(imena, politika)
    md = u_markdown(r)
    print(md)
    losih = [s for s, x in r.items() if not x["pametna_najbolja"]]
    dom = sum(1 for x in r.values() if x["ishod"] == "dominira")
    print(f"\nPametna nenadmašena u {len(r) - len(losih)}/{len(r)} scenarija (od toga dominira u {dom}) "
          f"({time.time() - t0:.0f} s)."
          + (f" Nije: {', '.join(losih)}" if losih else ""))
    if a.izlaz:
        a.izlaz.mkdir(parents=True, exist_ok=True)
        (a.izlaz / "usporedba.json").write_text(json.dumps(r, indent=1, ensure_ascii=False))
        (a.izlaz / "usporedba.md").write_text(md + "\n")
    return 1 if losih else 0


if __name__ == "__main__":
    raise SystemExit(main())
