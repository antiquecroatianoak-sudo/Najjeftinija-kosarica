"""Automatski izvještaji o performansama – provjerljiv dokaz vrijednosti za kupca.

Svaki izvještaj (tjedni, mjesečni ili na zahtjev) izvozi se kao:
- JSON (kanonski, strojno čitljiv), CSV (satni podaci), HTML (za ispis / PDF iz preglednika),
- potpis Ed25519 nad SHA-256 kanonskog JSON-a + javni ključ jezgre. Kupac ili treća strana
  mogu provjeriti da brojke nisu naknadno mijenjane (`provjeri`).

Ušteda se računa usporedbom s osnovicom "isti uređaji bez pametnog upravljanja"
(baterija u običnom načinu, bojler na uobičajenom terminu 18–20 h, navodnjavanje na
fiksnom satu bez obzira na kišu). To je modelska procjena i tako je označena; izmjereni
podaci (uvoz, izvoz, proizvodnja) navedeni su odvojeno.
"""
from __future__ import annotations

import base64
import csv
import hashlib
import html
import io
import json
import time
from pathlib import Path

from .optimizator import osnovni_scenarij
from .sifra import provjeri_potpis


def _osnovica(sati: list[dict], cfg: dict) -> dict:
    if not sati:
        return {"trosak_eur": 0.0, "neisporuceno_kwh": 0.0, "uvoz_kwh": 0.0}
    potrosnja, pv, cijene = [], [], []
    po_danu: dict[str, dict] = {}
    for s in sati:
        d = time.strftime("%Y-%m-%d", time.localtime(s["ts"]))
        x = po_danu.setdefault(d, {"bojler": 0.0, "pumpa": 0.0, "preskoceno_min": 0.0})
        x["bojler"] += s.get("bojler_kwh", 0.0)
        x["pumpa"] += s.get("pumpa_kwh", 0.0)
        x["preskoceno_min"] += s.get("preskoceno_min", 0.0)
    pumpa_kw = cfg["navodnjavanje"]["pumpa_kw"]
    for s in sati:
        lt = time.localtime(s["ts"])
        d = time.strftime("%Y-%m-%d", lt)
        x = po_danu[d]
        osnova = (s["potrosnja_kwh"] - s.get("bojler_kwh", 0.0) - s.get("pumpa_kwh", 0.0)) * 1000
        if lt.tm_hour in (18, 19):
            osnova += x["bojler"] / 2 * 1000
        if lt.tm_hour == 7:
            osnova += (x["pumpa"] + x["preskoceno_min"] / 60 * pumpa_kw) * 1000
        potrosnja.append(osnova)
        pv.append(s.get("pv_moguce_kwh", s["pv_kwh"]) * 1000)
        cijene.append({"kupnja": s["cijena_kupnja"], "prodaja": s["cijena_prodaja"]})
    r = osnovni_scenarij(potrosnja, pv, cijene, sati[0].get("soc_pocetak", 0.5), cfg)
    # uvoz osnovice (za CO2): ponovi bez cijena
    jedinice = [{"kupnja": 1.0, "prodaja": 0.0} for _ in cijene]
    cfg_bez = json.loads(json.dumps(cfg))
    cfg_bez["baterija"]["trosak_ciklusa_eur_kwh"] = 0.0
    r["uvoz_kwh"] = osnovni_scenarij(potrosnja, pv, jedinice, sati[0].get("soc_pocetak", 0.5), cfg_bez)["trosak_eur"]
    return r


