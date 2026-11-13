"""Pokretač scenarija: simulator + jezgra + mokani HTTP + čuvar sigurnosnih invarijanti + KPI.

    python -m scenariji.pokretac                 # svi scenariji iz kataloga
    python -m scenariji.pokretac --oznaka brzi   # podskup (CI)
    python -m scenariji.pokretac --scenarij zima_dinamicka --izlaz /tmp/rez

Mrežni pozivi idu STVARNIM kodom jezgre (urllib), a `urlopen` je zamijenjen mokom koji
poslužuje odgovore simulatora ili po rasporedu scenarija vraća pad mreže, HTTP 503, istek
ili neispravan JSON. Uređaji su simulirani; ispad uređaja diže iznimku kao Modbus istek.
Izlazni kod 0 samo ako su svi scenariji prošli (invarijante + očekivanja).
"""
from __future__ import annotations

import argparse
import copy
import io
import json
import socket
import tempfile
import time
import traceback
import urllib.error
from pathlib import Path
from unittest import mock

from jezgra import konfig
from jezgra.jezgra import Jezgra
from jezgra.otkrivanje import Uredaj
from jezgra.simulacija import Lokacija, izravni_uredaji

from .katalog import KATALOG, PROVJERA_UCENJA, Scenarij, po_imenu

URL_TARIFA = "http://tarife.lokalno/v1/cijene"


class SimSat:
    def __init__(self, t: float):
        self.t = t

    def __call__(self) -> float:
        return self.t


class IspadUredaja(Uredaj):
    """Omotač koji u zadanim prozorima glumi uređaj koji ne odgovara (kao Modbus istek)."""

    def __init__(self, u: Uredaj, lok: Lokacija, prozori: list[tuple[float, float]]):
        self.u, self.lok, self.prozori = u, lok, prozori
        self.id, self.tip, self.protokol = u.id, u.tip, u.protokol

    def _ispad(self) -> bool:
        dan = (self.lok.t - self.lok.pocetak_sim) / 86400
        return any(od <= dan < do for od, do in self.prozori)

    def citaj(self):
        if self._ispad():
            raise ConnectionError(f"Modbus {self.id}: istek (nema odgovora)")
        return self.u.citaj()

    def postavi(self, kanal, v):
        if self._ispad():
            raise ConnectionError(f"Modbus {self.id}: istek (nema odgovora)")
        return self.u.postavi(kanal, v)


