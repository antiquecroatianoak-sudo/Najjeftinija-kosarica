"""Cjelovita izolirana provjera: jezgra + pymodbus simulator + MQTT senzori + lažni Open-Meteo.

Izlazni kod 0 = sve provjere prošle. Svaka provjera ispisuje ✓/✗ i dokaz.
Okolina: JEZGRA_URL, CA (put do ca.pem jezgre), SIM_URL, OPENMETEO_URL, ENERGIJA_KOD,
         PROVJERI_IZOLACIJU=1 (u Composeu: dokaži da nema izlaza na internet).
"""
from __future__ import annotations

import json
import os
import socket
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jezgra.izvjestaji import provjeri as provjeri_potpis  # noqa: E402

JEZGRA = os.environ.get("JEZGRA_URL", "https://localhost:8443")
SIM = os.environ.get("SIM_URL", "http://localhost:8081")
OM = os.environ.get("OPENMETEO_URL", "http://localhost:8080")
CA = os.environ.get("CA", "/podaci-jezgre/certifikati/ca.pem")
KOD = os.environ.get("ENERGIJA_KOD", "")
ROK = float(os.environ.get("ROK_S", "120"))

rezultati: list[tuple[bool, str, str]] = []


def zabiljezi(ok: bool, naziv: str, dokaz: str = "") -> bool:
    rezultati.append((ok, naziv, dokaz))
    print(f"{'✓' if ok else '✗'} {naziv}" + (f" – {dokaz}" if dokaz else ""), flush=True)
    return ok


def cekaj(uvjet, rok: float = ROK, korak: float = 1.0):
    kraj = time.time() + rok
    zadnje = None
    while time.time() < kraj:
        try:
            zadnje = uvjet()
            if zadnje:
                return zadnje
        except Exception as e:  # servis se još diže
            zadnje = e
        time.sleep(korak)
    return None


