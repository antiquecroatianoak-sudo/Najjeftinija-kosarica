"""Enkripcija: podaci u mirovanju, dvosmjerne sesije i potpisi.

- Glavni ključ (32 B) nastaje pri prvom pokretanju i nikad ne napušta uređaj.
- Iz njega se HKDF-om izvode namjenski ključevi (dnevnik, kopije, oblak...).
- Omotnica: AES-256-GCM s nasumičnim nonceom i pridruženim podacima (AAD).
- Sesija: X25519 razmjena + HKDF -> zaseban ključ za svaki smjer, brojač kao nonce,
  zaštita od ponavljanja. Identitet strana potvrđuje se Ed25519 potpisom.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import struct
from pathlib import Path

from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

OZNAKA = b"E1"


class GreskaSifre(Exception):
    pass


def _zapisi_tajno(p: Path, podaci: bytes) -> None:
    tmp = p.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(podaci)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, p)


def izvedi(kljuc: bytes, namjena: str, duljina: int = 32) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=duljina, salt=None, info=namjena.encode()).derive(kljuc)


class Trezor:
    """Ključevi uređaja u podatkovnoj mapi (datoteke 0600)."""

    def __init__(self, mapa: Path):
        self.mapa = Path(mapa) / "kljucevi"
        self.mapa.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.mapa, 0o700)
        except OSError:
            pass
        self.glavni = self._ucitaj_ili_stvori("glavni.key", lambda: os.urandom(32))
        potpis = self._ucitaj_ili_stvori(
            "potpis.key",
            lambda: Ed25519PrivateKey.generate().private_bytes(
                serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()),
        )
        self.potpisni = Ed25519PrivateKey.from_private_bytes(potpis)

    def _ucitaj_ili_stvori(self, ime: str, stvori) -> bytes:
        p = self.mapa / ime
        if p.exists():
            return p.read_bytes()
        v = stvori()
        _zapisi_tajno(p, v)
        return v

    def kljuc(self, namjena: str) -> bytes:
        return izvedi(self.glavni, "energija/" + namjena)

    @property
    def javni_potpisni(self) -> bytes:
        return self.potpisni.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)

    def id_uredaja(self) -> str:
        return hashlib.sha256(self.javni_potpisni).hexdigest()[:16]

    def potpisi(self, podaci: bytes) -> bytes:
        return self.potpisni.sign(podaci)


def provjeri_potpis(javni: bytes, podaci: bytes, potpis: bytes) -> bool:
    try:
        Ed25519PublicKey.from_public_bytes(javni).verify(potpis, podaci)
        return True
    except (InvalidSignature, ValueError):
        return False


def zapakiraj(kljuc: bytes, podaci: bytes, aad: bytes = b"") -> bytes:
    nonce = os.urandom(12)
    return OZNAKA + nonce + AESGCM(kljuc).encrypt(nonce, podaci, aad)


def otpakiraj(kljuc: bytes, omotnica: bytes, aad: bytes = b"") -> bytes:
    if len(omotnica) < 30 or omotnica[:2] != OZNAKA:
        raise GreskaSifre("nepoznat format omotnice")
    try:
        return AESGCM(kljuc).decrypt(omotnica[2:14], omotnica[14:], aad)
    except InvalidTag as e:
        raise GreskaSifre("podaci su izmijenjeni ili je ključ pogrešan") from e


class Sesija:
    """Dvosmjerno šifrirani kanal (npr. tunel za održavanje, izravna P2P veza u LAN-u).

    Rukovanje: svaka strana pošalje `pozdrav()` (32 B X25519 + 32 B Ed25519 + 64 B potpis),
    zatim pozove `dovrsi(tudji_pozdrav, dopusteni_kljucevi)`. Relej između njih vidi samo
    šifrirani tekst i ne može se predstaviti ni kao jedna strana.
    """

    def __init__(self, trezor_ili_kljuc, uloga: str):
        assert uloga in ("jezgra", "klijent")
        self.uloga = uloga
        self._id = trezor_ili_kljuc.potpisni if isinstance(trezor_ili_kljuc, Trezor) else trezor_ili_kljuc
        self._eph = X25519PrivateKey.generate()
        self._slanje = self._primanje = None
        self._n_out = 0
        self._n_in = 0
        self.tudji_identitet: bytes | None = None

    def pozdrav(self) -> bytes:
        e = self._eph.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        i = self._id.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        return e + i + self._id.sign(self.uloga.encode() + e)

    def dovrsi(self, tudji: bytes, dopusteni: set[bytes] | None = None) -> None:
        if len(tudji) != 128:
            raise GreskaSifre("neispravan pozdrav")
        e, i, s = tudji[:32], tudji[32:64], tudji[64:]
        druga = "klijent" if self.uloga == "jezgra" else "jezgra"
        if not provjeri_potpis(i, druga.encode() + e, s):
            raise GreskaSifre("potpis pozdrava ne odgovara")
        if dopusteni is not None and i not in dopusteni:
            raise GreskaSifre("nepoznat identitet – pristup odbijen")
        zajednicki = self._eph.exchange(X25519PublicKey.from_public_bytes(e))
        moj_e = self._eph.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        sol = b"".join(sorted([moj_e, e]))
        k = HKDF(algorithm=hashes.SHA256(), length=64, salt=sol, info=b"energija/sesija").derive(zajednicki)
        k_j2k, k_k2j = k[:32], k[32:]
        self._slanje, self._primanje = (k_j2k, k_k2j) if self.uloga == "jezgra" else (k_k2j, k_j2k)
        self.tudji_identitet = i

    def sifriraj(self, podaci: bytes) -> bytes:
        if self._slanje is None:
            raise GreskaSifre("sesija nije uspostavljena")
        nonce = struct.pack(">4xQ", self._n_out)
        self._n_out += 1
        return nonce[4:] + AESGCM(self._slanje).encrypt(nonce, podaci, None)

    def desifriraj(self, poruka: bytes) -> bytes:
        if self._primanje is None:
            raise GreskaSifre("sesija nije uspostavljena")
        (n,) = struct.unpack(">Q", poruka[:8])
        if n < self._n_in:
            raise GreskaSifre("ponovljena ili zakašnjela poruka")
        try:
            v = AESGCM(self._primanje).decrypt(b"\0\0\0\0" + poruka[:8], poruka[8:], None)
        except InvalidTag as e:
            raise GreskaSifre("poruka je izmijenjena") from e
        self._n_in = n + 1
        return v


def oznaka_integriteta(kljuc: bytes, podaci: bytes) -> str:
    return hmac.new(kljuc, podaci, hashlib.sha256).hexdigest()
