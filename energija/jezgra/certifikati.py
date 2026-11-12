"""Lokalno tijelo za certifikate (nulta konfiguracija, bez interneta).

Pri prvom pokretanju jezgra stvori vlastiti CA (ECDSA P-256), izda certifikat za svoj
HTTPS/MQTT/tunel poslužitelj i za svaki upareni uređaj ili klijent. Certifikati se
automatski obnavljaju 30 dana prije isteka. Privatni ključ CA-a šifriran je ključem
izvedenim iz glavnog ključa uređaja.

Korisnik jednom potvrdi otisak CA-a (prikazan u sučelju / QR-u na kućištu); nakon toga su
sve veze provjerene bez ručnog podešavanja.
"""
from __future__ import annotations

import datetime as dt
import ipaddress
import socket
import ssl
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from .sifra import Trezor, _zapisi_tajno

TRAJANJE_CA_DANA = 3650
TRAJANJE_DANA = 397
OBNOVI_DANA = 30


def _sada() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class LokalniCA:
    def __init__(self, mapa: Path, trezor: Trezor):
        self.mapa = Path(mapa) / "certifikati"
        self.mapa.mkdir(parents=True, exist_ok=True)
        self._lozinka = trezor.kljuc("ca-kljuc").hex().encode()
        self.id = trezor.id_uredaja()
        kp, cp = self.mapa / "ca.key", self.mapa / "ca.pem"
        if kp.exists() and cp.exists():
            self.kljuc = serialization.load_pem_private_key(kp.read_bytes(), self._lozinka)
            self.cert = x509.load_pem_x509_certificate(cp.read_bytes())
        else:
            self.kljuc = ec.generate_private_key(ec.SECP256R1())
            ime = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, f"Energija lokalni CA {self.id}")])
            self.cert = (
                x509.CertificateBuilder().subject_name(ime).issuer_name(ime)
                .public_key(self.kljuc.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(_sada() - dt.timedelta(minutes=5))
                .not_valid_after(_sada() + dt.timedelta(days=TRAJANJE_CA_DANA))
                .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
                .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), critical=True)
                .sign(self.kljuc, hashes.SHA256())
            )
            _zapisi_tajno(kp, self.kljuc.private_bytes(
                serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                serialization.BestAvailableEncryption(self._lozinka)))
            _zapisi_tajno(cp, self.cert.public_bytes(serialization.Encoding.PEM))

    @property
    def ca_pem(self) -> Path:
        return self.mapa / "ca.pem"

    def otisak(self) -> str:
        h = self.cert.fingerprint(hashes.SHA256()).hex().upper()
        return ":".join(h[i:i + 4] for i in range(0, 32, 4))  # skraćeno za prikaz/QR

    def izdaj(self, ime: str, dns: list[str] | None = None, ip: list[str] | None = None,
              klijent: bool = False) -> tuple[Path, Path]:
        kljuc = ec.generate_private_key(ec.SECP256R1())
        san: list[x509.GeneralName] = [x509.DNSName(d) for d in (dns or [])]
        san += [x509.IPAddress(ipaddress.ip_address(a)) for a in (ip or [])]
        b = (
            x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, ime)]))
            .issuer_name(self.cert.subject).public_key(kljuc.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(_sada() - dt.timedelta(minutes=5))
            .not_valid_after(_sada() + dt.timedelta(days=TRAJANJE_DANA))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.ExtendedKeyUsage(
                [ExtendedKeyUsageOID.CLIENT_AUTH] if klijent else
                [ExtendedKeyUsageOID.SERVER_AUTH, ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False)
        )
        if san:
            b = b.add_extension(x509.SubjectAlternativeName(san), critical=False)
        cert = b.sign(self.kljuc, hashes.SHA256())
        sigurno = "".join(c if c.isalnum() or c in "-_." else "_" for c in ime)
        kp, cp = self.mapa / f"{sigurno}.key", self.mapa / f"{sigurno}.pem"
        _zapisi_tajno(kp, kljuc.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                              serialization.NoEncryption()))
        _zapisi_tajno(cp, cert.public_bytes(serialization.Encoding.PEM))
        return cp, kp

    def treba_obnovu(self, cp: Path) -> bool:
        if not cp.exists():
            return True
        c = x509.load_pem_x509_certificate(cp.read_bytes())
        return c.not_valid_after_utc - _sada() < dt.timedelta(days=OBNOVI_DANA)

    def certifikat_posluzitelja(self) -> tuple[Path, Path]:
        """Vrati (cert, ključ) jezgre; izdaje/obnavlja automatski. Uključuje lokalna imena i IP."""
        cp, kp = self.mapa / "jezgra.pem", self.mapa / "jezgra.key"
        if self.treba_obnovu(cp) or not kp.exists():
            ipovi = {"127.0.0.1"}
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("10.255.255.255", 1))  # ne šalje ništa; samo odabire lokalno sučelje
                ipovi.add(s.getsockname()[0])
                s.close()
            except OSError:
                pass
            return self.izdaj("jezgra", dns=["localhost", "energija.local", f"energija-{self.id[:6]}.local"],
                              ip=sorted(ipovi))
        return cp, kp

    def kontekst_posluzitelja(self, trazi_klijenta: bool = False) -> ssl.SSLContext:
        cp, kp = self.certifikat_posluzitelja()
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.load_cert_chain(cp, kp)
        if trazi_klijenta:
            ctx.verify_mode = ssl.CERT_REQUIRED
            ctx.load_verify_locations(self.ca_pem)
        return ctx

    def kontekst_klijenta(self, cert: Path | None = None, kljuc: Path | None = None) -> ssl.SSLContext:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.load_verify_locations(self.ca_pem)
        if cert and kljuc:
            ctx.load_cert_chain(cert, kljuc)
        return ctx
