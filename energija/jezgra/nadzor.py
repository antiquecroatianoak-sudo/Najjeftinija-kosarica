"""Nadzornik zadataka: autonomni oporavak bez gubitka podataka.

- Svaki zadatak radi u svojoj niti s rokom (watchdog). Iznimka ili prekoračenje roka se
  zapisuje u dnevnik, a zadatak se ponovno pokreće s eksponencijalnim čekanjem.
- Kritični zadatak koji padne 3 puta zaredom prebacuje sustav u SIGURNO STANJE (pastir
  uključen, pumpa i bojler isključeni, baterija bez punjenja iz mreže) dok se ne oporavi.
- Ako ništa ne radi (sve niti zaglave), proces se gasi; vanjski nadzor (systemd watchdog
  ili `restart: always` kontejnera, a na Raspberry Pi i hardverski watchdog) ga ponovno
  pokreće, a jezgra pri startu učita snimku i dnevnik (vidi pohrana.py).
"""
from __future__ import annotations

import os
import socket
import threading
import time
import traceback
from dataclasses import dataclass, field


@dataclass
class Zadatak:
    ime: str
    funkcija: object
    period: object  # float ili callable -> float (dinamički interval)
    kriticno: bool = False
    rok_s: float = 60.0
    padova_zaredom: int = 0
    ukupno_padova: int = 0
    zadnji_pocetak: float = 0.0
    zadnji_kraj: float = 0.0
    zadnja_greska: str | None = None
    u_tijeku: bool = False
    sljedece: float = 0.0
    nit: threading.Thread | None = field(default=None, repr=False)


def sd_notify(poruka: str) -> None:
    """systemd obavijest (READY=1 / WATCHDOG=1); bez systemd-a ne radi ništa."""
    adr = os.environ.get("NOTIFY_SOCKET")
    if not adr:
        return
    if adr.startswith("@"):
        adr = "\0" + adr[1:]
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as s:
            s.connect(adr)
            s.sendall(poruka.encode())
    except OSError:
        pass


class Nadzornik:
    def __init__(self, dnevnik=None, sigurno_stanje=None):
        self.zadaci: dict[str, Zadatak] = {}
        self.dnevnik = dnevnik
        self.sigurno_stanje = sigurno_stanje
        self.u_sigurnom = False
        self._radi = False

    def dodaj(self, ime, funkcija, period, kriticno=False, rok_s=60.0) -> None:
        self.zadaci[ime] = Zadatak(ime, funkcija, period, kriticno, rok_s)

    def _period(self, z: Zadatak) -> float:
        return float(z.period() if callable(z.period) else z.period)

    def _izvrsi(self, z: Zadatak) -> None:
        z.u_tijeku, z.zadnji_pocetak = True, time.monotonic()
        try:
            z.funkcija()
            z.padova_zaredom = 0
            z.zadnja_greska = None
            z.sljedece = time.monotonic() + self._period(z)
        except Exception as e:
            z.padova_zaredom += 1
            z.ukupno_padova += 1
            z.zadnja_greska = f"{type(e).__name__}: {e}"
            odgoda = min(300.0, 2.0 ** z.padova_zaredom)
            z.sljedece = time.monotonic() + odgoda
            self._zapisi("pad_zadatka", {"zadatak": z.ime, "greska": z.zadnja_greska,
                                         "trag": traceback.format_exc(limit=4), "ponovno_za_s": odgoda})
            if z.kriticno and z.padova_zaredom >= 3 and not self.u_sigurnom:
                self._u_sigurno(z)
        finally:
            z.u_tijeku, z.zadnji_kraj = False, time.monotonic()
        if self.u_sigurnom and z.kriticno and z.padova_zaredom == 0 and \
                all(x.padova_zaredom < 3 for x in self.zadaci.values() if x.kriticno):
            self.u_sigurnom = False
            self._zapisi("izlaz_iz_sigurnog", {"zadatak": z.ime})

    def _u_sigurno(self, z: Zadatak) -> None:
        self.u_sigurnom = True
        self._zapisi("sigurno_stanje", {"uzrok": z.ime, "greska": z.zadnja_greska})
        if self.sigurno_stanje:
            try:
                self.sigurno_stanje()
            except Exception as e:
                self._zapisi("sigurno_stanje_greska", {"greska": str(e)})

    def _zapisi(self, vrsta: str, podaci: dict) -> None:
        if self.dnevnik:
            try:
                self.dnevnik.zapisi(vrsta, podaci, kriticno=True)
            except Exception:
                pass

    def jednom(self) -> None:
        """Jedan prolaz rasporeda (koristi se i u testovima / ubrzanoj simulaciji)."""
        sada = time.monotonic()
        for z in self.zadaci.values():
            if z.u_tijeku:
                if sada - z.zadnji_pocetak > z.rok_s and z.zadnja_greska != "rok":
                    z.zadnja_greska = "rok"
                    z.ukupno_padova += 1
                    z.padova_zaredom += 1
                    self._zapisi("zaglavljen_zadatak", {"zadatak": z.ime, "s": round(sada - z.zadnji_pocetak)})
                    if z.kriticno and z.padova_zaredom >= 3:
                        self._u_sigurno(z)
                continue
            if sada >= z.sljedece:
                z.nit = threading.Thread(target=self._izvrsi, args=(z,), daemon=True, name=z.ime)
                z.nit.start()

    def pokreni(self) -> None:
        self._radi = True
        sd_notify("READY=1")
        while self._radi:
            self.jednom()
            zivi = any(not z.u_tijeku or time.monotonic() - z.zadnji_pocetak < z.rok_s * 3
                       for z in self.zadaci.values() if z.kriticno)
            if zivi:
                sd_notify("WATCHDOG=1")
            time.sleep(0.5)

    def zaustavi(self) -> None:
        self._radi = False

    def stanje(self) -> dict:
        return {"sigurno_stanje": self.u_sigurnom,
                "zadaci": {z.ime: {"kriticno": z.kriticno, "padova": z.ukupno_padova, "greska": z.zadnja_greska,
                                   "u_tijeku": z.u_tijeku} for z in self.zadaci.values()}}
