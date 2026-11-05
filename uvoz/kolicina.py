"""Tekst, količine, jedinice i barkodovi. Bez vanjskih paketa.

Pravilo: količinu pakiranja uzimamo samo iz podatka koji je trgovina objavila (polje količine/jedinice ili naziv)
i provjeravamo je jediničnom cijenom (cijena po kg/l/kom) kad postoji. Ako se podaci ne slažu, količina je
nepoznata – ništa ne izmišljamo.
"""

from __future__ import annotations

import math
import re
import unicodedata

_DIJAKRITICI = str.maketrans({"č": "c", "ć": "c", "đ": "d", "š": "s", "ž": "z", "Č": "c", "Ć": "c", "Đ": "d", "Š": "s", "Ž": "z"})
_NE_ZNAK = re.compile(r"[^a-z0-9%]+")


def norm(tekst: str | None) -> str:
    """Mala slova, bez dijakritika i interpunkcije, jedan razmak između riječi."""
    if not tekst:
        return ""
    t = str(tekst).translate(_DIJAKRITICI).lower()
    t = unicodedata.normalize("NFKD", t)
    t = "".join(z for z in t if not unicodedata.combining(z))
    return _NE_ZNAK.sub(" ", t).strip()


def norm_pojam(pojam: str) -> str:
    """Pojam iz grupe: završetak razmakom/interpunkcijom znači 'cijela riječ'."""
    n = norm(pojam)
    if pojam and not pojam[-1].isalnum():
        n += " "
    return n


def sadrzi(stog: str, pojam_n: str) -> bool:
    """stog je ' ' + norm(naziv) + ' '; pojam mora početi na početku riječi."""
    return (" " + pojam_n) in stog


# ---------------------------------------------------------------- jedinice
# jedinica -> (osnovna vrsta, faktor do osnovne jedinice)
JEDINICE = {
    "mg": ("kg", 1e-6), "g": ("kg", 1e-3), "gr": ("kg", 1e-3), "grama": ("kg", 1e-3), "gram": ("kg", 1e-3),
    "dag": ("kg", 1e-2), "dkg": ("kg", 1e-2), "kg": ("kg", 1.0), "kgr": ("kg", 1.0),
    "ml": ("l", 1e-3), "cl": ("l", 1e-2), "dl": ("l", 0.1), "l": ("l", 1.0), "lit": ("l", 1.0), "litra": ("l", 1.0),
    "ltr": ("l", 1.0), "lt": ("l", 1.0),
    "kom": ("kom", 1.0), "komad": ("kom", 1.0), "komada": ("kom", 1.0), "kos": ("kom", 1.0), "pcs": ("kom", 1.0),
    "kpl": ("kom", 1.0), "par": ("kom", 1.0),
}
# Iznad ovoga je količina gotovo sigurno pogrešno upisana.
NAJVISE = {"kg": 60.0, "l": 60.0, "kom": 1000.0}

_BROJ = r"(\d+(?:[.,]\d+)?)"
_JED = r"(mg|grama|gram|gr|g|dkg|dag|kgr|kg|ml|cl|dl|litra|lit|ltr|lt|l|komada|komad|kom|kos|pcs|kpl)"
_GRANICA = r"(?![a-z0-9])"
RE_VISE = re.compile(rf"(?<![\d.,])(\d{{1,3}})\s*[x×*]\s*{_BROJ}\s*{_JED}{_GRANICA}", re.I)
RE_VISE_IZA = re.compile(rf"{_BROJ}\s*{_JED}\s*[x×*]\s*(\d{{1,3}}){_GRANICA}", re.I)
RE_JEDNO = re.compile(rf"(?<![\d.,]){_BROJ}\s*{_JED}{_GRANICA}", re.I)


def broj(vrijednost) -> float | None:
    if vrijednost is None:
        return None
    s = str(vrijednost).strip().replace(" ", "")
    if not s:
        return None
    if s.count(",") == 1 and s.count(".") >= 1:      # 1.299,50
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    try:
        b = float(s)
    except ValueError:
        return None
    return b if math.isfinite(b) else None


def _u_osnovnu(iznos: float, jed: str) -> tuple[float, str] | None:
    j = JEDINICE.get(jed.lower())
    if not j or iznos <= 0:
        return None
    vrsta, faktor = j
    k = iznos * faktor
    if k <= 0 or k > NAJVISE[vrsta]:
        return None
    return round(k, 6), vrsta


