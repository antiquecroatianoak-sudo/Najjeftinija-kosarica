"""Šifrirani dnevnik (append-only) i snimke stanja – oporavak bez gubitka podataka.

Zapis u segmentu: [8 B slijed][4 B duljina][4 B CRC32][AES-GCM omotnica, AAD = slijed].
- Kritični zapisi (odluke, kvarovi, naredbe) odmah se fsync-aju.
- Telemetrija se grupira (fsync svakih N zapisa ili T sekundi) radi manjeg trošenja SD kartice.
- Pri pokretanju se zadnji segment provjerava; oštećen ili nedovršen rep (nestanak struje
  usred pisanja) odreže se na zadnji ispravan zapis. Ništa potvrđeno se ne gubi.
- Snimka stanja piše se atomski (tmp + fsync + rename) i čuva prethodnu generaciju.
"""
from __future__ import annotations

import json
import os
import struct
import threading
import time
import zlib
from pathlib import Path
from typing import Iterator

from .sifra import GreskaSifre, otpakiraj, zapakiraj

ZAGLAVLJE = struct.Struct(">QII")
MAX_SEGMENT = 1 << 20


class Dnevnik:
    def __init__(self, mapa: Path, kljuc: bytes, fsync_svakih: int = 50, fsync_sekundi: float = 30.0,
                 max_segmenata: int = 2000):
        self.mapa = Path(mapa) / "dnevnik"
        self.mapa.mkdir(parents=True, exist_ok=True)
        self.kljuc = kljuc
        self.fsync_svakih, self.fsync_sekundi = fsync_svakih, fsync_sekundi
        self.max_segmenata = max_segmenata
        self._lock = threading.RLock()
        self._nesinkronizirano = 0
        self._zadnji_fsync = time.monotonic()
        self.oporavak: dict = {"odrezano_bajtova": 0, "segment": None}
        self.slijed = 0
        self._otvori()

    # --- segmenti -------------------------------------------------------------
    def segmenti(self) -> list[Path]:
        return sorted(self.mapa.glob("seg-*.log"))

    def _otvori(self) -> None:
        seg = self.segmenti()
        if not seg:
            self._aktivni = self.mapa / "seg-00000001.log"
            self._aktivni.touch()
        else:
            self._aktivni = seg[-1]
            ispravno, zadnji = self._provjeri(self._aktivni)
            velicina = self._aktivni.stat().st_size
            if ispravno < velicina:
                with open(self._aktivni, "r+b") as f:
                    f.truncate(ispravno)
                    f.flush()
                    os.fsync(f.fileno())
                self.oporavak = {"odrezano_bajtova": velicina - ispravno, "segment": self._aktivni.name}
            if zadnji is None and len(seg) > 1:
                _, zadnji = self._provjeri(seg[-2])
            self.slijed = zadnji or 0
        self._f = open(self._aktivni, "ab")

    def _provjeri(self, p: Path) -> tuple[int, int | None]:
        """Vrati (broj ispravnih bajtova, zadnji slijed)."""
        pomak, zadnji = 0, None
        with open(p, "rb") as f:
            while True:
                z = f.read(ZAGLAVLJE.size)
                if len(z) < ZAGLAVLJE.size:
                    break
                slijed, duljina, crc = ZAGLAVLJE.unpack(z)
                tijelo = f.read(duljina)
                if len(tijelo) < duljina or zlib.crc32(tijelo) != crc:
                    break
                try:
                    otpakiraj(self.kljuc, tijelo, struct.pack(">Q", slijed))
                except GreskaSifre:
                    break
                pomak += ZAGLAVLJE.size + duljina
                zadnji = slijed
        return pomak, zadnji

    def _rotiraj(self) -> None:
        self._sinkroniziraj()
        self._f.close()
        broj = int(self._aktivni.stem.split("-")[1]) + 1
        self._aktivni = self.mapa / f"seg-{broj:08d}.log"
        self._f = open(self._aktivni, "ab")
        seg = self.segmenti()
        for stari in seg[: max(0, len(seg) - self.max_segmenata)]:
            stari.unlink(missing_ok=True)

    def zatvoreni_segmenti(self) -> list[Path]:
        return [s for s in self.segmenti() if s != self._aktivni]

    # --- pisanje / čitanje ------------------------------------------------------
    def zapisi(self, vrsta: str, podaci: dict, kriticno: bool = False, ts: float | None = None) -> int:
        with self._lock:
            self.slijed += 1
            tijelo = json.dumps({"s": self.slijed, "t": ts if ts is not None else time.time(), "v": vrsta,
                                 "d": podaci}, separators=(",", ":"), ensure_ascii=False).encode()
            omot = zapakiraj(self.kljuc, tijelo, struct.pack(">Q", self.slijed))
            self._f.write(ZAGLAVLJE.pack(self.slijed, len(omot), zlib.crc32(omot)) + omot)
            self._nesinkronizirano += 1
            if (kriticno or self._nesinkronizirano >= self.fsync_svakih
                    or time.monotonic() - self._zadnji_fsync > self.fsync_sekundi):
                self._sinkroniziraj()
            if self._f.tell() > MAX_SEGMENT:
                self._rotiraj()
            return self.slijed

    def _sinkroniziraj(self) -> None:
        self._f.flush()
        os.fsync(self._f.fileno())
        self._nesinkronizirano = 0
        self._zadnji_fsync = time.monotonic()

    def sinkroniziraj(self) -> None:
        with self._lock:
            self._sinkroniziraj()

    def citaj(self, od_slijeda: int = 0, vrste: set[str] | None = None) -> Iterator[dict]:
        with self._lock:
            self._f.flush()
            segmenti = self.segmenti()
        for p in segmenti:
            with open(p, "rb") as f:
                while True:
                    z = f.read(ZAGLAVLJE.size)
                    if len(z) < ZAGLAVLJE.size:
                        break
                    slijed, duljina, crc = ZAGLAVLJE.unpack(z)
                    tijelo = f.read(duljina)
                    if len(tijelo) < duljina or zlib.crc32(tijelo) != crc:
                        break
                    if slijed <= od_slijeda:
                        continue
                    z = json.loads(otpakiraj(self.kljuc, tijelo, struct.pack(">Q", slijed)))
                    if vrste is None or z["v"] in vrste:
                        yield z

    def zatvori(self) -> None:
        with self._lock:
            self._sinkroniziraj()
            self._f.close()


