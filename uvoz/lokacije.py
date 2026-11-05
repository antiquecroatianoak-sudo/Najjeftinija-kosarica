"""Koordinate poslovnica kojih nema u dopuni (senko/cijene-api enrichment/stores.csv).

Izvor: OpenStreetMap Nominatim (© OpenStreetMap suradnici, ODbL). Pravila korištenja Nominatima:
najviše jedan upit u sekundi, prepoznatljiv User-Agent, rezultati se spremaju i ne traže ponovno.
Zato se svaki rezultat (i neuspjeh) sprema u predmemoriju koja se objavljuje uz aplikaciju
(`data/hr/lokacije.json`) i sljedećim pokretanjem čita s objavljene stranice; po pokretanju se
postavlja najviše NAJVISE_UPITA upita, ostatak dolazi idućih dana.

Što se prihvaća (bolje bez točke nego s pogrešnom točkom):
  - "adresa": rezultat razine kućnog broja (place_rank >= 30);
  - "ulica": samo kratke lokalne ulice (stambena, neklasificirana, pješačka...), nikad glavne ceste,
    jer duga cesta može biti kilometrima od poslovnice;
  - sve izvan Hrvatske ili grublje od ulice se odbija.
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta
from typing import Callable

from kolicina import norm

NOMINATIM = "https://nominatim.openstreetmap.org/search"
NAJVISE_UPITA = 400            # po pokretanju (~8 min uz 1 upit/s)
PAUZA = 1.1                    # sekundi između upita
PONOVI_NEUSPJELE_NAKON = 30    # dana
LOKALNE_ULICE = {"residential", "unclassified", "living_street", "pedestrian", "service", "tertiary", "road",
                 "footway", "tertiary_link"}
HR = (42.0, 46.7, 13.0, 19.6)


def ocisti_adresu(adresa: str) -> str:
    """'Ulica Svetog Nikole16A' -> 'Ulica Svetog Nikole 16A'; 'A.Senoe 14' -> 'A. Senoe 14'."""
    a = " ".join((adresa or "").split())
    a = re.sub(r"(?<=[^\W\d_])(?=\d)", " ", a)
    a = re.sub(r"\.(?=[^\W\d_])", ". ", a)
    return a.strip(" ,")


def kljuc(adresa: str, grad: str) -> str:
    return f"{norm(ocisti_adresu(adresa))}|{norm(grad)}"


def prihvati(rez: dict) -> str | None:
    """Kvaliteta rezultata ('adresa' / 'ulica') ili None ako nije dovoljno točan."""
    try:
        lat, lon = float(rez["lat"]), float(rez["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    if not (HR[0] < lat < HR[1] and HR[2] < lon < HR[3]):
        return None
    if (rez.get("address") or {}).get("country_code", "hr") != "hr":
        return None
    rang = int(rez.get("place_rank") or 0)
    if rang >= 28:
        return "adresa"
    if rang >= 26 and rez.get("category") == "highway" and rez.get("type") in LOKALNE_ULICE:
        return "ulica"
    return None


def _dohvati_json(url: str, korisnik: str) -> list:
    zahtjev = urllib.request.Request(url, headers={"User-Agent": korisnik, "Accept-Language": "hr"})
    with urllib.request.urlopen(zahtjev, timeout=30) as r:
        return json.loads(r.read())


class Lokacije:
    def __init__(self, predmemorija: dict | None, korisnik: str, najvise: int = NAJVISE_UPITA, pauza: float = PAUZA,
                 dohvati: Callable[[str], list] | None = None, danas: date | None = None):
        self.p = dict((predmemorija or {}).get("a", {}))
        self.korisnik = korisnik
        self.najvise, self.pauza = najvise, pauza
        self.dohvati = dohvati or (lambda url: _dohvati_json(url, korisnik))
        self.danas = danas or date.today()
        self.upita = 0
        self.zadnji = 0.0
        self.stat = {"iz_predmemorije": 0, "novo_adresa": 0, "novo_ulica": 0, "nije_nadeno": 0, "odgodeno": 0, "greska": 0}
        self.prekid = False

    def _upit(self, parametri: dict) -> list:
        cekaj = self.pauza - (time.monotonic() - self.zadnji)
        if cekaj > 0:
            time.sleep(cekaj)
        self.zadnji = time.monotonic()
        self.upita += 1
        p = {**parametri, "format": "jsonv2", "addressdetails": "1", "limit": "3", "countrycodes": "hr"}
        return self.dohvati(NOMINATIM + "?" + urllib.parse.urlencode({k: v for k, v in p.items() if v}))

    def trazi(self, adresa: str, grad: str, pbr: str = "") -> tuple[float, float] | None:
        if not (adresa or "").strip() or not (grad or "").strip():
            return None
        k = kljuc(adresa, grad)
        zapis = self.p.get(k)
        if zapis is not None:
            lat, lon, _kval, dan = zapis
            if lat is not None:
                self.stat["iz_predmemorije"] += 1
                return lat, lon
            try:
                svjez = date.fromisoformat(dan) > self.danas - timedelta(days=PONOVI_NEUSPJELE_NAKON)
            except (TypeError, ValueError):
                svjez = False
            if svjez:
                self.stat["iz_predmemorije"] += 1
                return None
        if self.prekid or self.upita + 2 > self.najvise:
            self.stat["odgodeno"] += 1
            return None
        cista = ocisti_adresu(adresa)
        ulica = cista.split(",")[0].strip()
        upiti = [{"street": ulica, "city": grad.strip(), "postalcode": (pbr or "").strip()},
                 {"q": f"{cista}, {grad.strip()}"}]
        for upit in upiti:
            try:
                rezultati = self._upit(upit)
            except Exception as e:  # noqa: BLE001 - Nominatim nedostupan: stani za danas, zadrži dosadašnje
                self.stat["greska"] += 1
                if "429" in str(e) or "403" in str(e) or self.stat["greska"] >= 5:
                    self.prekid = True
                return None
            for rez in rezultati or []:
                kval = prihvati(rez)
                if kval:
                    lat, lon = round(float(rez["lat"]), 6), round(float(rez["lon"]), 6)
                    self.p[k] = [lat, lon, kval, self.danas.isoformat()]
                    self.stat["novo_" + kval] += 1
                    return lat, lon
        self.p[k] = [None, None, "", self.danas.isoformat()]
        self.stat["nije_nadeno"] += 1
        return None

    def za_objavu(self) -> dict:
        return {"format": 1, "izvor": "OpenStreetMap Nominatim (© OpenStreetMap suradnici, ODbL)",
                "polja": ["lat", "lon", "kvaliteta", "datum"], "a": dict(sorted(self.p.items()))}
