"""Simulirana lokacija (vikendica + voćnjak) za razvoj, testove i demonstraciju.

Fizički modeli (pojednostavljeni, ponovljivi uz isti `sjeme`):
- fotonapon (vedro nebo × dnevna naoblaka), hibridni izmjenjivač s baterijom LiFePO4
  (napon ovisan o SoC-u, unutarnji otpor koji polako raste – starenje, zagrijavanje),
- potrošnja vikendice (stanari petak 17 h – nedjelja 18 h + povremeni radni dan),
- bojler, pumpa (rad na suho kao ubačeni kvar), dvije zone vlage tla s isparavanjem i kišom,
- električni pastir: 4 dionice, povratni vod, ubačeni kratki spoj, prekid i vegetacija,
- impulsno brojilo s nepoznatom konstantom (jezgra je mora sama kalibrirati).

Uređaji se jezgri daju izravno (brzo, za višednevne ubrzane simulacije) ili preko
stvarnih protokola: Modbus TCP (SunSpec izmjenjivač/baterija) i MQTT (senzori, releji).
"""
from __future__ import annotations

import json
import math
import random
import time

from .otkrivanje import Uredaj
from .prognoza import zracenje_vedro

N_DIONICA = 4


class Lokacija:
    ZADANI_KVAROVI = [  # (vrsta, parametar, od_dana, do_dana) – raspored iz prvih simulacija
        ("kratki", 3, 1.4, 1.55),       # grana na žici ~3,6 h
        ("prekid", 2, 3.3, 3.5),        # divljač prekinula žicu ~4,8 h
        ("suho", None, 5.2, 5.4),       # bunar presušio
        ("vegetacija", 0.008, 2.0, 99), # odvod raste od 2. dana (po danu)
    ]

    def __init__(self, cfg: dict, pocetak: float, sjeme: int = 7, kvarovi: bool | list = True):
        self.cfg = cfg
        self.t = pocetak
        self.rng = random.Random(sjeme)
        # kvarovi: True = zadani raspored, False = bez kvarova, lista = scenarij
        self.dogadjaji = list(self.ZADANI_KVAROVI) if kvarovi is True else list(kvarovi or [])
        self.kvarovi = bool(self.dogadjaji)
        self.temp_pomak = 0.0           # scenarij: hladnije/toplije od klimatskog prosjeka
        b = cfg["baterija"]
        self.kap_kwh = b["kapacitet_kwh"]
        self.soc = 0.55
        self.r_int = 0.020          # Ω, raste ~0,25 mΩ/dan
        self.bat_temp = 18.0
        self.bat_struja = 0.0
        self.bat_snaga_w = 0.0
        self.naredba_bat: float | None = None
        self.releji = {"bojler": False, "pumpa": False, "uticnice": True, "hladnjak": True}
        self.ventili = {"z1": False, "z2": False}
        self.bojler_kwh = 1.5        # energija u spremniku (max 3)
        self.vlaga = {"z1": 34.0, "z2": 31.0}
        self.pastir_sklopke = {k: True for k in range(1, N_DIONICA + 1)}
        self.pastir_povrat = False
        self.pastir_snaga = 1.0
        self.pastir_bat = 0.8
        self.pastir_punjenje = False
        self.vegetacija = 0.0
        self.impulsi = 0.0
        self.konstanta = 2000.0       # stvarna, jezgri nepoznata
        self.mreza_w = 0.0
        self.neisporuceno_wh = 0.0
        self._dan_vrijeme: dict[int, dict] = {}
        self.pv_w = self.potrosnja_w = 0.0
        self.pumpa_struja = 0.0
        self.pocetak_sim = pocetak
        self.bat_napon = 16 * 3.15
        self.bojler_w = 0.0
        self.suho = False
        self.ogranicenje = 0
        self.r_int_rast = 0.00025  # Ω/dan; scenarij "starenje" ubrzava
        self.izvoz_zabranjen = False
        self.mreza_prisutna = True
        # mjerila udobnosti (da se ušteda ne postiže na račun stanara ili biljaka)
        self.bez_tople_vode_min = 0.0   # minute prisutnosti s praznim bojlerom
        self.stres_biljaka_h = 0.0      # sati zone ispod 22 % vlage
        self.voda_min = 0.0             # minute rada pumpe s vodom

    # ------------------------------------------------------------------ vrijeme / okolina
    def _dan(self, ts: float) -> dict:
        d = int(ts // 86400)
        if d not in self._dan_vrijeme:
            r = random.Random(d * 7919 + 13)
            kisa = r.random() < 0.22
            self._dan_vrijeme[d] = {"naoblaka": r.uniform(0.0, 0.85) if not kisa else r.uniform(0.7, 0.95),
                                    "kisa_mm": r.uniform(3, 14) if kisa else 0.0, "kisa_sat": r.randint(10, 20),
                                    "temp": 13 - 11 * math.cos(2 * math.pi * (time.gmtime(d * 86400).tm_yday - 20) / 365)
                                            + r.uniform(-6, 6)}  # dnevni maksimum; siječanj ~2 °C, srpanj ~24 °C
        return self._dan_vrijeme[d]

    def okolina_temp(self, ts: float) -> float:
        d = self._dan(ts)
        h = time.localtime(ts).tm_hour + time.localtime(ts).tm_min / 60
        return d["temp"] - 6 + 7 * math.sin((h - 9) / 24 * 2 * math.pi) + self.temp_pomak

    def naoblaka(self, ts: float, stvarna: bool = True) -> float:
        """Naoblaka dana; scenarij: "oblacno" (najavljeno) ili "nenajavljeno_oblacno" (samo stvarno)."""
        n = self.aktivni("oblacno", ts)
        if n is None and stvarna:
            n = self.aktivni("nenajavljeno_oblacno", ts)
        return n if n is not None else self._dan(ts)["naoblaka"]

    def prisutni(self, ts: float) -> bool:
        lt = time.localtime(ts)
        wd, h = lt.tm_wday, lt.tm_hour
        if wd == 4 and h >= 17 or wd == 5 or wd == 6 and h < 18:
            return True
        return wd == 2 and 16 <= h < 21  # srijedom navrati poslije posla

    def prognoza_api(self, od_ts: float) -> dict:
        """Ono što bi vratio Open-Meteo za ovu lokaciju (za offline demonstraciju/testove)."""
        sati = [od_ts - od_ts % 3600 + i * 3600 for i in range(48)]
        lok = self.cfg["lokacija"]
        g, t, p, c = [], [], [], []
        for s in sati:
            d = self._dan(s)
            g.append(zracenje_vedro(s + 1800, lok["sirina"], lok["duzina"]) * (1 - 0.75 * self.naoblaka(s, stvarna=False)))
            t.append(self.okolina_temp(s))
            p.append(d["kisa_mm"] / 3 if abs(time.localtime(s).tm_hour - d["kisa_sat"]) <= 1 else 0.0)
            c.append(self.naoblaka(s, stvarna=False) * 100)
        return {"hourly": {"time": sati, "shortwave_radiation": g, "temperature_2m": t, "precipitation": p,
                           "cloud_cover": c}}

    def tarife_api(self, od_ts: float) -> dict:
        """Dinamička satna tarifa (oblik burzovne krivulje: jutarnji i večernji vrh, podnevni pad)."""
        out = []
        pocetak = od_ts - od_ts % 3600
        for i in range(48):
            ts = pocetak + i * 3600
            h = time.localtime(ts).tm_hour
            r = random.Random(int(ts // 3600))
            c = 0.11 + (0.09 if 7 <= h <= 9 else 0) + (0.15 if 18 <= h <= 21 else 0) \
                - (0.06 if 11 <= h <= 15 else 0) - (0.04 if 1 <= h <= 5 else 0) + r.uniform(-0.015, 0.015)
            out.append({"od": ts, "do": ts + 3600, "eur_kwh": round(c, 4), "izvoz_eur_kwh": round(max(0.0, c * 0.55 - 0.02), 4)})
        return {"cijene": out}

    # ------------------------------------------------------------------ pastir (električni model)
    def aktivni(self, vrsta: str, ts: float | None = None):
        """Parametar aktivnog ubačenog događaja te vrste (ili None)."""
        dan = ((self.t if ts is None else ts) - self.pocetak_sim) / 86400
        for v, par, od, do in self.dogadjaji:
            if v == vrsta and od <= dan < do:
                return True if par is None else par
        return None

    def _kvarovi_pastira(self, ts: float) -> tuple[int | None, int | None]:
        """(dionica s kratkim spojem, dionica s prekidom) prema ubačenom rasporedu."""
        return self.aktivni("kratki", ts), self.aktivni("prekid", ts)

    def pastir_naponi(self) -> list[float]:
        kratki, prekid = self._kvarovi_pastira(self.t)
        n = N_DIONICA
        rub = {}  # čvorovi i-1 -- i preko dionice i
        for k in range(1, n + 1):
            if self.pastir_sklopke[k] and prekid != k:
                rub[k] = True
        dosegnuto = {0}
        promjena = True
        while promjena:
            promjena = False
            for k in rub:
                a, b = k - 1, k
                if (a in dosegnuto) != (b in dosegnuto):
                    dosegnuto |= {a, b}
                    promjena = True
            if self.pastir_povrat and 0 in dosegnuto and n not in dosegnuto:
                dosegnuto.add(n)
                promjena = True
        G = 0.0
        for k in range(1, n + 1):
            # kraj dionice k dodiruje čvor k bez sklopke; početak preko S_k
            pod = (k - 1 in dosegnuto and self.pastir_sklopke[k]) or (k in dosegnuto)
            if not pod:
                continue
            g = 0.002
            if k == 4:
                g += self.vegetacija
            if kratki == k:
                g = 0.5
            G += g
        voc = 9.0 * math.sqrt(self.pastir_snaga) if self.pastir_bat > 0.05 else 0.0
        v_izlaz = voc / (1 + 20 * G)
        out = [v_izlaz]
        for k in range(1, n + 1):
            out.append(v_izlaz * (0.97 ** k) if k in dosegnuto else 0.0)
        return [round(x + self.rng.gauss(0, 0.05), 2) if x > 0 else 0.0 for x in out]

    # ------------------------------------------------------------------ korak fizike
    def korak(self, dt: float) -> None:
        self.t += dt
        ts = self.t
        d = self._dan(ts)
        lok = self.cfg["lokacija"]
        g = zracenje_vedro(ts, lok["sirina"], lok["duzina"]) * (1 - 0.75 * self.naoblaka(ts)) * self.rng.uniform(0.9, 1.05)
        f = self.cfg["fotonapon"]
        pv_moguce = f["kwp"] * 1000 * g / 1000 * f["faktor_ucinka"] * (1 - 0.004 * (self.okolina_temp(ts) + g * 0.03 - 25))
        pv_moguce *= 1 - min(0.25, (ts - self.pocetak_sim) / 86400 * 0.004)  # prašina na panelima
        pv_moguce = max(0.0, pv_moguce)

        # potrošnja
        h = time.localtime(ts).tm_hour
        p = 10.0  # usmjernik
        if self.releji["hladnjak"]:
            p += 90.0 if (int(ts) // 600) % 5 < 2 else 0.0
        if self.prisutni(ts):
            p += 140 + (1600 if h in (8, 13, 19) and self.rng.random() < 0.6 else 0) + self.rng.uniform(0, 150)
            t_vani = self.okolina_temp(ts)
            if t_vani < 10:  # električno grijanje: ovisi o vremenu, ne o rasporedu
                p += min(2000.0, 160.0 * (10 - t_vani))
            self.bojler_kwh = max(0.0, self.bojler_kwh - 0.25 * dt / 3600)
            if self.bojler_kwh < 0.3:
                self.bez_tople_vode_min += dt / 60
        if not self.releji["uticnice"]:
            p = min(p, 100.0)
        bojler_w = 0.0
        if self.releji["bojler"] and self.bojler_kwh < 3.0:
            bojler_w = 2000.0
            self.bojler_kwh += 2.0 * dt / 3600
        self.bojler_w = bojler_w
        suho = bool(self.aktivni("suho", ts))  # bunar presušio
        self.suho = suho
        pumpa_w = 0.0
        if self.releji["pumpa"]:
            pumpa_w = 250.0 if suho else 750.0
            self.pumpa_struja = (1.1 if suho else 3.4) + self.rng.gauss(0, 0.05)
        else:
            self.pumpa_struja = 0.0
        pastir_w = 8.0 * self.pastir_snaga
        punjenje_pastira_w = 15.0 if self.pastir_punjenje and self.pastir_bat < 1.0 else 0.0
        self.pastir_bat = min(1.0, max(0.0, self.pastir_bat + (punjenje_pastira_w * 0.9 - pastir_w) * dt / 3600 / 100))
        potreba = p + bojler_w + pumpa_w + punjenje_pastira_w

        # baterija + mreža
        b = self.cfg["baterija"]
        neto = potreba - pv_moguce
        if self.naredba_bat is not None:
            zeljeno = self.naredba_bat
        else:
            zeljeno = -neto  # obični vlastiti način
            if self.ogranicenje & 1:
                zeljeno = min(zeljeno, 0.0)
            if self.ogranicenje & 2:
                zeljeno = max(zeljeno, 0.0)
        zeljeno = max(-b["max_praznjenje_kw"] * 1000, min(b["max_punjenje_kw"] * 1000, zeljeno))
        if zeljeno > 0 and (self.soc >= 0.99 or self.bat_temp < 0):
            zeljeno = 0.0
        if zeljeno < 0 and self.soc <= 0.05:
            zeljeno = 0.0
        mreza = self.cfg["mreza"]["dostupna"] and not self.aktivni("mreza_ispad", ts)
        self.mreza_prisutna = mreza
        if not mreza:  # otočno: baterija mora pokriti ono što sunce ne može
            zeljeno = min(zeljeno, pv_moguce - potreba) if zeljeno > 0 else max(zeljeno, -max(0.0, neto))
        pv = pv_moguce
        m = neto + zeljeno
        if mreza and m < 0 and self.izvoz_zabranjen:  # negativna izvozna cijena: panel se ograničava
            pv += m
            m = 0.0
        if not mreza:
            if m < 0:
                pv += m  # ograničavanje panela
                m = 0.0
            elif m > 0:
                self.neisporuceno_wh += m * dt / 3600
                m = 0.0
        self.bat_snaga_w = zeljeno
        self.soc = min(1.0, max(0.0, self.soc + (zeljeno * (0.95 if zeljeno > 0 else 1 / 0.95)) * dt / 3600 /
                                (self.kap_kwh * 1000)))
        self.r_int += self.r_int_rast * dt / 86400
        napon_otvoreno = 16 * (3.0 + 0.3 * self.soc + 0.05 * math.tanh((self.soc - 0.5) * 6))
        self.bat_struja = zeljeno / max(40.0, napon_otvoreno)
        self.bat_napon = napon_otvoreno + self.bat_struja * self.r_int
        okolina = self.okolina_temp(ts)
        self.bat_temp += ((okolina + 4) - self.bat_temp) * dt / 7200 + self.bat_struja ** 2 * self.r_int * dt / 4e5
        self.pv_w, self.potrosnja_w, self.mreza_w = pv, potreba, m
        if m > 0:
            self.impulsi += m / 1000 * dt / 3600 * self.konstanta

        # tlo
        for z in self.vlaga:
            et = (0.15 + 0.25 * max(0.0, g) / 800) * (1 + max(0, okolina - 20) / 20)
            kisa = d["kisa_mm"] / 3 if abs(h - d["kisa_sat"]) <= 1 else 0.0
            dodatak = kisa * 1.2
            if self.releji["pumpa"] and self.ventili[z] and not suho:
                dodatak += 33.0  # %/h dok ventil i pumpa rade
                self.voda_min += dt / 60
            self.vlaga[z] = min(48.0, max(5.0, self.vlaga[z] + (dodatak - et * (1.3 if z == "z2" else 1.0)) * dt / 3600))
            if self.vlaga[z] < 22.0:
                self.stres_biljaka_h += dt / 3600

        stopa, od = 0.0, 0.0
        for v, par, od_d, _ in self.dogadjaji:
            if v == "vegetacija":
                stopa, od = par, od_d
        self.vegetacija = min(0.09, max(0.0, (ts - self.pocetak_sim) / 86400 - od) * stopa) if stopa else 0.0

    # ------------------------------------------------------------------ očitanja / naredbe
    def ocitanja(self) -> dict[str, float]:
        v = self.pastir_naponi()
        o = {
            "pv_snaga_w": round(self.pv_w, 1), "potrosnja_w": round(self.potrosnja_w, 1),
            "baterija_soc": round(self.soc, 4), "baterija_napon_v": round(self.bat_napon, 3),
            "baterija_struja_a": round(self.bat_struja, 2), "baterija_temp_c": round(self.bat_temp, 2),
            "baterija_snaga_w": round(self.bat_snaga_w, 1),
            "mreza_prisutna": 1.0 if self.mreza_prisutna else 0.0,
            "okolina_temp_c": round(self.okolina_temp(self.t), 1),
            "brojilo_impulsi": int(self.impulsi),
            "tlo_z1_vlaga": round(self.vlaga["z1"] + self.rng.gauss(0, 0.15), 2),
            "tlo_z2_vlaga": round(self.vlaga["z2"] + self.rng.gauss(0, 0.15), 2),
            "pumpa_struja_a": round(self.pumpa_struja, 2), "bojler_snaga_w": self.bojler_w,
            "bojler_temp_c": round(15.0 + self.bojler_kwh / 3.0 * 45.0, 1),  # osjetnik na spremniku
            "pastir_baterija_soc": round(self.pastir_bat, 3),
        }
        for k, x in enumerate(v):
            o[f"pastir_v{k}_kv"] = x
        return o

    def postavi(self, kanal: str, v: float) -> bool:
        if kanal == "baterija_snaga_w":
            self.naredba_bat = v
        elif kanal == "izvoz_zabranjen":
            self.izvoz_zabranjen = v >= 0.5
        elif kanal == "baterija_auto":
            self.naredba_bat = None
            self.ogranicenje = 0
        elif kanal == "baterija_ogranicenje":  # vlastiti način + ograničenje smjera (bit0 punjenje, bit1 pražnjenje)
            self.naredba_bat = None
            self.ogranicenje = int(v) & 3
        elif kanal.startswith("rele_pastir_k"):
            self.pastir_sklopke[int(kanal[13:])] = v >= 0.5
        elif kanal == "rele_pastir_povrat":
            self.pastir_povrat = v >= 0.5
        elif kanal == "rele_pastir_punjenje":
            self.pastir_punjenje = v >= 0.5
        elif kanal == "pastir_snaga":
            self.pastir_snaga = max(0.3, min(1.0, v))
        elif kanal.startswith("ventil_"):
            self.ventili[kanal[7:]] = v >= 0.5
        elif kanal.startswith("rele_") and kanal[5:] in self.releji:
            self.releji[kanal[5:]] = v >= 0.5
        else:
            return False
        return True


class SimUredaj(Uredaj):
    """Izravni pristup simulaciji (bez protokola) – za brze višednevne simulacije."""
    protokol = "simulacija"

    def __init__(self, lok: Lokacija, id_: str, tip: str, kanali: list[str] | None):
        self.lok, self.id, self.tip, self.kanali = lok, id_, tip, kanali

    def citaj(self) -> dict[str, float]:
        o = self.lok.ocitanja()
        return {k: v for k, v in o.items() if self.kanali is None or k in self.kanali or
                any(k.startswith(p[:-1]) for p in self.kanali if p.endswith("*"))}

    def postavi(self, kanal: str, vrijednost: float) -> bool:
        return self.lok.postavi(kanal, vrijednost)


def izravni_uredaji(lok: Lokacija) -> list[Uredaj]:
    return [
        SimUredaj(lok, "sim-izmjenjivac", "izmjenjivac",
                  ["pv_snaga_w", "potrosnja_w", "baterija_soc", "baterija_napon_v", "baterija_struja_a",
                   "baterija_temp_c", "baterija_snaga_w", "okolina_temp_c", "mreza_prisutna"]),
        SimUredaj(lok, "sim-impulsi", "impulsno_brojilo", ["brojilo_impulsi"]),
        SimUredaj(lok, "sim-tlo", "senzor_tla", ["tlo_z1_vlaga", "tlo_z2_vlaga"]),
        SimUredaj(lok, "sim-pumpa", "pumpa", ["pumpa_struja_a", "bojler_snaga_w", "bojler_temp_c"]),
        SimUredaj(lok, "sim-pastir", "pastir", ["pastir_*"]),
    ]


# ------------------------------------------------------------------ preko protokola
class ProtokolniMost:
    """Izlaže simulaciju kao stvarne uređaje: SunSpec preko Modbus TCP-a i MQTT senzore."""

    def __init__(self, lok: Lokacija, broker_port: int):
        from .modbus import ModbusPosluzitelj, Registri
        from .mqtt import Klijent

        self.lok = lok
        self.reg = Registri()
        self._sunspec_kostur()
        self.modbus = ModbusPosluzitelj({1: self.reg}, pri_upisu=self._upis).pokreni()
        self.mqtt = Klijent("sim-senzori", port=broker_port)
        self.mqtt.pri_poruci = self._naredba
        self.mqtt.pokreni()
        self.mqtt.spojen.wait(5)
        self.mqtt.pretplati("sim/+/set")
        kanali = {k: {"tema": f"sim/{k}"} for k in lok.ocitanja() if not k.startswith(("pv_", "baterija_soc"))}
        upravljanje = {k: {"tema": f"sim/{k}/set"} for k in
                       ["rele_bojler", "rele_pumpa", "rele_uticnice", "rele_hladnjak", "ventil_z1", "ventil_z2",
                        "rele_pastir_povrat", "rele_pastir_punjenje", "pastir_snaga", "baterija_snaga_w", "baterija_auto", "baterija_ogranicenje"]
                       + [f"rele_pastir_k{k}" for k in range(1, N_DIONICA + 1)]}
        self.mqtt.objavi("energija/otkrij/sim-farma", json.dumps(
            {"id": "sim-farma", "tip": "farma", "kanali": kanali, "upravljanje": upravljanje}), zadrzi=True)

    def _sunspec_kostur(self) -> None:
        r = self.reg
        r.postavi("holding", 40000, [0x5375, 0x6E53, 1, 66])
        ime = b"EnergijaSim".ljust(32, b"\0")
        r.postavi("holding", 40004, [int.from_bytes(ime[i:i + 2], "big") for i in range(0, 32, 2)])
        r.postavi("holding", 40020, [0] * 50)
        a103 = 40070
        r.postavi("holding", a103, [103, 50] + [0] * 50)
        a124 = a103 + 52
        r.postavi("holding", a124, [124, 24] + [0] * 24)
        r.postavi("holding", a124 + 2, [3000])           # WChaMax 3000 W, SF 0
        r.postavi("holding", a124 + 22, [0x10000 - 1])   # ChaState_SF = -1 (0,1 %)
        r.postavi("holding", a124 + 24, [0x10000 - 2])   # InBatV_SF = -2
        r.postavi("holding", a124 + 25, [0])
        r.postavi("holding", a124 + 26, [0xFFFF, 0])
        self.a103, self.a124 = a103, a124

    def osvjezi(self) -> None:
        o = self.lok.ocitanja()
        self.reg.postavi("holding", self.a103 + 14, [int(o["pv_snaga_w"]) & 0xFFFF, 0])
        self.reg.postavi("holding", self.a124 + 8, [int(o["baterija_soc"] * 1000)])
        self.reg.postavi("holding", self.a124 + 10, [int(o["baterija_napon_v"] * 100)])
        for k, v in o.items():
            if not k.startswith(("pv_", "baterija_soc")):
                self.mqtt.objavi(f"sim/{k}", json.dumps(v))

    def _upis(self, jed: int, adr: int, v: list[int]) -> None:
        a = self.a124
        if a + 5 <= adr <= a + 13:
            h = self.reg.holding
            mod, izl, ul = h.get(a + 5, 0), h.get(a + 12, 0), h.get(a + 13, 0)
            if mod == 0:
                self.lok.postavi("baterija_auto", 1)
            elif izl == 0 and ul == 0:
                self.lok.postavi("baterija_ogranicenje", mod)
            else:
                self.lok.postavi("baterija_snaga_w", 3000 * ul / 100 - 3000 * izl / 100)

    def _naredba(self, tema: str, poruka: bytes) -> None:
        kanal = tema.split("/")[1]
        txt = poruka.decode().strip().upper()
        v = 1.0 if txt == "ON" else 0.0 if txt == "OFF" else float(txt)
        self.lok.postavi(kanal, v)

    def zaustavi(self) -> None:
        self.modbus.zaustavi()
        self.mqtt.zaustavi()