class Snimka:
    """Atomska, šifrirana snimka stanja s prethodnom generacijom kao rezervom."""

    def __init__(self, mapa: Path, kljuc: bytes, ime: str = "stanje"):
        self.p = Path(mapa) / f"{ime}.bin"
        self.prev = Path(mapa) / f"{ime}.prev.bin"
        self.kljuc = kljuc

    def spremi(self, stanje: dict, slijed: int) -> None:
        omot = zapakiraj(self.kljuc, json.dumps({"slijed": slijed, "stanje": stanje}).encode(), b"snimka")
        tmp = self.p.with_suffix(".tmp")
        with open(tmp, "wb") as f:
            f.write(omot)
            f.flush()
            os.fsync(f.fileno())
        if self.p.exists():
            os.replace(self.p, self.prev)
        os.replace(tmp, self.p)
        try:
            d = os.open(self.p.parent, os.O_RDONLY)
            os.fsync(d)
            os.close(d)
        except OSError:
            pass

    def ucitaj(self) -> tuple[dict, int, str]:
        for p, izvor in ((self.p, "zadnja"), (self.prev, "prethodna")):
            if p.exists():
                try:
                    v = json.loads(otpakiraj(self.kljuc, p.read_bytes(), b"snimka"))
                    return v["stanje"], v["slijed"], izvor
                except (GreskaSifre, ValueError, KeyError):
                    continue
        return {}, 0, "nema"