def cijena_profila(profil: str, ts: float, osnovna: float) -> tuple[float, float]:
    """Ekstremni cjenovni profili (deterministični po satu). Vraća (kupnja, izvoz) €/kWh."""
    import random
    lt = time.localtime(ts)
    r = random.Random(int(ts // 3600) * 31 + 7)
    if profil == "skokovi" and 18 <= lt.tm_hour <= 21 and lt.tm_yday % 2 == 1:
        k = r.uniform(0.9, 1.2)
        return round(k, 4), round(k * 0.4, 4)
    if profil == "negativne" and 11 <= lt.tm_hour <= 15:
        k = -r.uniform(0.05, 0.25)
        return round(k, 4), round(k - 0.02, 4)
    if profil == "volatilne":
        k = osnovna * r.uniform(0.3, 2.5) if r.random() > 0.08 else -r.uniform(0.02, 0.1)
        return round(k, 4), round(k * 0.55 - 0.02, 4)
    return osnovna, round(max(0.0, osnovna * 0.55 - 0.02), 4)


class MokMreze:
    """Zamjena za urllib.request.urlopen: odgovori simulatora + raspored mrežnih kvarova."""

    def __init__(self, lok: Lokacija, kvarovi: list, profil: str | None = None):
        self.lok, self.kvarovi, self.profil = lok, kvarovi, profil
        self.zapis: list[dict] = []

    def _kvar(self, servis: str) -> str | None:
        dan = (self.lok.t - self.lok.pocetak_sim) / 86400
        return next((v for s, v, od, do in self.kvarovi if s == servis and od <= dan < do), None)

    def __call__(self, url, timeout=None, **_):
        url = url if isinstance(url, str) else url.full_url
        servis = "tarife" if url.startswith(URL_TARIFA) else "prognoza"
        kvar = self._kvar(servis)
        self.zapis.append({"t": self.lok.t, "servis": servis, "kvar": kvar})
        if kvar == "pad":
            raise urllib.error.URLError("Network is unreachable")
        if kvar == "istek":
            raise socket.timeout("timed out")
        if kvar == "503":
            raise urllib.error.HTTPError(url, 503, "Service Unavailable", {}, io.BytesIO(b""))
        if kvar == "neispravan":
            return io.BytesIO(b"<html>502 Bad Gateway</html>")
        if servis == "tarife":
            tijelo = self.lok.tarife_api(self.lok.t)
            if self.profil:
                for c in tijelo["cijene"]:
                    c["eur_kwh"], c["izvoz_eur_kwh"] = cijena_profila(self.profil, c["od"], c["eur_kwh"])
        else:
            tijelo = self.lok.prognoza_api(self.lok.t)
        return io.BytesIO(json.dumps(tijelo).encode())


class Cuvar:
    """Sigurnosne invarijante – provjeravaju se u SVAKOM koraku."""

    def __init__(self, cfg: dict, korak_s: float):
        self.cfg, self.korak_s = cfg, korak_s
        self.krsenja: list[dict] = []
        self._suho_koraka = 0
        self.suho_max = 0
        self._bez_napona: dict[int, int] = {}
        self.bez_napona_max_min = 0.0
        self._pokrivenost: list[float] = []  # udio dionica ograde pod naponom ≥ min_kv (mjereno u simulatoru)

    def _krsenje(self, lok, vrsta: str, poruka: str) -> None:
        if len(self.krsenja) < 50:
            self.krsenja.append({"dan": round((lok.t - lok.pocetak_sim) / 86400, 3), "vrsta": vrsta, "poruka": poruka})

    def provjeri(self, lok: Lokacija) -> None:
        b = self.cfg["baterija"]
        nb = lok.naredba_bat
        if nb is not None and nb < -1 and lok.soc <= b["soc_min"] - 0.01:
            self._krsenje(lok, "praznjenje_ispod_min", f"naredba {nb:.0f} W pri SoC {lok.soc:.2f}")
        if nb is not None and nb > 1 and lok.bat_temp < b["temp_punjenje_min_c"]:
            self._krsenje(lok, "punjenje_na_hladnom", f"naredba {nb:.0f} W pri {lok.bat_temp:.1f} °C")
        if lok.releji["pumpa"] and lok.suho:
            self._suho_koraka += 1
            self.suho_max = max(self.suho_max, self._suho_koraka)
        else:
            self._suho_koraka = 0
        # dionice bez kvara ne smiju dugo ostati bez napona (dok je kvar drugdje izoliran)
        kratki, prekid = lok._kvarovi_pastira(lok.t)
        v = lok.pastir_naponi()
        self._pokrivenost.append(sum(1 for x in v[1:] if x >= self.cfg["pastir"]["min_kv"]) / (len(v) - 1))
        for k in range(1, len(v)):
            if k in (kratki, prekid) or kratki is not None and not lok.pastir_povrat:
                continue  # bez prstena kratki spoj legitimno gasi dionice iza kvara
            if v[k] < self.cfg["pastir"]["kvar_kv"]:
                self._bez_napona[k] = self._bez_napona.get(k, 0) + 1
                self.bez_napona_max_min = max(self.bez_napona_max_min, self._bez_napona[k] * self.korak_s / 60)
            else:
                self._bez_napona[k] = 0


def pokreni(sc: Scenarij, cfg_izmjene: dict | None = None, mapa: Path | None = None, ispis: bool = False) -> dict:
    cfg = copy.deepcopy(konfig.ZADANO)
    cfg["mreza"]["dostupna"] = sc.mreza
    for k, v in (cfg_izmjene or {}).items():
        cfg[k].update(v)
    if sc.tarifa == "dinamicka":
        cfg["tarifa"]["izvor_url"] = URL_TARIFA
    pocetak = time.mktime((*sc.pocetak, 0, 0, 0, 0, 0, -1))
    lok = Lokacija(cfg, pocetak, kvarovi=sc.kvarovi or False)
    lok.soc, lok.temp_pomak = sc.soc0, sc.temp_pomak
    if sc.vlaga0 is not None:
        lok.vlaga = {z: sc.vlaga0 for z in lok.vlaga}
    if sc.starenje:
        lok.r_int_rast = sc.starenje
    uredaji: list[Uredaj] = []
    for u in izravni_uredaji(lok):
        prozori = [(od, do) for uid, od, do in sc.ispadi_uredaja if uid == u.id]
        uredaji.append(IspadUredaja(u, lok, prozori) if prozori else u)
    mok = MokMreze(lok, sc.mreza_kvarovi, sc.cijene_profil)
    sat = SimSat(pocetak)
    cuvar = Cuvar(cfg, sc.korak_s)
    tmp = None
    if mapa is None:
        tmp = tempfile.TemporaryDirectory()
        mapa = Path(tmp.name)
    iznimke: list[str] = []
    prognoza_izvori: list[str] = []
    tarifa_izvori: set[str] = set()
    t0 = time.time()
    with mock.patch("jezgra.prognoza.urllib.request.urlopen", mok), \
            mock.patch("jezgra.tarife.urllib.request.urlopen", mok):
        j = Jezgra(mapa, cfg, sat=sat, uredaji=uredaji)
        for i in range(int(sc.dani * 86400 / sc.korak_s)):
            lok.korak(sc.korak_s)
            sat.t = lok.t
            try:
                j.korak()
            except Exception:
                iznimke.append(traceback.format_exc(limit=3))
                if len(iznimke) > 5:
                    break
            cuvar.provjeri(lok)
            if j.plan and i % 30 == 0:
                prognoza_izvori.append(j.plan[0].get("izvor_prognoze", "?"))
                tarifa_izvori.add(j.tarife.cijena(sat.t)["izvor"])
        izv = j.izvjestaj(pocetak, sat.t, izvezi=False)
        sati = [x for x in j.sati if pocetak <= x["ts"] < sat.t]
        dog = list(j.arhiva.citaj(0))
        odrzavanje = j.detektor.predvidi(90)
        j.zatvori()
    trajanje = time.time() - t0
    kpi = _kpi(izv, dog, lok, cuvar, mok, prognoza_izvori, tarifa_izvori, odrzavanje)
    kpi.update(usporedivi_trosak(sati, cfg, sc.soc0))
    kpi.update({"bez_tople_vode_min": round(lok.bez_tople_vode_min), "stres_biljaka_h": round(lok.stres_biljaka_h, 1),
                "voda_min": round(lok.voda_min)})
    kpi["iznimke"] = len(iznimke)
    rez = {"scenarij": sc.ime, "opis": sc.opis, "kpi": kpi, "krsenja": cuvar.krsenja, "iznimke": iznimke[:2],
           "trajanje_s": round(trajanje, 1), "koraka": int(sc.dani * 86400 / sc.korak_s)}
    rez["neuspjesi"] = _ocijeni(sc, rez)
    rez["prosao"] = not rez["neuspjesi"]
    if tmp:
        tmp.cleanup()
    if ispis:
        print(f"{'✓' if rez['prosao'] else '✗'} {sc.ime} ({trajanje:.0f} s): " +
              ("; ".join(rez["neuspjesi"]) if rez["neuspjesi"] else _sazetak(kpi)), flush=True)
    return rez


def usporedivi_trosak(sati: list[dict], cfg: dict, soc0: float) -> dict:
    """Trošak na istoj osnovi za sve strategije: satni neto obračun mreže + trošenje baterije
    − vrijednost promjene napunjenosti na kraju (prosječna izvozna cijena, ista za sve)."""
    if not sati:
        return {"trosak_eur": None, "granica_eur": None}
    trosenje = cfg["baterija"]["trosak_ciklusa_eur_kwh"]
    kap = cfg["baterija"]["kapacitet_kwh"]
    prodaja = sum(s["cijena_prodaja"] for s in sati) / len(sati)
    t = 0.0
    for s in sati:
        n = s["uvoz_kwh"] - s["izvoz_kwh"]
        t += n * (s["cijena_kupnja"] if n > 0 else s["cijena_prodaja"]) + abs(s.get("bat_neto_kwh", 0.0)) * trosenje
    soc_kraj = next((s["soc_kraj"] for s in reversed(sati) if s.get("soc_kraj") is not None), soc0)
    t -= (soc_kraj - soc0) * kap * max(0.0, prodaja)
    # procjena granice: ista satna potrošnja i sunce, optimalna baterija uz savršeno znanje budućnosti
    granica = None
    if cfg["mreza"]["dostupna"]:
        from jezgra.optimizator import planiraj_bateriju
        plan = planiraj_bateriju([s["potrosnja_kwh"] * 1000 for s in sati], [s["pv_kwh"] * 1000 for s in sati],
                                 [{"kupnja": s["cijena_kupnja"], "prodaja": s["cijena_prodaja"]} for s in sati],
                                 soc0, cfg, cfg["baterija"]["soc_min"], sati[0]["ts"])
        g = sum(p["trosak_eur"] for p in plan) - (plan[-1]["soc_cilj"] - soc0) * kap * max(0.0, prodaja)
        granica = round(g, 3)
    return {"trosak_eur": round(t, 3), "granica_eur": granica}


def _kpi(izv, dog, lok, cuvar, mok, prognoza_izvori, tarifa_izvori, odrzavanje) -> dict:
    u, m, p = izv["procjena_ustede"], izv["izmjereno"], izv["pouzdanost"]
    kratki_t = [z["t"] for z in dog if z["v"] == "pastir" and z["d"].get("vrsta") == "kratki_spoj"]
    izol_t = [z["t"] for z in dog if z["v"] == "pastir" and z["d"].get("vrsta") == "izolacija"]
    izolacije_min = [min((i - k for i in izol_t if i >= k), default=float("inf")) / 60 for k in kratki_t]
    offline = [z for z in dog if z["v"] == "uredaj" and "nedostupan" in z["d"].get("poruka", "")]
    online = [z for z in dog if z["v"] == "uredaj" and "ponovno dostupan" in z["d"].get("poruka", "")]
    return {
        "osnovica_eur": u["osnovica_eur"], "s_upravljanjem_eur": u["s_upravljanjem_eur"], "usteda_eur": u["usteda_eur"],
        "usteda_udio": round(u["usteda_eur"] / abs(u["osnovica_eur"]), 3) if abs(u["osnovica_eur"]) > 0.5 else None,
        "samoopskrba": m["samoopskrba"], "uvoz_kwh": m["uvoz_kwh"],
        "neisporuceno_kwh": round(lok.neisporuceno_wh / 1000, 3),
        "baterija_ciklusa": m["baterija_ekv_ciklusa"],
        "pastir_dostupnost": p["pastir_dostupnost"], "pastir_izolacija": p["pastir_automatskih_izolacija"],
        "pastir_pokrivenost": round(sum(cuvar._pokrivenost) / len(cuvar._pokrivenost), 4) if cuvar._pokrivenost else None,
        "izolacija_min": [round(x, 1) for x in izolacije_min],
        "bez_napona_neopravdano_max_min": round(cuvar.bez_napona_max_min, 1),
        "suho_koraka_max": cuvar.suho_max,
        "zastita_pumpe": sum(1 for z in dog if z["v"] == "zastita" and z["d"].get("trosilo") == "pumpa"),
        "uredaj_ispada": len(offline), "uredaj_oporavaka": len(online),
        "prognoza_izvori": sorted(set(prognoza_izvori)),
        "prognoza_na_kraju": prognoza_izvori[-1] if prognoza_izvori else None,
        "tarifa_izvori": sorted(tarifa_izvori),
        "mreznih_poziva": len(mok.zapis), "mreznih_kvarova": sum(1 for z in mok.zapis if z["kvar"]),
        "odrzavanje": [z["pokazatelj"] for z in odrzavanje],
        "krsenja": len(cuvar.krsenja),
    }


def _ocijeni(sc: Scenarij, rez: dict) -> list[str]:
    k, o, n = rez["kpi"], sc.ocekivanja, []
    if rez["krsenja"]:
        n.append(f"sigurnosna invarijanta prekršena {len(rez['krsenja'])}×: {rez['krsenja'][0]}")
    if k["iznimke"]:
        n.append(f"iznimka u jezgri ({k['iznimke']}×)")
    if k["bez_napona_neopravdano_max_min"] > 30:
        n.append(f"ispravna dionica ograde bez napona {k['bez_napona_neopravdano_max_min']} min")
    if "usteda_min_udio" in o and k["usteda_udio"] is not None and k["usteda_udio"] < o["usteda_min_udio"]:
        n.append(f"ušteda {k['usteda_udio']:.1%} < {o['usteda_min_udio']:.0%}")
    if "pastir_dostupnost_min" in o and (k["pastir_dostupnost"] or 0) < o["pastir_dostupnost_min"]:
        n.append(f"dostupnost pastira {k['pastir_dostupnost']} < {o['pastir_dostupnost_min']}")
    if "izolacija_max_min" in o and any(x > o["izolacija_max_min"] for x in k["izolacija_min"]):
        n.append(f"izolacija kvara trajala {max(k['izolacija_min'])} min")
    if "izolacija_min_broj" in o and k["pastir_izolacija"] < o["izolacija_min_broj"]:
        n.append(f"samo {k['pastir_izolacija']} izolacija (očekivano ≥{o['izolacija_min_broj']})")
    if "suho_reakcija_max_koraka" in o and not 0 < k["suho_koraka_max"] <= o["suho_reakcija_max_koraka"]:
        n.append(f"pumpa na suho {k['suho_koraka_max']} koraka (očekivano 1–{o['suho_reakcija_max_koraka']})")
    if o.get("zastita_pumpe") and not k["zastita_pumpe"]:
        n.append("pumpa nije zaštićeno isključena")
    if "neisporuceno_max_kwh" in o and k["neisporuceno_kwh"] > o["neisporuceno_max_kwh"]:
        n.append(f"neisporučeno {k['neisporuceno_kwh']} kWh")
    if o.get("uredaj_oporavak") and not (k["uredaj_ispada"] and k["uredaj_oporavaka"] >= k["uredaj_ispada"]):
        n.append(f"ispad/oporavak uređaja nije zabilježen ({k['uredaj_ispada']}/{k['uredaj_oporavaka']})")
    if o.get("prognoza_zamjena") and "procjena" not in k["prognoza_izvori"]:
        n.append("bez prognoze nije korišten zamjenski model")
    if o.get("prognoza_oporavak") and k["prognoza_na_kraju"] != "prognoza":
        n.append(f"prognoza se nije oporavila (na kraju: {k['prognoza_na_kraju']})")
    if "tarifa_izvor" in o and o["tarifa_izvor"] not in k["tarifa_izvori"]:
        n.append(f"tarifa nije iz izvora {o['tarifa_izvor']} ({k['tarifa_izvori']})")
    if "odrzavanje_pokazatelj" in o and o["odrzavanje_pokazatelj"] not in k["odrzavanje"]:
        n.append(f"prediktivno održavanje nije upozorilo na {o['odrzavanje_pokazatelj']}")
    return n


def _sazetak(k: dict) -> str:
    dio = [f"ušteda {k['usteda_eur']:.2f} €" + (f" ({k['usteda_udio']:.0%})" if k["usteda_udio"] is not None else "")]
    if k["pastir_dostupnost"] is not None:
        dio.append(f"pastir {k['pastir_dostupnost']:.1%}")
    if k["izolacija_min"]:
        dio.append(f"izolacija {', '.join(str(x) for x in k['izolacija_min'])} min")
    if k["uredaj_ispada"]:
        dio.append(f"ispadi uređaja {k['uredaj_ispada']}/oporavci {k['uredaj_oporavaka']}")
    if k["mreznih_kvarova"]:
        dio.append(f"mrežni kvarovi {k['mreznih_kvarova']}/{k['mreznih_poziva']} poziva")
    if k["odrzavanje"]:
        dio.append(f"održavanje: {', '.join(k['odrzavanje'])}")
    return ", ".join(dio)


def u_markdown(rezultati: list[dict]) -> str:
    red = ["| Scenarij | Ishod | Ušteda | Pastir | Izolacija (min) | Kršenja | Napomena |",
           "|---|---|---|---|---|---|---|"]
    for r in rezultati:
        k = r["kpi"]
        udio = "–" if k["usteda_udio"] is None else f"{k['usteda_udio']:.0%}"
        pastir = "–" if k["pastir_dostupnost"] is None else f"{k['pastir_dostupnost']:.1%}"
        izol = ", ".join(str(x) for x in k["izolacija_min"]) or "–"
        napomena = "; ".join(r["neuspjesi"]) or _sazetak(k)
        red.append(f"| {r['scenarij']} | {'✓' if r['prosao'] else '✗'} | {k['usteda_eur']:.2f} € ({udio}) | {pastir} | "
                   f"{izol} | {k['krsenja']} | {napomena} |")
    return "\n".join(red)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Automatizirani scenariji na simulatorima")
    ap.add_argument("--scenarij", action="append", help="ime scenarija (može više puta)")
    ap.add_argument("--oznaka", help="npr. 'brzi' za CI podskup")
    ap.add_argument("--sve", action="store_true", help="svi scenariji iz kataloga (zadano kad nema --oznaka)")
    ap.add_argument("--postavke", type=Path, help="JSON s izmjenama postavki (npr. naučena politika)")
    ap.add_argument("--izlaz", type=Path, help="mapa za rezultati.json i rezultati.md")
    a = ap.parse_args(argv)
    if a.scenarij:
        odabrani = [po_imenu(x) for x in a.scenarij]
    else:
        odabrani = [s for s in KATALOG if a.sve or not a.oznaka or a.oznaka in s.oznake]
    izmjene = json.loads(a.postavke.read_text())["postavke"] if a.postavke else None
    rezultati = [pokreni(s, izmjene, ispis=True) for s in odabrani]
    md = u_markdown(rezultati)
    print("\n" + md)
    if a.izlaz:
        a.izlaz.mkdir(parents=True, exist_ok=True)
        (a.izlaz / "rezultati.json").write_text(json.dumps(rezultati, indent=1, ensure_ascii=False))
        (a.izlaz / "rezultati.md").write_text(md + "\n")
    palo = [r["scenarij"] for r in rezultati if not r["prosao"]]
    print(f"\n{len(rezultati) - len(palo)}/{len(rezultati)} scenarija prošlo." + (f" Palo: {', '.join(palo)}" if palo else ""))
    return 1 if palo else 0


if __name__ == "__main__":
    raise SystemExit(main())
