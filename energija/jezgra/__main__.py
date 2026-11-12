"""Pokretanje: `python -m jezgra [--sim | --sim-dani N] [--podaci MAPA] [--port P]`.

- bez opcija: stvarni uređaji (otkrivanje Modbus/MQTT/UDP), HTTPS sučelje i API,
- `--sim`: simulirana farma preko stvarnih protokola (Modbus TCP + MQTT), ubrzano vrijeme,
- `--sim-dani N`: brza simulacija N dana bez mreže, na kraju potpisani izvještaj.
"""
from __future__ import annotations

import argparse
import json
import signal
import sys
import threading
import time
from pathlib import Path

from . import konfig
from .jezgra import Jezgra


class SimSat:
    def __init__(self, pocetak: float):
        self.t = pocetak

    def __call__(self) -> float:
        return self.t


SEZONE = {"proljece": (2026, 3, 16), "ljeto": (2026, 7, 6), "zima": (2026, 1, 12), "jesen": (2026, 10, 12)}


def brza_simulacija(mapa: Path, dani: float, korak_s: float = 30.0, pocetak: float | None = None,
                    kvarovi: bool = True, ispis: bool = True, sezona: str = "proljece",
                    dinamicka: bool = False, otocno: bool = False) -> tuple[Jezgra, dict]:
    from .simulacija import Lokacija, izravni_uredaji

    cfg = konfig.ucitaj(mapa)
    if otocno:
        cfg["mreza"]["dostupna"] = False
    cfg["kopije"]["odredista"] = [str(Path(mapa) / "usb")]
    (Path(mapa) / "usb").mkdir(parents=True, exist_ok=True)
    pocetak = pocetak or time.mktime((*SEZONE[sezona], 0, 0, 0, 0, 0, -1))  # uvijek ponedjeljak
    lok = Lokacija(cfg, pocetak, kvarovi=kvarovi)
    sat = SimSat(pocetak)
    j = Jezgra(mapa, cfg, sat=sat, uredaji=izravni_uredaji(lok),
               dohvati_prognozu=lambda ts: lok.prognoza_api(ts),
               dohvati_tarife=(lambda ts: lok.tarife_api(ts)) if dinamicka else None)
    koraka = int(dani * 86400 / korak_s)
    t0 = time.time()
    for i in range(koraka):
        lok.korak(korak_s)
        sat.t = lok.t
        j.korak()
        if ispis and i % int(86400 / korak_s) == 0 and i:
            print(f"  dan {i * korak_s / 86400:.0f}: SoC {lok.soc:.0%}, pastir {j.pastir.nacin}, "
                  f"zone {', '.join(f'{k} {v:.0f}%' for k, v in lok.vlaga.items())}", flush=True)
    izv = j.izvjestaj(pocetak, sat.t, "simulacija")
    j.napravi_kopiju()
    j.zatvori()
    if ispis:
        print(f"Simulirano {dani} dana u {time.time() - t0:.1f} s")
    return j, izv


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="jezgra", description="Lokalna jezgra upravljanja energijom")
    ap.add_argument("--podaci", type=Path, default=None)
    ap.add_argument("--sim", action="store_true", help="simulirana farma preko Modbus/MQTT, sučelje uživo")
    ap.add_argument("--sim-dani", type=float, default=None, help="brza simulacija N dana i izvještaj")
    ap.add_argument("--brzina", type=float, default=60.0, help="ubrzanje vremena u --sim načinu")
    ap.add_argument("--sezona", choices=sorted(SEZONE), default="proljece")
    ap.add_argument("--dinamicka", action="store_true", help="dinamička satna tarifa u simulaciji")
    ap.add_argument("--otocno", action="store_true", help="bez mreže (otočni rad)")
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--bez-tls", action="store_true", help="HTTP umjesto HTTPS (samo za lokalni razvoj)")
    a = ap.parse_args(argv)
    mapa = a.podaci or konfig.podatkovna_mapa()

    if a.sim_dani:
        _, izv = brza_simulacija(mapa, a.sim_dani, sezona=a.sezona, dinamicka=a.dinamicka, otocno=a.otocno)
        print(json.dumps({"procjena_ustede": izv["procjena_ustede"], "izmjereno": izv["izmjereno"],
                          "pouzdanost": izv["pouzdanost"], "voda": izv["voda"]}, indent=1, ensure_ascii=False))
        print(f"Izvještaj: {Path(mapa) / 'izvjestaji' / 'simulacija.html'}")
        return 0

    from .api import pokreni_api
    from .nadzor import Nadzornik
    from .otkrivanje import Najavljivac
    from .mqtt import Broker

    cfg = konfig.ucitaj(mapa)
    broker = Broker(host="0.0.0.0" if not a.sim else "127.0.0.1", port=0 if a.sim else 1883).pokreni()
    uredaji = []
    most = None
    sat = time.time
    if a.sim:
        from .simulacija import Lokacija, ProtokolniMost

        pocetak = time.time()
        lok = Lokacija(cfg, pocetak)
        stvarni0 = time.time()
        sat = lambda: pocetak + (time.time() - stvarni0) * a.brzina  # noqa: E731
        most = ProtokolniMost(lok, broker.port)
        cfg["otkrivanje"]["modbus_hostovi"] = [["127.0.0.1", most.modbus.port]]

        def fizika():
            zadnje = sat()
            while True:
                time.sleep(0.5)
                sada = sat()
                lok.korak(sada - zadnje)
                zadnje = sada
                most.osvjezi()

        threading.Thread(target=fizika, daemon=True).start()
    j = Jezgra(mapa, cfg, sat=sat, uredaji=uredaji)
    from .uredjaji import Registar

    registar = Registar(j, broker, cfg)
    registar.pokreni()
    if a.sim:
        j.dohvati_prognozu = lambda ts: lok.prognoza_api(ts)
    port = a.port or cfg["api"]["port"]
    srv, adresa = pokreni_api(j, port, tls=not a.bez_tls)
    Najavljivac({"usluga": "energija-jezgra", "id": j.trezor.id_uredaja(), "https": port,
                 "mqtt": broker.port}).pokreni()

    # tunel: izravno u LAN-u (P2P) uvijek; preko releja samo ako ga je vlasnik dopustio
    from .api import obrada_tunela
    from .tunel import TunelJezgre

    def ovlasteni() -> set[bytes]:
        p = Path(mapa) / "ovlasteni_kljucevi.json"  # javni Ed25519 ključevi uparenih klijenata (hex)
        try:
            return {bytes.fromhex(k) for k in json.loads(p.read_text())}
        except (OSError, ValueError):
            return set()

    tunel = TunelJezgre(j.trezor, ovlasteni, obrada_tunela(j))
    tunel_port = tunel.izravno(port=(a.port or cfg["api"]["port"]) + 2)
    if cfg["tunel"]["relej"] and cfg["tunel"]["dopusteno"]:
        import ssl as _ssl
        host, _, rport = cfg["tunel"]["relej"].partition(":")
        tunel.preko_releja(host, int(rport or 7443), _ssl.create_default_context())
    print(f"Tunel (LAN P2P) na portu {tunel_port}; relej: {cfg['tunel']['relej'] or 'isključen'}")

    nadzor = Nadzornik(j.arhiva, sigurno_stanje=j.sigurno_stanje)
    nadzor.dodaj("upravljanje", j.korak, lambda: max(0.5, 10.0 / (a.brzina if a.sim else 1.0)), kriticno=True, rok_s=30)
    nadzor.dodaj("otkrivanje", registar.skeniraj, lambda: 300.0, rok_s=120)
    nadzor.dodaj("oblak", j.sinkronizacija.korak, lambda: 900.0, rok_s=120)
    j.nadzor = nadzor

    def kraj(*_):
        nadzor.zaustavi()
        j.zatvori()
        sys.exit(0)

    signal.signal(signal.SIGTERM, kraj)
    signal.signal(signal.SIGINT, kraj)
    print(f"Jezgra {j.trezor.id_uredaja()} radi. Sučelje: {adresa}")
    if not a.bez_tls:
        from .certifikati import LokalniCA
        print(f"Otisak lokalnog CA (provjeri jednom pri uparivanju): {LokalniCA(mapa, j.trezor).otisak()}")
    print(f"Kod za uparivanje (vrijedi 15 min): {j.kod_uparivanja}")
    nadzor.pokreni()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
