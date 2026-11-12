"""Univerzalni adapter za optičko očitanje impulsne LED diode na bilo kojem brojilu.

Fototranzistor/fotodioda na brojilu daje uzorke (ADC 0..4095). Algoritam se sam nivelira:
- osnovna razina (ambijentalno svjetlo) prati se sporim EWMA-om samo dok LED ne svijetli,
- vršna ovojnica polako opada, pa se prag prilagođava jačini LED-a i udaljenosti,
- prag s histerezom (60 % / 40 % raspona) i minimalna širina/razmak impulsa uklanjaju šum,
- ako je kontrast premali (adapter pomaknut, poklopac zamagljen), stanje je "nema_signala".

Konstanta brojila (imp/kWh) kalibrira se sama pri prvom pokretanju: jezgra kratko uključi
trošilo poznate snage (npr. bojler) i iz promjene učestalosti impulsa izračuna konstantu,
pa je zaokruži na najbližu standardnu vrijednost (±15 %). Bez mogućnosti kalibracije
koristi se 1000 imp/kWh i rezultat je označen kao pretpostavka.

Isti algoritam predviđen je za firmware adaptera (mikrokontroler broji impulse i šalje
zbrojeve preko MQTT-a); ovdje služi i za simulaciju i za adaptere koji šalju sirove uzorke.
"""
from __future__ import annotations

STANDARDNE_KONSTANTE = [100, 200, 250, 400, 500, 800, 1000, 1200, 1600, 2000, 2500, 3200, 4000, 5000, 6400, 10000]


class DetektorImpulsa:
    def __init__(self, frekvencija_hz: float = 200.0, min_sirina_s: float = 0.004, min_razmak_s: float = 0.05):
        self.fs = frekvencija_hz
        self.min_sirina = max(1, int(min_sirina_s * frekvencija_hz))
        self.min_razmak = max(1, int(min_razmak_s * frekvencija_hz))
        self.osnova: float | None = None
        self.vrh: float | None = None
        self.sum = 5.0
        self._u_impulsu = False
        self._sirina = 0
        self._od_zadnjeg = 10 ** 9
        self._n = 0
        self.impulsi = 0
        self.vremena: list[float] = []  # vrijeme (s od početka) svakog impulsa
        self.stanje = "kalibracija"

    def uzorak(self, x: float) -> bool:
        """Obradi jedan uzorak; vrati True kad je potvrđen novi impuls."""
        self._n += 1
        self._od_zadnjeg += 1
        if self.osnova is None:
            self.osnova = self.vrh = float(x)
            return False
        raspon = self.vrh - self.osnova
        prag_gore = self.osnova + 0.6 * raspon
        prag_dolje = self.osnova + 0.4 * raspon
        dovoljno = raspon > max(40.0, 6 * self.sum)

        # samoniveliranje
        if not self._u_impulsu:
            odmak = x - self.osnova
            if odmak < 0.3 * max(raspon, 1.0):
                self.osnova += 0.002 * odmak
                self.sum += 0.01 * (abs(odmak) - self.sum)
        if x > self.vrh:
            self.vrh = float(x)
        else:
            self.vrh -= (self.vrh - self.osnova) * 0.00002  # sporo opadanje (~dugi odmor LED-a)
        if self.vrh < self.osnova:
            self.vrh = self.osnova

        if not dovoljno:
            self.stanje = "nema_signala" if self._n > 10 * self.fs else "kalibracija"
            return False
        self.stanje = "radi"
        novi = False
        if not self._u_impulsu and x > prag_gore:
            self._u_impulsu, self._sirina = True, 1
        elif self._u_impulsu:
            if x < prag_dolje:
                self._u_impulsu = False
                if self._sirina >= self.min_sirina and self._od_zadnjeg >= self.min_razmak:
                    self.impulsi += 1
                    self.vremena.append(self._n / self.fs)
                    del self.vremena[:-50]
                    self._od_zadnjeg = 0
                    novi = True
            else:
                self._sirina += 1
        return novi

    def ucestalost(self, prozor: int = 5) -> float | None:
        """Impulsa po satu iz zadnjih `prozor` razmaka."""
        v = self.vremena[-(prozor + 1):]
        if len(v) < 2:
            return None
        return (len(v) - 1) / (v[-1] - v[0]) * 3600.0


class ImpulsnoBrojilo:
    def __init__(self, konstanta: float | None = None):
        self.konstanta = konstanta or 1000.0
        self.konstanta_izvor = "kalibrirano" if konstanta else "pretpostavka"
        self.detektor = DetektorImpulsa()
        self.energija_kwh = 0.0

    def impuls(self) -> None:
        self.energija_kwh += 1.0 / self.konstanta

    def snaga_w(self) -> float | None:
        f = self.detektor.ucestalost()
        return None if f is None else f / self.konstanta * 1000.0

    @staticmethod
    def kalibriraj(ucestalost_prije: float, ucestalost_poslije: float, poznata_snaga_w: float) -> tuple[float, str]:
        """Iz promjene učestalosti (imp/h) pri uključenju poznatog trošila izračunaj imp/kWh."""
        delta = ucestalost_poslije - ucestalost_prije
        if poznata_snaga_w <= 0 or delta <= 0:
            return 1000.0, "pretpostavka"
        izmjereno = delta / (poznata_snaga_w / 1000.0)
        najbliza = min(STANDARDNE_KONSTANTE, key=lambda c: abs(c - izmjereno) / c)
        if abs(najbliza - izmjereno) / najbliza <= 0.15:
            return float(najbliza), "kalibrirano"
        return round(izmjereno, 1), "kalibrirano-nestandardno"