def sazetak(sati: list[dict], dogadjaji: list[dict], cfg: dict, od: float, do: float, meta: dict) -> dict:
    zbroj = lambda k: round(sum(s.get(k, 0.0) for s in sati), 3)  # noqa: E731
    pv, potr, uvoz, izvoz = zbroj("pv_kwh"), zbroj("potrosnja_kwh"), zbroj("uvoz_kwh"), zbroj("izvoz_kwh")
    trosak = zbroj("trosak_eur") + zbroj("bat_protok_kwh") * cfg["baterija"]["trosak_ciklusa_eur_kwh"]
    # usporedba na istoj osnovi kao osnovica: satni neto obračun mreže i satni neto protok baterije
    usporedivo = 0.0
    for s in sati:
        neto = s["uvoz_kwh"] - s["izvoz_kwh"]
        usporedivo += neto * (s["cijena_kupnja"] if neto > 0 else s["cijena_prodaja"])
        usporedivo += abs(s.get("bat_neto_kwh", s["bat_protok_kwh"])) * cfg["baterija"]["trosak_ciklusa_eur_kwh"]
    osn = _osnovica(sati, cfg)
    # energija koja na kraju razdoblja ostane u bateriji vrijedi (oprezno) izvoznu cijenu
    soc_kraj = next((s["soc_kraj"] for s in reversed(sati) if s.get("soc_kraj") is not None), None)
    korekcija = 0.0
    if soc_kraj is not None and sati:
        korekcija = (soc_kraj - osn["soc_kraj"]) * cfg["baterija"]["kapacitet_kwh"] * sati[-1]["cijena_prodaja"]
    usporedivo -= korekcija
    usteda = osn["trosak_eur"] - usporedivo
    co2 = cfg["izvjestaji"]["co2_kg_kwh"]
    izolacije = [d for d in dogadjaji if d["v"] == "pastir" and d["d"].get("vrsta") == "izolacija"]
    kvarovi_pastira = [d for d in dogadjaji if d["v"] == "pastir" and d["d"].get("vrsta") in ("kratki_spoj", "prekid")]
    zastite = [d for d in dogadjaji if d["v"] == "zastita"]
    anomalije = [d for d in dogadjaji if d["v"] == "anomalija"]
    dostupnost = [s["pastir_dostupnost"] for s in sati if s.get("pastir_dostupnost") is not None]
    return {
        "vrsta": "izvjestaj_performansi", "verzija": 1,
        "lokacija": cfg["lokacija"]["naziv"], "uredaj": meta.get("uredaj"),
        "razdoblje": {"od": od, "do": do, "sati_podataka": len(sati),
                      "od_tekst": time.strftime("%d.%m.%Y.", time.localtime(od)),
                      "do_tekst": time.strftime("%d.%m.%Y.", time.localtime(do))},
        "izmjereno": {
            "proizvodnja_pv_kwh": pv, "potrosnja_kwh": potr, "uvoz_kwh": uvoz, "izvoz_kwh": izvoz,
            "trosak_eur": round(trosak, 2), "neisporuceno_kwh": zbroj("neisporuceno_kwh"),
            "samoopskrba": round(1 - uvoz / potr, 3) if potr else None,
            "vlastita_potrosnja_pv": round(1 - izvoz / pv, 3) if pv else None,
            "baterija_protok_kwh": zbroj("bat_protok_kwh"),
            "baterija_ekv_ciklusa": round(zbroj("bat_protok_kwh") / (2 * cfg["baterija"]["kapacitet_kwh"]), 2),
        },
        "procjena_ustede": {
            "osnovica_eur": round(osn["trosak_eur"], 2), "s_upravljanjem_eur": round(usporedivo, 2),
            "usteda_eur": round(usteda, 2),
            "usteda_postotak": round(100 * usteda / osn["trosak_eur"], 1) if osn["trosak_eur"] > 0.5 else None,
            "co2_izbjegnuto_kg": round(max(0.0, osn["uvoz_kwh"] - uvoz) * co2, 1),
            "co2_iz_sunca_kg": round((pv - izvoz) * co2, 1),
            "napomena": "Procjena prema modelu: isti uređaji bez pametnog upravljanja (vidi metodologiju).",
        },
        "pouzdanost": {
            "pastir_dostupnost": round(sum(dostupnost) / len(dostupnost), 4) if dostupnost else None,
            "pastir_kvarova": len(kvarovi_pastira), "pastir_automatskih_izolacija": len(izolacije),
            "preventivnih_iskljucenja": len(zastite),
            "anomalija": {o: sum(1 for a in anomalije if a["d"].get("ozbiljnost") == o)
                          for o in ("upozorenje", "kriticno")},
            "sigurno_stanje_puta": sum(1 for d in dogadjaji if d["v"] == "sigurno_stanje"),
        },
        "voda": {"zalijevanje_min": round(zbroj("pumpa_min"), 1), "preskoceno_zbog_kise_min": round(zbroj("preskoceno_min"), 1)},
        "odrzavanje": meta.get("odrzavanje", []),
        "dogadjaji": [{"ts": d["t"], "vrsta": d["v"], "poruka": d["d"].get("poruka", "")}
                      for d in (kvarovi_pastira + izolacije + zastite)][:50],
        "satni_trosak": [[s["ts"], round(s["trosak_eur"], 4), round(s["pv_kwh"], 3), round(s["potrosnja_kwh"], 3)]
                         for s in sati],
        "metodologija": ("Izmjereni podaci zbrojeni su iz satnih zapisa jezgre. Oba scenarija obračunata su po satu "
                         "(neto mreža i neto protok baterije), da razlika u rezoluciji ne utječe na uštedu. "
                         "Razlika napunjenosti baterije na kraju razdoblja vrednuje se izvoznom cijenom. "
                         "Osnovica: ista potrošnja bez "
                         "fleksibilnih trošila, bojler 18–20 h, navodnjavanje u 7 h uključujući preskočena "
                         "zalijevanja, baterija u običnom načinu vlastite potrošnje. Trošenje baterije "
                         f"{cfg['baterija']['trosak_ciklusa_eur_kwh']} €/kWh protoka uključeno je u oba scenarija."),
        "izradjeno": time.time(),
    }