def iz_teksta(tekst: str | None) -> tuple[float, str] | None:
    """'6x0,5 l' -> (3.0, 'l'); '500 g' -> (0.5, 'kg'); '10 kom' -> (10, 'kom'). Uzima zadnji navod u tekstu."""
    if not tekst:
        return None
    t = str(tekst).translate(_DIJAKRITICI).lower()
    m = list(RE_VISE.finditer(t))
    if m:
        n, iznos, jed = m[-1].groups()
        b = broj(iznos)
        r = _u_osnovnu(b * int(n), jed) if b else None
        if r and int(n) > 0:
            return r
    m = list(RE_VISE_IZA.finditer(t))
    if m:
        iznos, jed, n = m[-1].groups()
        b = broj(iznos)
        r = _u_osnovnu(b * int(n), jed) if b else None
        if r and int(n) > 0:
            return r
    m = list(RE_JEDNO.finditer(t))
    if m:
        iznos, jed = m[-1].groups()
        b = broj(iznos)
        return _u_osnovnu(b, jed) if b else None
    return None


def iz_polja(kolicina: str | None, jedinica: str | None) -> tuple[float, str] | None:
    """Polja 'quantity' i 'unit' iz cjenika."""
    k = (kolicina or "").strip()
    j = (jedinica or "").strip().lower().rstrip(".")
    if k:
        r = iz_teksta(k) if re.search(r"[a-zA-Z]", k) else None
        if r:
            return r
        b = broj(k)
        if b and j in JEDINICE:
            return _u_osnovnu(b, j)
        return None
    return None


def vrsta_jedinice(jedinica: str | None) -> str | None:
    j = (jedinica or "").strip().lower().rstrip(".")
    return JEDINICE[j][0] if j in JEDINICE else None


def slaze_se(a: float, b: float, tolerancija: float = 0.04) -> bool:
    return a > 0 and b > 0 and abs(a - b) / max(a, b) <= tolerancija


def odaberi_kolicinu(polje, naziv, dopuna, implicirana: tuple[float, str] | None):
    """Vrati ((iznos, vrsta) ili None, oznaka izvora).

    implicirana = cijena / jedinična cijena (ako ju je trgovina objavila) – služi samo kao provjera.
    Redoslijed: ručno provjerena dopuna (po barkodu) > polje > naziv, ali samo ako se slaže s jediničnom cijenom.
    """
    kandidati = [(dopuna, "dopuna"), (polje, "polje"), (naziv, "naziv")]
    kandidati = [(k, o) for k, o in kandidati if k]
    if not kandidati:
        return None, "nema"
    if implicirana:
        for k, o in kandidati:
            if k[1] == implicirana[1] and slaze_se(k[0], implicirana[0]):
                return k, o
        if dopuna:
            return dopuna, "dopuna"
        return None, "neslaganje"
    if dopuna:
        return dopuna, "dopuna"
    if polje and naziv and polje[1] == naziv[1] and not slaze_se(polje[0], naziv[0]):
        return None, "neslaganje"
    return kandidati[0]


# ---------------------------------------------------------------- barkod
def barkod(vrijednost: str | None) -> str | None:
    """Važeći EAN/UPC (8, 12, 13 ili 14 znamenki) u obliku od 13 znamenki gdje je moguće; inače None."""
    if not vrijednost:
        return None
    s = str(vrijednost).strip()
    if not s.isdigit():
        return None
    if len(s) == 14 and s.startswith("0"):
        s = s[1:]
    if len(s) == 12:
        s = "0" + s
    if len(s) not in (8, 13, 14) or set(s) == {"0"}:
        return None
    return s


def lijep_naziv(naziv: str) -> str:
    """'MLIJEKO SVJEŽE 2,8% 1L' -> 'Mlijeko svježe 2,8% 1L' (samo za nazive pisane velikim slovima)."""
    n = " ".join(str(naziv or "").split())
    slova = [z for z in n if z.isalpha()]
    if slova and sum(z.isupper() for z in slova) / len(slova) > 0.8:
        n = n.lower()
        n = n[:1].upper() + n[1:]
    return n


_KOLICINA_U_NAZIVU = re.compile(
    r"\d+(?:[.,]\d+)?\s*(?:x\s*\d+(?:[.,]\d+)?\s*)?(?:kg|kgr|g|gr|dag|dkg|mg|l|lit|litra|ml|cl|dl|kom|pak)(?![a-z])",
    re.IGNORECASE)


def naziv_bez_kolicine(naziv: str, kol: tuple[float, str] | None = None) -> str:
    """Naziv za usporedbu istih proizvoda. Uklanja se samo količina koja JEST količina pakiranja ("Šećer 1 kg" =
    "Secer, 1kg"); ostali brojevi ostaju jer razlikuju proizvode (mlijeko 2,8 % ≠ 3,5 %, brašno T-400 ≠ T-850,
    kuhalo 1,7 l ≠ 1,8 l kad je pakiranje "1 kom")."""
    def zamjena(m):
        procitano = iz_teksta(m.group(0))
        if kol and procitano and procitano[1] == kol[1] and abs(procitano[0] - kol[0]) <= 0.01 * kol[0]:
            return " "
        return m.group(0)
    return norm(_KOLICINA_U_NAZIVU.sub(zamjena, naziv or ""))
