"""Lokalna redundancija: šifrirane sigurnosne kopije na sekundarni medij ili privatnu mrežu.

Odredišta (bilo koji broj):
- mapa: USB stick / druga SD kartica / NAS montiran lokalno (npr. "/mnt/usb"),
- "http(s)://...": druga jezgra ili NAS u privatnoj mreži (PUT, mTLS lokalnog CA).

Segmenti dnevnika i snimka već su šifrirani ključem uređaja; kopija dodatno nosi manifest s
HMAC oznakom, pa se oštećenje ili podmetanje otkriva prije oporavka. Za oporavak bez
ikakvog oblaka dovoljni su kopija i datoteka `kljucevi/` (ili njezina papirnata/USB kopija
koju vlasnik čuva odvojeno – bez nje kopija je neupotrebljiva, što je i svrha).
"""
from __future__ import annotations

import hashlib
import json
import shutil
import ssl
import time
import urllib.request
from pathlib import Path

from .sifra import oznaka_integriteta


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 16), b""):
            h.update(b)
    return h.hexdigest()


class Kopije:
    def __init__(self, podaci: Path, kljuc: bytes, odredista: list[str], generacija: int = 5,
                 ssl_kontekst: ssl.SSLContext | None = None):
        self.podaci = Path(podaci)
        self.kljuc = kljuc
        self.odredista = list(odredista)
        self.generacija = generacija
        self.ssl = ssl_kontekst
        self.zadnje: dict[str, dict] = {}

    def _datoteke(self, segmenti: list[Path]) -> list[tuple[str, Path]]:
        """Ime u kopiji: relativna putanja s '__' umjesto '/' (dnevnik__seg-00000001.log)."""
        out = []
        for p in list(segmenti) + [self.podaci / "stanje.bin", self.podaci / "stanje.prev.bin"]:
            if p.exists():
                out.append((str(p.relative_to(self.podaci)).replace("/", "__"), p))
        return out

    def napravi(self, segmenti: list[Path]) -> list[dict]:
        rezultati = []
        datoteke = self._datoteke(segmenti)
        manifest = {"vrijeme": time.time(), "datoteke": {ime: _sha(p) for ime, p in datoteke}}
        tijelo = json.dumps(manifest, sort_keys=True).encode()
        manifest_b = json.dumps({"m": manifest, "hmac": oznaka_integriteta(self.kljuc, tijelo)}).encode()
        for od in self.odredista:
            try:
                if od.startswith(("http://", "https://")):
                    self._na_mrezu(od, datoteke, manifest_b)
                else:
                    self._na_medij(Path(od), datoteke, manifest_b)
                r = {"odrediste": od, "ok": True, "datoteka": len(datoteke), "vrijeme": manifest["vrijeme"]}
            except Exception as e:  # medij izvađen, mreža pala... – sljedeći pokušaj kasnije
                r = {"odrediste": od, "ok": False, "greska": f"{type(e).__name__}: {e}", "vrijeme": manifest["vrijeme"]}
            self.zadnje[od] = r
            rezultati.append(r)
        return rezultati

    def _na_medij(self, korijen: Path, datoteke: list[tuple[str, Path]], manifest_b: bytes) -> None:
        if not korijen.exists():
            raise FileNotFoundError(f"medij {korijen} nije priključen")
        baza = korijen / "energija-kopije"
        segm = baza / "segmenti"
        segm.mkdir(parents=True, exist_ok=True)
        for ime, p in datoteke:  # zatvoreni segmenti se ne mijenjaju: kopiraj samo nove ili promijenjene
            cilj = segm / ime
            if not cilj.exists() or cilj.stat().st_size != p.stat().st_size or ime.startswith("stanje"):
                tmp = cilj.with_suffix(".tmp")
                shutil.copyfile(p, tmp)
                tmp.replace(cilj)
        gen = baza / f"manifest-{int(time.time() * 1000)}.json"
        gen.write_bytes(manifest_b)
        for stari in sorted(baza.glob("manifest-*.json"))[: -self.generacija]:
            stari.unlink(missing_ok=True)

    def _na_mrezu(self, url: str, datoteke: list[tuple[str, Path]], manifest_b: bytes) -> None:
        for ime, p in datoteke:
            zahtjev = urllib.request.Request(f"{url.rstrip('/')}/{ime}", data=p.read_bytes(), method="PUT",
                                             headers={"Content-Type": "application/octet-stream"})
            urllib.request.urlopen(zahtjev, timeout=20, context=self.ssl).read()
        zahtjev = urllib.request.Request(f"{url.rstrip('/')}/manifest.json", data=manifest_b, method="PUT")
        urllib.request.urlopen(zahtjev, timeout=20, context=self.ssl).read()

    def provjeri(self, korijen: Path) -> dict:
        """Provjeri zadnji manifest na mediju: HMAC i SHA-256 svake datoteke."""
        baza = Path(korijen) / "energija-kopije"
        manifesti = sorted(baza.glob("manifest-*.json"))
        if not manifesti:
            return {"ok": False, "razlog": "nema kopije"}
        v = json.loads(manifesti[-1].read_bytes())
        tijelo = json.dumps(v["m"], sort_keys=True).encode()
        if oznaka_integriteta(self.kljuc, tijelo) != v["hmac"]:
            return {"ok": False, "razlog": "manifest je izmijenjen ili pripada drugom uređaju"}
        lose = [ime for ime, h in v["m"]["datoteke"].items()
                if not (baza / "segmenti" / ime).exists() or _sha(baza / "segmenti" / ime) != h]
        return {"ok": not lose, "lose": lose, "manifest": manifesti[-1].name, "datoteka": len(v["m"]["datoteke"])}

    def obnovi(self, korijen: Path, cilj: Path) -> dict:
        """Vrati podatke s medija u (praznu) podatkovnu mapu. Ključevi se vraćaju zasebno."""
        r = self.provjeri(korijen)
        if not r["ok"]:
            return r
        baza = Path(korijen) / "energija-kopije"
        v = json.loads(sorted(baza.glob("manifest-*.json"))[-1].read_bytes())
        for ime in v["m"]["datoteke"]:
            odred = Path(cilj).joinpath(*ime.split("__"))
            if ".." in odred.relative_to(cilj).parts:
                continue
            odred.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(baza / "segmenti" / ime, odred)
        return {"ok": True, "vraceno": len(v["m"]["datoteke"])}