def kanonski(izv: dict) -> bytes:
    return json.dumps(izv, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def potpisi(izv: dict, trezor) -> dict:
    sazetak_h = hashlib.sha256(kanonski(izv)).digest()
    return {"sha256": sazetak_h.hex(), "potpis": base64.b64encode(trezor.potpisi(sazetak_h)).decode(),
            "javni_kljuc": trezor.javni_potpisni.hex(), "algoritam": "Ed25519(SHA-256(kanonski JSON))"}


def provjeri(izv: dict, potpis: dict) -> bool:
    h = hashlib.sha256(kanonski(izv)).digest()
    return h.hex() == potpis["sha256"] and provjeri_potpis(bytes.fromhex(potpis["javni_kljuc"]), h,
                                                         base64.b64decode(potpis["potpis"]))


def u_csv(izv: dict) -> str:
    out = io.StringIO()
    w = csv.writer(out, delimiter=";")
    w.writerow(["vrijeme", "trosak_eur", "pv_kwh", "potrosnja_kwh"])
    for ts, c, pv, p in izv["satni_trosak"]:
        w.writerow([time.strftime("%Y-%m-%d %H:00", time.localtime(ts)), f"{c:.4f}".replace(".", ","),
                    f"{pv:.3f}".replace(".", ","), f"{p:.3f}".replace(".", ",")])
    return out.getvalue()


def _broj(v, dec=1, suf="") -> str:
    if v is None:
        return "–"
    return f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".") + suf


