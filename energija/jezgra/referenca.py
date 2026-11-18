"""Generirani dio reference ULAZI_IZLAZI.md: naredbeni redak, postavke, API, kanali uređaja.

`python3 -m jezgra.referenca` ispisuje dio između oznaka; `--upisi` ga obnavlja u ULAZI_IZLAZI.md.
Test `test_ulazi.TestReferenca` pada ako dokument zaostaje za kodom – dokumentacija ne može zastarjeti.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

POCETAK = "<!-- generirano: python3 -m jezgra.referenca --upisi (ne uređivati ručno ispod) -->"
KRAJ = "<!-- kraj generiranog dijela -->"
DOKUMENT = Path(__file__).resolve().parent.parent / "ULAZI_IZLAZI.md"

# izlazi prema uređajima: kanal -> (vrijednost, značenje)
IZLAZI = [
    ("baterija_snaga_w", "W, + punjenje / − pražnjenje", "ručna ili planirana snaga baterije (SunSpec 124 InWRte/OutWRte)"),
    ("baterija_auto", "1", "izmjenjivač u vlastitom načinu rada (StorCtl_Mod = 0)"),
    ("baterija_ogranicenje", "bitovi 1 = bez punjenja, 2 = bez pražnjenja", "zabrana punjenja/pražnjenja (mraz, prenapon)"),
    ("izvoz_zabranjen", "0/1", "zabrana izvoza u mrežu"),
    ("rele_bojler", "0/1", "električni grijač spremnika"),
    ("rele_dizalica", "0/1", "dizalica topline (PTV)"),
    ("rele_pumpa", "0/1", "pumpa za navodnjavanje"),
    ("rele_uticnice", "0/1", "utičnice (nekritično)"),
    ("rele_hladnjak", "0/1", "hladnjak"),
    ("ventil_<zona>", "0/1", "ventil zone navodnjavanja"),
    ("pastir_snaga", "0–1", "udio snage aparata električnog pastira"),
    ("rele_pastir_k<k>", "0/1", "sklopka dionice ograde k (izolacija kvara)"),
    ("rele_pastir_povrat", "0/1", "povratni vod ograde (prsten)"),
    ("rele_pastir_punjenje", "0/1", "punjenje baterije aparata pastira"),
]

# ulazi s uređaja: kanal -> (jedinica, značenje); fizikalni raspon dolazi iz jezgra/ulazi.py
ULAZI = [
    ("pv_snaga_w", "W", "snaga sunčanih panela"),
    ("potrosnja_w", "W", "ukupna potrošnja"),
    ("mreza_snaga_w", "W", "snaga na priključku (+ uvoz)"),
    ("mreza_prisutna", "0/1", "ima li mrežnog napona"),
    ("mreza_uvoz_kwh", "kWh", "brojilo: uvoz (ukupno)"),
    ("mreza_izvoz_kwh", "kWh", "brojilo: izvoz (ukupno)"),
    ("baterija_soc", "0–1", "napunjenost baterije"),
    ("baterija_napon_v", "V", "napon baterije"),
    ("baterija_struja_a", "A", "struja baterije (+ punjenje)"),
    ("baterija_snaga_w", "W", "snaga baterije"),
    ("baterija_temp_c", "°C", "temperatura baterije"),
    ("okolina_temp_c", "°C", "vanjska temperatura"),
    ("bojler_temp_c", "°C", "temperatura vode u spremniku"),
    ("bojler_snaga_w", "W", "snaga grijača"),
    ("dizalica_snaga_w", "W", "snaga dizalice topline"),
    ("pumpa_struja_a", "A", "struja pumpe (rad na suho, blokada)"),
    ("tlo_<zona>_vlaga", "%", "vlaga tla po zoni"),
    ("pastir_v<k>_kv", "kV", "napon ograde na kraju dionice k (v0 = aparat)"),
    ("pastir_baterija_soc", "0–1", "baterija aparata pastira"),
    ("brojilo_impulsi", "broj", "LED impulsi brojila (optički adapter)"),
]


def _naredbeni_redak() -> list[str]:
    from .__main__ import parser
    ap_pomoc = [(", ".join(a.option_strings), a.metavar or ("|".join(a.choices) if a.choices else
                                                            "" if a.nargs == 0 else "VRIJEDNOST"), a.help or "")
                for a in parser()._actions if a.option_strings and a.dest != "help"]
    out = ["### Naredbeni redak (`python3 -m jezgra …`)", "", "| Opcija | Vrijednost | Značenje |", "|---|---|---|"]
    out += [f"| `{o}` | {m} | {h} |" for o, m, h in ap_pomoc]
    return out


def _postavke() -> list[str]:
    from . import konfig
    out = ["### Važne postavke (`--postavi kljuc=vrijednost`)", "",
           "Vrijednost izvan raspona, krivog tipa ili nepoznat ključ odbacuje se uz upozorenje "
           "(`--dijagnoza`, događaj „postavke”, `GET /api/v1/dijagnostika`); vrijedi zadana.", "",
           "| Ključ | Zadano | Jedinica | Raspon | Značenje |", "|---|---|---|---|---|"]
    for k, (jed, mn, mx, opis) in konfig.OPIS.items():
        raspon = f"{mn:g}–{mx:g}" if mn is not None else "–"
        out.append(f"| `{k}` | `{json.dumps(konfig._dohvati(konfig.ZADANO, k), ensure_ascii=False)}` | {jed} | "
                   f"{raspon} | {opis} |")
    out += ["", "Odnosi koji moraju vrijediti (inače se ti ključevi vraćaju na zadano):", ""]
    out += [f"- {poruka}" for _, poruka, _ in konfig.ODNOSI]
    out += ["", "Popisi kojima se provjerava i sadržaj: " + ", ".join(f"`{k}`" for k in konfig.SADRZAJ) + "."]
    return out


def _api() -> list[str]:
    from .api_v1 import RUTE, ULOGE
    out = ["### API v1 (HTTPS, token iz uparivanja; puna shema: `GET /api/v1/openapi.json`)", "",
           "| Metoda | Put | Opseg | Opis |", "|---|---|---|---|"]
    out += [f"| {m} | `{p}` | {o} | {opis.replace('|', chr(92) + '|')} |" for m, p, o, _, opis in RUTE]
    out += ["", "Uloge i opsezi: " + "; ".join(f"**{u}**: {', '.join(sorted(o))}" for u, o in ULOGE.items()) + ".",
            "", "Neispravan ulaz (tijelo koje nije JSON objekt, broj izvan raspona, NaN) vraća **400** s porukom; "
            "nepoznat put 404, kriva metoda 405, nedovoljna uloga 403."]
    return out


def _kanali() -> list[str]:
    from .ulazi import granice
    out = ["### Ulazi s uređaja (očitanja)", "",
           "Očitanje izvan fizikalnog raspona, NaN/beskonačno ili SunSpec oznaka „nije dostupno” se odbacuje "
           "(kao da kanal nije javljen) i prikazuje u dijagnostici (`odbacena_ocitanja`).", "",
           "| Kanal | Jedinica | Fizikalni raspon | Značenje |", "|---|---|---|---|"]
    for k, jed, opis in ULAZI:
        g = granice(k.replace("<zona>", "z").replace("<k>", "0"))
        out.append(f"| `{k}` | {jed} | {f'{g[0]:g} … {g[1]:g}' if g else 'konačan broj'} | {opis} |")
    out += ["", "### Izlazi prema uređajima (naredbe)", "", "| Kanal | Vrijednost | Značenje |", "|---|---|---|"]
    out += [f"| `{k}` | {v} | {opis} |" for k, v, opis in IZLAZI]
    return out


def generiraj() -> str:
    dijelovi = [_naredbeni_redak(), _postavke(), _api(), _kanali()]
    return "\n\n".join(["\n".join(d) for d in dijelovi]) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="jezgra.referenca")
    ap.add_argument("--upisi", action="store_true", help="obnovi generirani dio u ULAZI_IZLAZI.md")
    a = ap.parse_args(argv)
    tekst = generiraj()
    if not a.upisi:
        sys.stdout.write(tekst)
        return 0
    d = DOKUMENT.read_text("utf-8")
    pocetak, kraj = d.index(POCETAK) + len(POCETAK), d.index(KRAJ)
    DOKUMENT.write_text(d[:pocetak] + "\n\n" + tekst + "\n" + d[kraj:], "utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
