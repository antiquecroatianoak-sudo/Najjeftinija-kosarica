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


def ocijeni_scenarij(v: dict) -> dict:
    p = v["pametna"]
    ref = {k: x for k, x in v.items() if k != "pametna"}
    najbolja_ref = min(ref, key=lambda k: ref[k]["trosak_eur"])
    nalazi = []
    if p["trosak_eur"] > ref[najbolja_ref]["trosak_eur"] + 0.01:
        nalazi.append(f"skuplje od '{najbolja_ref}' za {p['trosak_eur'] - ref[najbolja_ref]['trosak_eur']:.2f} €")
    if p["bez_tople_vode_min"] > min(x["bez_tople_vode_min"] for x in ref.values()) + 30:
        nalazi.append(f"manje udobno: {p['bez_tople_vode_min']} min bez tople vode")
    if p["stres_biljaka_h"] > min(x["stres_biljaka_h"] for x in ref.values()) + 2:
        nalazi.append(f"biljke pod stresom {p['stres_biljaka_h']} h")
    if (p["pastir"] or 0) < max((x["pastir"] or 0) for x in ref.values()) - 0.001:
        nalazi.append(f"manja pokrivenost ograde ({p['pastir']:.1%})")
    if p["krsenja"] or p["iznimke"]:
        nalazi.append("sigurnosno kršenje ili iznimka")
    if p["neisporuceno_kwh"] > min(x["neisporuceno_kwh"] for x in ref.values()) + 0.01:
        nalazi.append(f"više neisporučene energije ({p['neisporuceno_kwh']} kWh)")
    vl = v["vlastita"]["trosak_eur"]
    g = p["granica_eur"]
    udio = None
    if g is not None and vl - g > 0.05:
        udio = round((vl - p["trosak_eur"]) / (vl - g), 3)
    return {"strategije": v, "najbolja_referentna": najbolja_ref, "udio_ostvarivog": udio,
            "nalazi": nalazi, "pametna_najbolja": not nalazi}


def u_markdown(r: dict) -> str:
    red = ["| Scenarij | Pametna € | Vlastita € | ToU € | Cjenovni prag € | Granica € | Ostvareno od mogućeg | "
           "Ograda pod naponom (pametna / referentne) | Bez tople vode min (P/V) | Ishod |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for s, x in r.items():
        v = x["strategije"]
        trosak = {k: f"{v[k]['trosak_eur']:.2f}" for k in v}
        g = v["pametna"]["granica_eur"]
        granica = "–" if g is None else f"{g:.2f}"
        udio = "–" if x["udio_ostvarivog"] is None else f"{x['udio_ostvarivog']:.0%}"
        pastir_p = v["pametna"]["pastir"] or 0
        pastir_ref = min((v[k]["pastir"] or 0) for k in v if k != "pametna")
        ishod = "✓" if x["pametna_najbolja"] else "✗ " + "; ".join(x["nalazi"])
        red.append(f"| {s} | **{trosak['pametna']}** | {trosak['vlastita']} | {trosak['tou']} | "
                   f"{trosak['cjenovni_prag']} | {granica} | {udio} | {pastir_p:.1%} / {pastir_ref:.1%} | "
                   f"{v['pametna']['bez_tople_vode_min']} / {v['vlastita']['bez_tople_vode_min']} | {ishod} |")
    return "\n".join(red)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Usporedba s referentnim strategijama")
    ap.add_argument("--oznaka", default=None)
    ap.add_argument("--scenarij", action="append")
    ap.add_argument("--postavke", type=Path, help="naučena politika za pametnu strategiju")
    ap.add_argument("--izlaz", type=Path)
    a = ap.parse_args(argv)
    imena = a.scenarij or [s.ime for s in KATALOG if not a.oznaka or a.oznaka in s.oznake]
    politika = json.loads(a.postavke.read_text())["postavke"]["politika"] if a.postavke else None
    t0 = time.time()
    r = usporedi(imena, politika)
    md = u_markdown(r)
    print(md)
    losih = [s for s, x in r.items() if not x["pametna_najbolja"]]
    print(f"\nPametna najbolja u {len(r) - len(losih)}/{len(r)} scenarija ({time.time() - t0:.0f} s)."
          + (f" Nije: {', '.join(losih)}" if losih else ""))
    if a.izlaz:
        a.izlaz.mkdir(parents=True, exist_ok=True)
        (a.izlaz / "usporedba.json").write_text(json.dumps(r, indent=1, ensure_ascii=False))
        (a.izlaz / "usporedba.md").write_text(md + "\n")
    return 1 if losih else 0


if __name__ == "__main__":
    raise SystemExit(main())