def u_html(izv: dict, potpis: dict) -> str:
    m, u, p = izv["izmjereno"], izv["procjena_ustede"], izv["pouzdanost"]
    dani: dict[str, list[float]] = {}
    for ts, c, pv, _ in izv["satni_trosak"]:
        d = time.strftime("%d.%m.", time.localtime(ts))
        x = dani.setdefault(d, [0.0, 0.0])
        x[0] += pv
        x[1] += c
    maks = max([v[0] for v in dani.values()] + [0.1])
    stupci = []
    sirina = 600 / max(1, len(dani))
    for i, (d, (pv, _)) in enumerate(dani.items()):
        h = 120 * pv / maks
        stupci.append(f'<rect x="{i * sirina + 4:.1f}" y="{130 - h:.1f}" width="{max(2, sirina - 8):.1f}" '
                      f'height="{h:.1f}" rx="3" fill="var(--naglasak)"><title>{d}: {pv:.1f} kWh</title></rect>'
                      f'<text x="{i * sirina + sirina / 2:.1f}" y="148" text-anchor="middle">{d}</text>')
    odr = "".join(f"<li>{html.escape(z['poruka'])} – za ~{_broj(z['dana_do_praga'], 0)} dana</li>"
                  for z in izv["odrzavanje"]) or "<li>Nema predviđenih zahvata.</li>"
    dog = "".join(f"<li><time>{time.strftime('%d.%m. %H:%M', time.localtime(d['ts']))}</time> "
                  f"{html.escape(d['poruka'])}</li>" for d in izv["dogadjaji"][:12]) or "<li>Bez kvarova.</li>"
    dost = p["pastir_dostupnost"]
    return f"""<!doctype html><html lang="hr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Izvještaj o učinku</title>
<style>
:root{{--pozadina:#f6f5f2;--kartica:#fff;--tekst:#1b1c1e;--blago:#6b6e73;--naglasak:#1f7a5c;--rub:#e4e2dd}}
@media (prefers-color-scheme:dark){{:root{{--pozadina:#121314;--kartica:#1b1c1e;--tekst:#ececea;--blago:#9a9ca0;--naglasak:#4cc79a;--rub:#2a2c2f}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--pozadina);color:var(--tekst);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:860px;margin:0 auto;padding:32px 16px}}h1{{font-weight:600;font-size:22px;margin:0}}
.blago{{color:var(--blago)}}.glavno{{font-size:56px;font-weight:600;letter-spacing:-.02em;color:var(--naglasak);margin:24px 0 0}}
.mreza{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:24px 0}}
.k{{background:var(--kartica);border:1px solid var(--rub);border-radius:14px;padding:16px}}.k b{{display:block;font-size:22px;font-weight:600}}
svg{{width:100%;height:auto}}svg text{{font-size:10px;fill:var(--blago)}}ul{{padding-left:18px}}time{{color:var(--blago);margin-right:6px}}
footer{{margin-top:32px;font-size:12px;color:var(--blago);word-break:break-all}}@media print{{body{{background:#fff}}}}
</style></head><body><main>
<h1>Izvještaj o učinku · {html.escape(izv['lokacija'])}</h1>
<div class="blago">{izv['razdoblje']['od_tekst']} – {izv['razdoblje']['do_tekst']} · {izv['razdoblje']['sati_podataka']} sati podataka</div>
<p class="glavno">{_broj(u['usteda_eur'], 2, ' €')}</p>
<div class="blago">procijenjena ušteda u odnosu na iste uređaje bez upravljanja ({_broj(u['usteda_postotak'], 1, ' %')})</div>
<div class="mreza">
<div class="k"><span class="blago">Proizvodnja sunca</span><b>{_broj(m['proizvodnja_pv_kwh'], 1, ' kWh')}</b></div>
<div class="k"><span class="blago">Samoopskrba</span><b>{_broj((m['samoopskrba'] or 0) * 100, 0, ' %')}</b></div>
<div class="k"><span class="blago">Uvoz iz mreže</span><b>{_broj(m['uvoz_kwh'], 1, ' kWh')}</b></div>
<div class="k"><span class="blago">Trošak energije</span><b>{_broj(m['trosak_eur'], 2, ' €')}</b></div>
<div class="k"><span class="blago">CO₂ izbjegnuto upravljanjem</span><b>{_broj(u['co2_izbjegnuto_kg'], 1, ' kg')}</b></div>
<div class="k"><span class="blago">Pastir ispravan</span><b>{_broj((dost or 0) * 100, 2, ' %') if dost is not None else '–'}</b></div>
<div class="k"><span class="blago">Automatske izolacije kvara</span><b>{p['pastir_automatskih_izolacija']}</b></div>
<div class="k"><span class="blago">Preskočeno zalijevanje (kiša)</span><b>{_broj(izv['voda']['preskoceno_zbog_kise_min'], 0, ' min')}</b></div>
</div>
<div class="k"><span class="blago">Dnevna proizvodnja (kWh)</span>
<svg viewBox="0 0 600 152" role="img" aria-label="Dnevna proizvodnja">{''.join(stupci)}</svg></div>
<div class="mreza"><div class="k"><span class="blago">Predviđeno održavanje</span><ul>{odr}</ul></div>
<div class="k"><span class="blago">Kvarovi i automatske reakcije</span><ul>{dog}</ul></div></div>
<p class="blago">{html.escape(u['napomena'])} {html.escape(izv['metodologija'])}</p>
<footer>Potpisano lokalnom jezgrom {html.escape(str(izv.get('uredaj')))} · {html.escape(potpis['algoritam'])}<br>
SHA-256: {potpis['sha256']}<br>Javni ključ: {potpis['javni_kljuc']}<br>Potpis: {html.escape(potpis['potpis'])}</footer>
</main></body></html>"""


def izvezi(izv: dict, trezor, mapa: Path, ime: str) -> dict[str, Path]:
    mapa = Path(mapa)
    mapa.mkdir(parents=True, exist_ok=True)
    potpis = potpisi(izv, trezor)
    datoteke = {
        "json": mapa / f"{ime}.json", "csv": mapa / f"{ime}.csv",
        "html": mapa / f"{ime}.html", "potpis": mapa / f"{ime}.potpis.json",
    }
    datoteke["json"].write_bytes(kanonski(izv))
    datoteke["csv"].write_text(u_csv(izv), encoding="utf-8")
    datoteke["html"].write_text(u_html(izv, potpis), encoding="utf-8")
    datoteke["potpis"].write_text(json.dumps(potpis, indent=1))
    return datoteke
