"""Sigurna sinkronizacija s oblakom – nikad nije uvjet za rad jezgre.

- Izlaz: zapisi dnevnika od zadnjeg potvrđenog slijeda šalju se u paketima. Paket je
  šifriran ključem `oblak` (AES-256-GCM) – oblak sprema samo šifrirani tekst; čitati ga
  mogu samo vlasnikovi upareni uređaji. Uz paket ide Ed25519 potpis jezgre.
- Pokazivač (zadnji potvrđeni slijed) sprema se tek nakon 2xx odgovora, pa se ništa ne
  gubi ni ne duplira (oblak odbacuje već primljene slijedove – idempotentno).
- Bez mreže: eksponencijalno čekanje do 1 h; dnevnik čuva podatke lokalno.
- Ulaz: oblak smije predložiti nove postavke samo ako ih je potpisao vlasnikov ključ;
  nepotpisane ili tuđe promjene se odbacuju. Kritične sigurnosne granice (minimalni SoC,
  zaštita pastira) ne mogu se mijenjati izvana.
"""
from __future__ import annotations

import base64
import json
import time
import urllib.request

from .sifra import provjeri_potpis, zapakiraj

ZASTICENO = {"baterija", "pastir"}


class Sinkronizacija:
    def __init__(self, cfg: dict, trezor, dnevnik, stanje: dict | None = None, posalji=None):
        self.url = cfg["sinkronizacija"]["url"]
        self.trezor, self.dnevnik = trezor, dnevnik
        s = stanje or {}
        self.pokazivac = s.get("pokazivac", 0)
        self.kljuc_vlasnika: bytes | None = bytes.fromhex(s["vlasnik"]) if s.get("vlasnik") else None
        self.cekaj_do = 0.0
        self.odgoda = 30.0
        self.zadnji_uspjeh = s.get("zadnji_uspjeh")
        self.greska: str | None = None
        self._posalji = posalji or self._http
        self.ukljuceno = bool(self.url) or posalji is not None
        self.predlozene: dict | None = None

    def stanje(self) -> dict:
        return {"pokazivac": self.pokazivac, "vlasnik": self.kljuc_vlasnika.hex() if self.kljuc_vlasnika else None,
                "zadnji_uspjeh": self.zadnji_uspjeh}

    def _http(self, putanja: str, tijelo: bytes) -> tuple[int, bytes]:
        z = urllib.request.Request(self.url.rstrip("/") + putanja, data=tijelo, method="POST",
                                   headers={"Content-Type": "application/octet-stream",
                                            "X-Uredaj": self.trezor.id_uredaja()})
        with urllib.request.urlopen(z, timeout=20) as r:
            return r.status, r.read()

    def korak(self, sada: float | None = None, najvise: int = 500) -> dict:
        sada = sada or time.time()
        if not self.ukljuceno or sada < self.cekaj_do:
            return {"poslano": 0, "na_cekanju": True}
        zapisi = []
        for z in self.dnevnik.citaj(self.pokazivac):
            zapisi.append(z)
            if len(zapisi) >= najvise:
                break
        if not zapisi:
            return {"poslano": 0}
        sirovo = json.dumps(zapisi, separators=(",", ":")).encode()
        omot = zapakiraj(self.trezor.kljuc("oblak"), sirovo, self.trezor.id_uredaja().encode())
        paket = json.dumps({
            "uredaj": self.trezor.id_uredaja(), "od": zapisi[0]["s"], "do": zapisi[-1]["s"],
            "podaci": base64.b64encode(omot).decode(),
            "potpis": base64.b64encode(self.trezor.potpisi(omot)).decode(),
        }).encode()
        try:
            status, odg = self._posalji("/v1/paket", paket)
            if not 200 <= status < 300:
                raise ConnectionError(f"HTTP {status}")
            self.pokazivac = zapisi[-1]["s"]
            self.zadnji_uspjeh, self.greska, self.odgoda = sada, None, 30.0
            self._primi_postavke(odg)
            return {"poslano": len(zapisi), "pokazivac": self.pokazivac}
        except Exception as e:
            self.greska = f"{type(e).__name__}: {e}"
            self.cekaj_do = sada + self.odgoda
            self.odgoda = min(3600.0, self.odgoda * 2)
            return {"poslano": 0, "greska": self.greska}

    def _primi_postavke(self, odg: bytes) -> None:
        if not odg:
            return
        try:
            v = json.loads(odg)
        except ValueError:
            return
        if "postavke" in v and self.kljuc_vlasnika:
            tijelo = json.dumps(v["postavke"], sort_keys=True).encode()
            if provjeri_potpis(self.kljuc_vlasnika, tijelo, base64.b64decode(v.get("potpis", ""))):
                self.predlozene = {k: x for k, x in v["postavke"].items() if k not in ZASTICENO}