def http_json(url: str, tijelo=None, token: str | None = None, ctx=None) -> tuple[int, dict]:
    z = urllib.request.Request(url, data=None if tijelo is None else json.dumps(tijelo).encode(),
                               method="GET" if tijelo is None else "POST",
                               headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"}
                                                                                if token else {})})
    try:
        with urllib.request.urlopen(z, context=ctx, timeout=10) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def main() -> int:
    print(f"Provjera: jezgra {JEZGRA}, simulator {SIM}, Open-Meteo (lažni) {OM}", flush=True)

    # 1) TLS lokalnog CA-a, stroga provjera (ime hosta + AKI/SKI)
    if not cekaj(lambda: Path(CA).exists()):
        zabiljezi(False, "CA jezgre dostupan", CA)
        return izvjestaj()
    ctx = ssl.create_default_context(cafile=CA)
    st = cekaj(lambda: http_json(f"{JEZGRA}/api/zdravlje", ctx=ctx)[1].get("ok"))
    zabiljezi(bool(st), "HTTPS jezgre, certifikat lokalnog CA-a prolazi strogu provjeru")
    if not st:
        return izvjestaj()

    # 2) uparivanje (jednokratni kod) i zaštita API-ja
    s, _ = http_json(f"{JEZGRA}/api/stanje", ctx=ctx)
    zabiljezi(s == 401, "API bez tokena odbijen", f"HTTP {s}")
    s, v = http_json(f"{JEZGRA}/api/upari", {"kod": KOD, "ime": "provjera"}, ctx=ctx)
    token = v.get("token")
    zabiljezi(s == 200 and bool(token), "uparivanje kodom", f"HTTP {s}")
    s, _ = http_json(f"{JEZGRA}/api/upari", {"kod": KOD}, ctx=ctx)
    zabiljezi(s == 403, "isti kod drugi put odbijen", f"HTTP {s}")
    if not token:
        return izvjestaj()
    stanje = lambda: http_json(f"{JEZGRA}/api/stanje", token=token, ctx=ctx)[1]  # noqa: E731

    # 3) plug-and-play: pymodbus (SunSpec + SDM) i MQTT najava prepoznati bez ručnog upisa
    def uredaji_ok():
        u = stanje()["uredaji"]
        p = {x["protokol"] for x in u if x["dostupan"]}
        return u if {"modbus/sunspec", "modbus/sdm", "mqtt"} <= p else None
    u = cekaj(uredaji_ok)
    zabiljezi(bool(u), "automatsko prepoznavanje uređaja (pymodbus SunSpec, pymodbus SDM, MQTT)",
              ", ".join(f"{x['id']} [{x['protokol']}]" for x in (u or [])))

    # 4) očitanja i prognoza iz lažnog Open-Meteo
    sv = cekaj(lambda: (lambda s: s if s["energija"]["baterija_soc"] is not None and s["prognoza"]["izvor"] == "prognoza"
                        else None)(stanje()))
    zabiljezi(bool(sv), "očitanja stižu i prognoza dolazi iz (lažnog) Open-Meteo",
              f"SoC {sv['energija']['baterija_soc'] if sv else '?'}")
    _, zahtjevi = http_json(f"{OM}/zahtjevi")
    ok = bool(zahtjevi) and all(k in zahtjevi[-1]["upit"] for k in ("latitude", "longitude", "hourly"))
    zabiljezi(ok, "jezgra je pozvala Open-Meteo s ispravnim parametrima",
              f"{len(zahtjevi)} zahtjeva, zadnji: {zahtjevi[-1]['upit'] if zahtjevi else '-'}")

    # 5) odluke su objašnjene, plan postoji, pastir nadziran
    sv = stanje()
    zabiljezi(all(k in sv["odluke"] for k in ("baterija", "prognoza")) and len(sv["plan"]) >= 24,
              "odluke s razlozima i plan za 36 h", ", ".join(f"{k}: {v['odluka']}" for k, v in sv["odluke"].items()))
    p = cekaj(lambda: stanje()["pastir"]["dionice"] if "?" not in stanje()["pastir"]["dionice"] else None, rok=60)
    zabiljezi(bool(p), "pastir: stanje svih dionica iz MQTT mjerenja", str(p))

    # 6) ručno premošćivanje baterije -> Modbus upis u pymodbus registre -> model simulatora
    http_json(f"{JEZGRA}/api/postavke", {"baterija_nacin": "rucno", "rucna_snaga_w": 1200, "minuta": 10},
              token=token, ctx=ctx)
    n = cekaj(lambda: (lambda b: b if b is not None and abs(b - 1200) < 40 else None)(
        http_json(f"{SIM}/stanje")[1]["naredba_bat"]), rok=30)
    zabiljezi(n is not None, "ručna snaga baterije stiže do izmjenjivača preko Modbusa", f"naredba {n} W")
    http_json(f"{JEZGRA}/api/postavke", {"baterija_nacin": "vlastita"}, token=token, ctx=ctx)
    a = cekaj(lambda: http_json(f"{SIM}/stanje")[1]["naredba_bat"] is None or None, rok=30)
    zabiljezi(bool(a), "povratak na vlastiti način (StorCtl_Mod = 0)")
    http_json(f"{JEZGRA}/api/postavke", {"baterija_nacin": "auto"}, token=token, ctx=ctx)

    # 7) MQTT naredba releju (bojler) i odbijanje ručnog gašenja pastira
    s, _ = http_json(f"{JEZGRA}/api/naredba", {"trosilo": "bojler", "ukljuci": True, "minuta": 5}, token=token, ctx=ctx)
    b = cekaj(lambda: http_json(f"{SIM}/stanje")[1]["releji"]["bojler"] or None, rok=30)
    zabiljezi(s == 200 and bool(b), "ručna naredba bojleru stiže preko MQTT-a")
    s, _ = http_json(f"{JEZGRA}/api/naredba", {"trosilo": "pastir", "ukljuci": False}, token=token, ctx=ctx)
    zabiljezi(s == 400, "ručno gašenje pastira odbijeno", f"HTTP {s}")

    # 8) potpisani izvještaj
    s, v = http_json(f"{JEZGRA}/api/izvjestaj?dana=1&format=json", token=token, ctx=ctx)
    ok = s == 200 and provjeri_potpis(v["izvjestaj"], v["potpis"])
    v2 = json.loads(json.dumps(v)) if ok else None
    if v2:
        v2["izvjestaj"]["izmjereno"]["uvoz_kwh"] = 999
    zabiljezi(ok and not provjeri_potpis(v2["izvjestaj"], v2["potpis"]), "izvještaj potpisan, izmjena se otkriva")

    # 9) AI profil: provjera resursa izvršena na ovom uređaju
    ai = stanje()["ai"]
    zabiljezi(bool(ai["provjera"].get("resursi")), "AI: izmjereno zauzeće memorije prije primjene profila",
              f"slobodno {ai['provjera'].get('slobodno_mb')} MB, cgroup limit "
              f"{ai['provjera'].get('resursi', {}).get('cgroup_limit_mb')} MB, aktivan={ai['aktivan']}")

    # 10) izolacija: nema izlaza na internet (samo u Composeu)
    if os.environ.get("PROVJERI_IZOLACIJU") == "1":
        try:
            socket.create_connection(("api.open-meteo.com", 443), timeout=5).close()
            zabiljezi(False, "mreža je izolirana (nema interneta)", "veza prema api.open-meteo.com USPJELA")
        except OSError as e:
            zabiljezi(True, "mreža je izolirana (nema interneta)", type(e).__name__)
    return izvjestaj()


def izvjestaj() -> int:
    palo = [r for r in rezultati if not r[0]]
    print(f"\n{len(rezultati) - len(palo)}/{len(rezultati)} provjera prošlo.", flush=True)
    return 1 if palo else 0


if __name__ == "__main__":
    sys.exit(main())
