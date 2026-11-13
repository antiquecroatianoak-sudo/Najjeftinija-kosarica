"""Lokalna jezgra: jedan autonomni ciklus odlučivanja na temelju očitanja senzora.

Redoslijed u svakom koraku (zaštita uvijek prije optimizacije):
 1. očitaj sve uređaje (nedostupan uređaj ne ruši korak),
 2. anomalije i tvrde granice -> preventivno isključenje trošila (po prioritetu),
 3. kaskada niske baterije u otočnom radu (prvo fleksibilna, zatim nekritična trošila),
 4. električni pastir (traženje/izolacija kvara, napajanje aparata),
 5. navodnjavanje (vlaga, kiša, višak sunca),
 6. plan baterije i fleksibilnih trošila (tarife + prognoza + naučene navike),
 7. naredbe uređajima, zapis u šifrirani dnevnik, satni zbroj, snimka stanja.

Oporavak: pri pokretanju se učita zadnja ispravna snimka i ponove svi zapisi telemetrije
iz dnevnika nakon nje – satni zbrojevi, učenje i stanje zaštite nastavljaju bez rupe.
"""
from __future__ import annotations

import time
from pathlib import Path

from . import izvjestaji, konfig, resursi
from .anomalije import Detektor
from .impulsi import ImpulsnoBrojilo
from .kopije import Kopije
from .navodnjavanje import Navodnjavanje
from .optimizator import planiraj_bateriju, smjesti_fleksibilna
from .pastir import Pastir
from .pohrana import Dnevnik, Snimka
from .povijest import Povijest
from .prognoza import Prognoza
from .rubni_ai import RubniModel, provjera_profila, ulazi
from .sifra import Trezor
from .sinkronizacija import Sinkronizacija
from .tarife import Tarife
from .ucenje import Navike

TELEMETRIJA = "o"
# koliko dugo trošilo ostaje isključeno nakon kritične anomalije (s)
TRAJANJE_ZASTITE = {"rad_na_suho": 6 * 3600, "blokada": 24 * 3600, "pregrijavanje": 3600}


class Jezgra:
    def __init__(self, mapa: Path, cfg: dict | None = None, sat=None, uredaji: list | None = None,
                 dohvati_prognozu=None, dohvati_tarife=None, n_dionica: int = 4, povratni_vod: bool = True,
                 posalji_oblaku=None):
        self.mapa = Path(mapa)
        self.mapa.mkdir(parents=True, exist_ok=True)
        self.cfg = cfg or konfig.ucitaj(self.mapa)
        self.sat = sat or time.time
        self.trezor = Trezor(self.mapa)
        self.dnevnik = Dnevnik(self.mapa, self.trezor.kljuc("dnevnik"))
        self.arhiva = Dnevnik(self.mapa / "arhiva", self.trezor.kljuc("arhiva"), fsync_svakih=1)
        self.snimka = Snimka(self.mapa, self.trezor.kljuc("snimka"))
        st, slijed, izvor = self.snimka.ucitaj()
        self.uredaji = list(uredaji or [])
        self.dohvati_prognozu, self.dohvati_tarife = dohvati_prognozu, dohvati_tarife

        self.detektor = Detektor(self.cfg, st.get("detektor"))
        self.navike = Navike(st.get("navike"))
        self.navodnjavanje = Navodnjavanje(self.cfg, st.get("navodnjavanje"))
        self.pastir = Pastir(self.cfg, n_dionica, povratni_vod, st.get("pastir"))
        self.tarife = Tarife(self.cfg, self.mapa)
        self.prognoza = Prognoza(self.cfg, self.mapa)
        self.sinkronizacija = Sinkronizacija(self.cfg, self.trezor, self.arhiva, st.get("sinkronizacija"),
                                             posalji=posalji_oblaku)
        self.kopije = Kopije(self.mapa, self.trezor.kljuc("kopije"), self.cfg["kopije"]["odredista"],
                             self.cfg["kopije"]["generacija"])
        k = st.get("brojilo", {})
        self.brojilo = ImpulsnoBrojilo(k.get("konstanta"))
        self.brojilo.konstanta_izvor = k.get("izvor", self.brojilo.konstanta_izvor)
        self.kalibracija: dict = st.get("kalibracija") or {"faza": "ceka"}

        self.releji: dict[str, bool] = st.get("releji") or {"bojler": False, "pumpa": False, "uticnice": True,
                                                            "hladnjak": True}
        self.ventili: dict[str, bool] = {}
        self.zastita_do: dict[str, float] = st.get("zastita_do", {})
        self.zabrana_punjenja_do = st.get("zabrana_punjenja_do", 0.0)
        self.agregat: dict | None = st.get("agregat")
        self.dan = st.get("dan")
        self.dnevno: dict = st.get("dnevno") or {}
        self.plan: list[dict] = []
        self.raspored: dict[str, list[int]] = {}
        self.plan_ts = 0.0
        self.parametri: dict = {}
        self.nacin = "NORMALNO"
        self.zadnje_ocitanje: dict = {}
        self.zadnji_ts: float | None = st.get("zadnji_ts")
        self.zadnja_snimka = 0.0
        self.zadnja_kopija = st.get("zadnja_kopija", 0.0)
        self.izvjestaji_izradjeni: list[str] = st.get("izvjestaji", [])
        self.odrzavanje: list[dict] = []
        self.offline_uredaji: dict[str, str] = {}
        self.pastir_izlaz: dict = {}
        self.navodnjavanje_izlaz: dict = {}
        self._naredbe_zadnje: dict[str, tuple[float, float]] = {}
        self._kes_ustede: tuple[float, dict] | None = None
        self.u_sigurnom = False
        # rubni AI + napredne postavke (ručno premošćivanje) + transparentne odluke
        self.ai = RubniModel(st.get("ai"))
        self.napredno: dict = {"ai": True, "baterija_nacin": "auto", "rucna_snaga_w": 0.0, "rucno_do": 0.0}
        self.napredno.update(st.get("napredno") or {})
        self.ai_provjera: dict = {}
        self.ai_aktivan = False
        self._ai_zadnje_ucenje = st.get("ai_zadnje_ucenje", 0.0)
        self.odluke: dict[str, dict] = {}
        self._prisutnost = 0.0
        self._mreza_bila = True
        self.povijest = Povijest()
        self.zahtjevi_mreze: list[dict] = st.get("zahtjevi_mreze", [])  # zahtjevi operatora za fleksibilnost
        self._usteda_dani: dict[str, dict] = {}
        self.mreza_dostupna = self.cfg["mreza"]["dostupna"]
        self.rucno: dict[str, tuple[bool, float]] = {}  # ručne naredbe s aplikacije (trošilo -> (stanje, do))
        self.kod_uparivanja: str | None = None

        # --- oporavak bez gubitka: ponovi telemetriju nakon snimke
        self._zakljuceni = {z["d"]["ts"] for z in self.arhiva.citaj(0, {"sat"})}
        self.sati: list[dict] = [z["d"] for z in self.arhiva.citaj(0, {"sat"})]
        self._ponavljanje = True
        ponovljeno = 0
        for z in self.dnevnik.citaj(slijed, {TELEMETRIJA}):
            self._akumuliraj(z["d"], z["t"])
            self.zadnji_ts = z["t"]
            ponovljeno += 1
        self._ponavljanje = False
        try:
            for z in self.dnevnik.citaj_od_vremena(self.sat() - 48 * 3600, {TELEMETRIJA}):
                self.povijest.dodaj(z["t"], self._za_povijest(z["d"]))
        except Exception as e:  # povijest za grafikone nikad ne smije spriječiti pokretanje
            self._dogadjaj("povijest", {"poruka": f"Povijest grafikona nije učitana: {e}"})
        self.oporavak = {"snimka": izvor, "ponovljeno_zapisa": ponovljeno,
                         "odrezano_bajtova": self.dnevnik.oporavak["odrezano_bajtova"] +
                         self.arhiva.oporavak["odrezano_bajtova"]}
        self._dogadjaj("pokretanje", {"poruka": "Jezgra pokrenuta", **self.oporavak})

    # ------------------------------------------------------------------ pomoćno
    def _dogadjaj(self, vrsta: str, d: dict, ts: float | None = None) -> None:
        if not self._ponavljanje:
            self.arhiva.zapisi(vrsta, d, kriticno=True, ts=ts if ts is not None else self.sat())

    def _ocitaj(self) -> dict[str, float]:
        o: dict[str, float] = {}
        for u in self.uredaji:
            try:
                o.update(u.citaj())
                if u.id in self.offline_uredaji:
                    self._dogadjaj("uredaj", {"poruka": f"{u.id} ponovno dostupan"})
                    self.offline_uredaji.pop(u.id)
            except Exception as e:
                if u.id not in self.offline_uredaji:
                    self._dogadjaj("uredaj", {"poruka": f"{u.id} nedostupan: {e}", "ozbiljnost": "upozorenje"})
                self.offline_uredaji[u.id] = str(e)
        return o

    def _postavi(self, kanal: str, v: float, ts: float, osvjezi_s: float = 60.0) -> None:
        zadnje = self._naredbe_zadnje.get(kanal)
        if zadnje and abs(zadnje[0] - v) < 1e-6 and ts - zadnje[1] < osvjezi_s:
            return
        for u in self.uredaji:
            try:
                if u.postavi(kanal, v):
                    self._naredbe_zadnje[kanal] = (v, ts)
                    return
            except Exception as e:
                self.offline_uredaji[u.id] = str(e)

    def _zasticeno(self, trosilo: str, ts: float) -> bool:
        return self.zastita_do.get(trosilo, 0) > ts

    # ------------------------------------------------------------------ satni zbroj (i za ponavljanje)
    def _akumuliraj(self, d: dict, ts: float) -> None:
        sat_pocetak = ts - ts % 3600
        if self.agregat and self.agregat["ts"] != sat_pocetak:
            self._zakljuci_sat()
        if not self.agregat:
            self.agregat = {"ts": sat_pocetak, "pv_kwh": 0.0, "potrosnja_kwh": 0.0, "uvoz_kwh": 0.0,
                            "izvoz_kwh": 0.0, "trosak_eur": 0.0, "bat_protok_kwh": 0.0, "bat_neto_kwh": 0.0, "bojler_kwh": 0.0,
                            "pumpa_kwh": 0.0, "pumpa_min": 0.0, "preskoceno_min": 0.0, "neisporuceno_kwh": 0.0,
                            "soc_pocetak": d.get("soc"), "cijena_kupnja": d["ck"], "cijena_prodaja": d["cp"],
                            "pastir_ok_s": 0.0, "pastir_s": 0.0, "n": 0}
        a, h = self.agregat, d["dt"] / 3600
        m = d["mreza"]
        a["pv_kwh"] += d["pv"] * h / 1000
        a["potrosnja_kwh"] += d["potr"] * h / 1000
        a["uvoz_kwh"] += max(0.0, m) * h / 1000
        a["izvoz_kwh"] += max(0.0, -m) * h / 1000
        a["trosak_eur"] += (max(0.0, m) * d["ck"] - max(0.0, -m) * d["cp"]) * h / 1000
        a["bat_protok_kwh"] += abs(d.get("bat", 0.0)) * h / 1000
        a["bat_neto_kwh"] += d.get("bat", 0.0) * h / 1000
        a["bojler_kwh"] += d.get("bojler", 0.0) * h / 1000
        a["pumpa_kwh"] += d.get("pumpa_w", 0.0) * h / 1000
        a["pumpa_min"] += (d["dt"] / 60) if d.get("pumpa") else 0.0
        a["preskoceno_min"] += d.get("presk", 0.0)
        a["neisporuceno_kwh"] += d.get("neisp", 0.0) * h / 1000
        if d.get("pastir_ok") is not None:
            a["pastir_s"] += d["dt"]
            a["pastir_ok_s"] += d["dt"] if d["pastir_ok"] else 0.0
        a["n"] += 1
        if d.get("soc") is not None:
            a["soc_kraj"] = d["soc"]
        t = d.get("o", {}).get("okolina_temp_c")
        if t is not None:
            a["temp_zbroj"] = a.get("temp_zbroj", 0.0) + t
            a["temp_n"] = a.get("temp_n", 0) + 1
        if d.get("potr") is not None:
            self.navike.dodaj(ts, d["potr"] - d.get("bojler", 0.0) - d.get("pumpa_w", 0.0), d["dt"])

    def _zakljuci_sat(self) -> None:
        a = self.agregat
        self.agregat = None
        if not a or a["n"] == 0:
            return
        a["pastir_dostupnost"] = a["pastir_ok_s"] / a["pastir_s"] if a["pastir_s"] else None
        for k in ("pastir_ok_s", "pastir_s"):
            a.pop(k)
        if a.get("temp_n"):
            a["temp"] = round(a.pop("temp_zbroj") / a.pop("temp_n"), 2)
        if a["ts"] in self._zakljuceni:
            return  # već zapisano prije pada (ponavljanje)
        self._zakljuceni.add(a["ts"])
        self._ai_uzorak(a)
        self.sati.append(a)
        del self.sati[:-24 * 400]
        self.arhiva.zapisi("sat", a, kriticno=True, ts=a["ts"] + 3600)

    # ------------------------------------------------------------------ rubni AI
    def primijeni_ai_profil(self, razlog: str = "provjera") -> dict:
        """Prije uključivanja (i svakog sata) izmjeri zauzeće memorije/CPU-a na uređaju."""
        self.ai_provjera = provjera_profila()
        prije = self.ai_aktivan
        self.ai_aktivan = bool(self.napredno.get("ai")) and self.ai_provjera["dopusteno"]
        if prije != self.ai_aktivan or razlog != "periodicno":
            if self.ai_aktivan:
                poruka = f"AI profil aktivan (slobodno {self.ai_provjera['slobodno_mb']} MB)"
            elif not self.napredno.get("ai"):
                poruka = "AI profil ručno isključen"
            else:
                poruka = "AI profil nije primijenjen: " + "; ".join(self.ai_provjera["razlozi"])
            self._dogadjaj("ai", {"poruka": poruka, "provjera": self.ai_provjera, "razlog": razlog})
        return self.ai_provjera

    def _potrosnja_sata(self, ts: float) -> float | None:
        for s in reversed(self.sati[-200:]):
            if s["ts"] == ts:
                return (s["potrosnja_kwh"] - s.get("bojler_kwh", 0.0) - s.get("pumpa_kwh", 0.0)) * 1000
        return None

    def _ai_uzorak(self, a: dict) -> None:
        stvarno = (a["potrosnja_kwh"] - a.get("bojler_kwh", 0.0) - a.get("pumpa_kwh", 0.0)) * 1000
        profil = self.navike.prognoza(a["ts"] + 1, 1)[0]
        x = ulazi(a["ts"], self._potrosnja_sata(a["ts"] - 3600), self._potrosnja_sata(a["ts"] - 86400),
                  self._potrosnja_sata(a["ts"] - 7 * 86400), profil, a.get("temp"), self.ai.temp_ref)
        self.ai.dodaj_uzorak(x, stvarno, profil)
        self.ai.osvjezi_temp(a.get("temp"))

    def _ai_prognoza(self, ts: float, profil: list[float], temp: list | None = None) -> tuple[list[float], dict]:
        k = self.ai.kvaliteta()
        if not (self.ai_aktivan and k["koristi_se"]):
            razlog = ("AI isključen ili nije dopušten na ovom uređaju" if not self.ai_aktivan else
                      f"AI još nije bolji od profila navika ({k['sati_provjere']} h provjere, "
                      f"MAE {k['mae_ai_w']} W prema {k['mae_profil_w']} W)")
            return profil, {"izvor": "profil navika", "razlog": razlog} | k
        pocetak = ts - ts % 3600
        poznato = {s["ts"]: (s["potrosnja_kwh"] - s.get("bojler_kwh", 0) - s.get("pumpa_kwh", 0)) * 1000
                   for s in self.sati[-200:]}
        out = []
        for i, p in enumerate(profil):
            t = pocetak + i * 3600
            x = ulazi(t, poznato.get(t - 3600), poznato.get(t - 86400), poznato.get(t - 7 * 86400), p,
                      temp[i] if temp and i < len(temp) else None, self.ai.temp_ref)
            v = max(0.0, p + self.ai.zakljuci(x))
            poznato[t] = v  # rekurzivno za dulji horizont
            out.append(v)
        return out, {"izvor": "rubni AI (int8)",
                     "razlog": f"AI točniji od profila: MAE {k['mae_ai_w']} W prema {k['mae_profil_w']} W"} | k

    def _odluka(self, kljuc: str, odluka: str, razlog: str, izvor: str, ts: float, **ulazi_) -> None:
        """Transparentan zapis: što je odlučeno, zašto, na temelju čega. Promjena ide u arhivu."""
        prije = self.odluke.get(kljuc)
        self.odluke[kljuc] = {"odluka": odluka, "razlog": razlog, "izvor": izvor, "ts": ts, "ulazi": ulazi_}
        if not prije or (prije["odluka"], prije["izvor"]) != (odluka, izvor):
            self._dogadjaj("odluka", {"podsustav": kljuc, "odluka": odluka, "razlog": razlog, "izvor": izvor,
                                      "poruka": f"{kljuc}: {odluka} – {razlog}"}, ts)

    def postavi_napredno(self, promjene: dict) -> dict:
        """Ručno premošćivanje iz naprednih postavki. Sigurnosne granice se ne mogu isključiti."""
        dopusteni = {"auto", "vlastita", "bez_punjenja_iz_mreze", "rucno"}
        if "ai" in promjene:
            self.napredno["ai"] = bool(promjene["ai"])
        if "baterija_nacin" in promjene:
            if promjene["baterija_nacin"] not in dopusteni:
                raise ValueError("nepoznat način baterije")
            self.napredno["baterija_nacin"] = promjene["baterija_nacin"]
            if promjene["baterija_nacin"] == "rucno":
                b = self.cfg["baterija"]
                w = float(promjene.get("rucna_snaga_w", 0))
                self.napredno["rucna_snaga_w"] = max(-b["max_praznjenje_kw"] * 1000, min(b["max_punjenje_kw"] * 1000, w))
                self.napredno["rucno_do"] = self.sat() + max(5, min(480, int(promjene.get("minuta", 60)))) * 60
        self._dogadjaj("postavke", {"poruka": f"Napredne postavke: {self.napredno}", **self.napredno})
        self.primijeni_ai_profil("promjena postavki")
        self.plan_ts = 0.0  # novi plan odmah
        return self.napredno

    # ------------------------------------------------------------------ plan
    def _planiraj(self, ts: float, soc: float) -> None:
        self.tarife.osvjezi(ts, self.dohvati_tarife and (lambda: self.dohvati_tarife(ts)))
        self.prognoza.osvjezi(ts, self.dohvati_prognozu and (lambda: self.dohvati_prognozu(ts)))
        H = 36
        cijene = self.tarife.niz(ts, H)
        prog = self.prognoza.niz(ts, H)
        pv = [p["pv_w"] for p in prog]
        profil = self.navike.prognoza(ts, H)
        potr, self.prognoza_info = self._ai_prognoza(ts, profil, [g.get("temp") for g in prog])
        self._odluka("prognoza", self.prognoza_info["izvor"], self.prognoza_info["razlog"],
                     "ai" if self.prognoza_info["izvor"].startswith("rubni") else "profil", ts)
        zadaci = []
        bojler = next((t for t in self.cfg["trosila"] if t["id"] == "bojler"), None)
        if bojler:
            # Topla voda: s osjetnikom temperature spremnika puni se točno koliko nedostaje; dok sustav ne
            # nauči navike (prva 2 tjedna) voda se drži toplom kao kod NT tajmera, ali u najjeftinijim satima.
            dolazak = self.parametri.get("bojler_spreman_do_h")
            t_bojler = self.zadnje_ocitanje.get("bojler_temp_c")
            if t_bojler is not None:
                nedostaje = max(0.0, (58.0 - t_bojler) / 45.0 * bojler["energija_kwh_dan"])
            else:
                nedostaje = max(0.0, 2 * bojler["energija_kwh_dan"] - self.dnevno.get("bojler_kwh", 0.0))
            if self.prisutni or not self.navike_naucene:
                # otočno: prozor do idućeg sunčanog dana (grije višak sunca, ne baterija u večernjem vrhu)
                do_h = 6 if self.prisutni else 12
                if not self.prisutni and not self.navike_naucene:
                    # dok uči: FIKSNI rok (15 h, tipičan dolazak) – pomični prozor bi grijanje stalno odgađao
                    lt = time.localtime(ts)
                    do_h = (15 - lt.tm_hour) % 24 or 24
                if not self.mreza_dostupna:
                    do_h = 24
                zadaci.append({"id": "bojler", "snaga_w": bojler["snaga_w"], "energija_kwh": nedostaje,
                               "od_h": 0, "do_h": do_h})
            elif dolazak is not None and dolazak <= 30:
                zadaci.append({"id": "bojler", "snaga_w": bojler["snaga_w"], "energija_kwh": nedostaje,
                               "od_h": max(0, dolazak - 24), "do_h": max(1, dolazak)})
        pumpa_kwh = self.navodnjavanje.potrebna_energija_kwh(24)
        if pumpa_kwh > 0:
            zadaci.append({"id": "pumpa", "snaga_w": self.cfg["navodnjavanje"]["pumpa_kw"] * 1000,
                           "energija_kwh": pumpa_kwh, "od_h": 0, "do_h": 24})
        cfg_plan = self.cfg
        if self.cfg["politika"].get("trosak_ciklusa_plan") is not None:
            cfg_plan = dict(self.cfg, baterija=dict(self.cfg["baterija"],
                                                    trosak_ciklusa_eur_kwh=self.cfg["politika"]["trosak_ciklusa_plan"]))
        ukupno, self.raspored = smjesti_fleksibilna(potr, pv, cijene, zadaci, soc, cfg_plan)
        self.plan = planiraj_bateriju(ukupno, pv, cijene, soc, cfg_plan,
                                      self.parametri.get("rezerva_soc", self.cfg["baterija"]["soc_min"]), ts,
                                      mreza=self.mreza_dostupna)
        for p, c, g in zip(self.plan, cijene, prog):
            p.update({"cijena": c["kupnja"], "izvor_cijene": c["izvor"], "pv_w": round(g["pv_w"]),
                      "izvor_prognoze": g["izvor"]})
        for p, u in zip(self.plan, ukupno):
            p["potr_w"] = round(u)
        self.plan_ts = ts

    def _sat_plana(self, ts: float) -> int:
        return int((ts - (self.plan_ts - self.plan_ts % 3600)) // 3600)

    # ------------------------------------------------------------------ glavni korak
    def korak(self) -> dict:
        ts = self.sat()
        dt = min(300.0, max(0.0, ts - self.zadnji_ts)) if self.zadnji_ts else 10.0
        self.zadnji_ts = ts
        o = self._ocitaj()
        self.zadnje_ocitanje = o
        b = self.cfg["baterija"]
        mreza_dostupna = self.cfg["mreza"]["dostupna"] and o.get("mreza_prisutna", 1.0) >= 0.5
        if self.cfg["mreza"]["dostupna"] and mreza_dostupna != self._mreza_bila:
            self._dogadjaj("mreza", {"poruka": "Mreža ponovno dostupna" if mreza_dostupna else
                                     "Ispad mreže – otočni rad, prioritet zaštiti i pastiru",
                                     "ozbiljnost": "info" if mreza_dostupna else "upozorenje"}, ts)
            self._mreza_bila = mreza_dostupna
            self.plan_ts = 0.0  # novi plan odmah, s drugim ograničenjima
        self.mreza_dostupna = mreza_dostupna
        soc = o.get("baterija_soc")
        pv = o.get("pv_snaga_w", 0.0)
        potr = o.get("potrosnja_w", 0.0)
        bat_w = o.get("baterija_snaga_w")
        if bat_w is None and "baterija_struja_a" in o and "baterija_napon_v" in o:
            bat_w = o["baterija_struja_a"] * o["baterija_napon_v"]
        mreza_w = o.get("mreza_snaga_w", potr - pv + (bat_w or 0.0)) if mreza_dostupna else 0.0

        # 1) anomalije i preventivna zaštita
        prije = set(self.detektor.aktivne)
        nalazi = self.detektor.obradi({k: v for k, v in o.items() if k != "brojilo_impulsi"}, dt, dict(self.releji))
        for n in nalazi:
            kljuc = f"{n.kanal}:{n.vrsta}"
            if n.ozbiljnost != "info" and kljuc not in prije:
                self._dogadjaj("anomalija", n.kao_dict() | {"ozbiljnost": n.ozbiljnost}, ts)
            trosila = n.trosila
            if not self.cfg["politika"].get("zastita_pumpe", True) and n.vrsta in ("rad_na_suho", "blokada"):
                trosila = []  # referentni sustav bez nadzora struje pumpe
            for t in trosila:
                if not self._zasticeno(t, ts):
                    self._dogadjaj("zastita", {"trosilo": t, "uzrok": n.vrsta,
                                               "poruka": f"Preventivno isključeno: {t} ({n.poruka})"}, ts)
                self.zastita_do[t] = max(self.zastita_do.get(t, 0), ts + TRAJANJE_ZASTITE.get(n.vrsta, 1800))
            if n.vrsta in ("punjenje_na_hladnom", "prenapon"):
                self.zabrana_punjenja_do = ts + 1800

        # prisutnost sada (iz potrošnje bez fleksibilnih trošila, ~20 min tromosti)
        osnovna = potr - o.get("bojler_snaga_w", 0.0) - (750.0 if self.releji.get("pumpa") else 0.0)
        aktivno = 1.0 if osnovna > max(150.0, 2.5 * self.navike.osnova_w) else 0.0
        self._prisutnost += min(1.0, dt / 1200) * (aktivno - self._prisutnost)

        # impulsno brojilo (+ kalibracija pri prvom pokretanju) – nakon detekcije, da detektor
        # vidi stvarno stanje releja bojlera tijekom kalibracije
        self._brojilo(o, ts, dt, pv)

        # 2) naučeni parametri i način rada
        if not self.parametri or int(ts) % 900 < dt:
            self.parametri = self.navike.parametri(ts, self.cfg)
        rezerva = min(0.6, self.parametri.get("rezerva_soc", b["soc_min"]) + self.cfg["politika"]["rezerva_dodatak"])
        opt = resursi.opterecenje()
        visak = pv - potr
        self.nacin = resursi.odaberi_nacin(soc, rezerva, visak, opt["load1"], opt["jezgri"], opt.get("cpu_temp_c"))
        interval = resursi.INTERVALI[self.nacin]
        if not self.ai_provjera or ts - self.ai_provjera.get("_ts", 0) >= 3600:
            self.primijeni_ai_profil("periodicno" if self.ai_provjera else "pokretanje")
            self.ai_provjera["_ts"] = ts
        if (self.ai_aktivan and self.nacin in ("PRILIKA", "NORMALNO") and ts - self._ai_zadnje_ucenje >= 3600
                and len(self.ai.uzorci) >= 72):
            self.ai.treniraj(proracun_ms=30.0 if self.nacin == "NORMALNO" else 60.0)  # nikad ne blokira ciklus
            self._ai_zadnje_ucenje = ts
        if soc is not None and (not self.plan or ts - self.plan_ts >= interval["plan"] or self._sat_plana(ts) >= len(self.plan)):
            self._planiraj(ts, soc)
        h_plan = self._sat_plana(ts)
        korak_plana = self.plan[h_plan] if 0 <= h_plan < len(self.plan) else None
        cijena = self.tarife.cijena(ts)

        # 3) kaskada niske baterije (otočni rad)
        if soc is not None and not mreza_dostupna:
            for t in self.cfg["trosila"]:
                if t["prioritet"] >= 3 and soc < rezerva or t["prioritet"] >= 2 and soc <= b["soc_min"] + 0.02:
                    if not self._zasticeno(t["id"], ts):
                        self._dogadjaj("zastita", {"trosilo": t["id"], "uzrok": "niska_baterija",
                                                   "poruka": f"Baterija {soc:.0%} – isključeno: {t['naziv']}"}, ts)
                    self.zastita_do[t["id"]] = ts + 900

        # 3b) vršna snaga (otočno): izmjenjivač daje najviše max_praznjenje (+ sunce). Fleksibilna trošila
        # se gase na 10 min kad je zbroj previsok (bez titranja), a uključuju se samo uz dovoljnu rezervu snage.
        vrsna_w = b["max_praznjenje_kw"] * 1000 * 0.9 + max(0.0, pv)
        slobodno_w = vrsna_w - potr if not mreza_dostupna else float("inf")
        if not mreza_dostupna and potr > vrsna_w:
            for t in ("bojler", "pumpa"):
                if self.releji.get(t):
                    self.zastita_do[t] = max(self.zastita_do.get(t, 0), ts + 600)
                    self._dogadjaj("zastita", {"trosilo": t, "uzrok": "vrsna_snaga",
                                               "poruka": f"Otočno: potrošnja {potr:.0f} W iznad snage izmjenjivača – "
                                                         f"{t} odgođen 10 min"}, ts)

        # 4) električni pastir
        n = self.pastir.n
        v = [o.get(f"pastir_v{k}_kv") for k in range(n + 1)]
        if any(x is not None for x in v) and not self.cfg["politika"].get("nadzor_pastira", True):
            # referentni sustav: aparat trajno priključen i radi punom snagom, ali nitko ne traži ni izolira kvar
            self.pastir_izlaz = {"naponi": v}
            self._postavi("rele_pastir_punjenje", 1.0, ts)
        elif any(x is not None for x in v):
            nacin_prije = self.pastir.nacin
            br_dog = len(self.pastir.dogadjaji)
            p = self.pastir.korak(ts, dt, v, o.get("pastir_baterija_soc"), soc if soc is not None else 1.0,
                                  visak > 50, rezerva)
            for d in self.pastir.dogadjaji[br_dog:]:
                self._dogadjaj("pastir", d, ts)
            for k, zatvoreno in p["sklopke"].items():
                self._postavi(f"rele_pastir_k{k}", 1.0 if zatvoreno else 0.0, ts)
            self._postavi("rele_pastir_povrat", 1.0 if p["povratni_vod"] else 0.0, ts)
            self._postavi("pastir_snaga", p["snaga"], ts)
            self._postavi("rele_pastir_punjenje", 1.0 if p["punjenje"] else 0.0, ts)
            self.pastir_izlaz = p | {"naponi": v, "promjena": nacin_prije != self.pastir.nacin}

        # 5) navodnjavanje
        vlage = {k[4:-6]: x for k, x in o.items() if k.startswith("tlo_") and k.endswith("_vlaga")}
        presk_prije = self.navodnjavanje.ustedjeno_min
        if vlage:
            povoljno = visak > self.cfg["navodnjavanje"]["pumpa_kw"] * 1000 or cijena["izvor"] == "NT" or \
                ("pumpa" in self.raspored and h_plan in self.raspored["pumpa"])
            dopusteno = not self._zasticeno("pumpa", ts) and (mreza_dostupna or soc is None or soc > rezerva + 0.05)
            r = self.navodnjavanje.korak(ts, vlage, self.prognoza.kisa_sljedecih(ts, 12), povoljno, dopusteno)
            self.navodnjavanje_izlaz = r
            for z in vlage:
                self.ventili[z] = r["ventil"] == z
            self.releji["pumpa"] = r["pumpa"]
        strategija = self.cfg["politika"].get("strategija", "pametna")
        lt = time.localtime(ts)
        if strategija != "pametna" and vlage:
            # tipičan tajmer: svaka zona 15 min od 7:00, svaki dan, bez obzira na kišu i vlagu
            minuta = lt.tm_hour * 60 + lt.tm_min
            zone = sorted(vlage)
            aktivna = next((zid for i, zid in enumerate(zone) if 420 + 15 * i <= minuta < 435 + 15 * i), None)
            self.ventili = {zid: zid == aktivna for zid in zone}
            self.releji["pumpa"] = aktivna is not None and not self._zasticeno("pumpa", ts)
            self.navodnjavanje_izlaz = {"razlog": "tajmer 7:00 (referentna strategija)", "pumpa": self.releji["pumpa"]}
        for z, otv in self.ventili.items():
            self._postavi(f"ventil_{z}", 1.0 if otv else 0.0, ts)

        # 6) bojler i ostala trošila
        bojler_plan = "bojler" in self.raspored and h_plan in self.raspored["bojler"]
        # ravnopravna usporedba (bojler_pravilo = "udobnost"): konkurent koristi NAŠU logiku bojlera u cijelosti
        ref_bojler = strategija != "pametna" and self.cfg["politika"].get("bojler_pravilo") != "udobnost"
        if ref_bojler and strategija in ("vlastita", "tou"):
            # NT tajmer: fiksni noćni termin (zimi 21–7, ljeti 22–8), neovisno o vrsti tarife – kao stvarni sat/HDO
            from .tarife import vt_nt
            bojler_plan = vt_nt(ts, self.cfg["tarifa"])[1] == "NT"
        elif (ref_bojler and strategija == "cjenovni_prag") \
                or self.cfg["politika"].get("bojler_pravilo") == "najjeftiniji_sati":
            # (drugi uvjet samo za pokus isključivanja: naša jezgra s konkurentovim pravilom za bojler)
            buduce = sorted(p["cijena"] for p in self.plan[h_plan:h_plan + 24]) if self.plan else []
            bojler_plan = bool(buduce) and cijena["kupnja"] <= buduce[min(2, len(buduce) - 1)]  # 3 najjeftinija sata
        elif cijena["kupnja"] <= 0 and mreza_dostupna:
            bojler_plan = True  # negativna cijena: grijanje vode se plaća nama
        elif self._treba_topla_voda():
            bojler_plan = True  # udobnost: voda ispod 42 °C, a stanari su tu
        # otočno: bojler samo uz rezervu snage i za tipičan kućni vrh (štednjak, kuhalo) dok su stanari tu –
        # kratki nestanak struje je kvar, a malo hladnija voda samo neudobnost
        rezerva_vrha = self._rezerva_vrha(ts) if self.prisutni else 200.0
        for zm in self._aktivni_zahtjevi(ts):
            if zm["vrsta"] == "ogranici_uvoz":
                bojler_plan = False
                if self.releji.get("pumpa"):
                    self.zastita_do["pumpa"] = max(self.zastita_do.get("pumpa", 0), ts + 600)
            elif zm["vrsta"] == "povecaj_potrosnju" and (self.zadnje_ocitanje.get("bojler_temp_c") or 0) < 57:
                bojler_plan = True
        if bojler_plan and not mreza_dostupna and slobodno_w + (2000 if self.releji.get("bojler") else 0) \
                < 2000 + rezerva_vrha:
            bojler_plan = False
        self.releji["bojler"] = bojler_plan and not self._zasticeno("bojler", ts)
        for t in ("uticnice", "hladnjak"):
            self.releji[t] = not self._zasticeno(t, ts)
        if self._zasticeno("pumpa", ts):
            self.releji["pumpa"] = False
        for t, (stanje, do) in list(self.rucno.items()):
            if do < ts:
                self.rucno.pop(t)
            elif not self._zasticeno(t, ts):  # zaštita uvijek ima prednost pred ručnom naredbom
                self.releji[t] = stanje
        if self.kalibracija.get("faza") == "mjerenje_s":
            self.releji["bojler"] = True
        if self.kalibracija.get("faza") == "mjerenje_s":
            self._odluka("bojler", "uključen", "kalibracija brojila (poznato trošilo)", "kalibracija", ts)
        elif self._zasticeno("bojler", ts):
            self._odluka("bojler", "isključen", "zaštita aktivna", "zastita", ts)
        elif "bojler" in self.rucno:
            self._odluka("bojler", "uključen" if self.releji["bojler"] else "isključen", "ručna naredba", "rucno", ts)
        elif self.releji["bojler"]:
            self._odluka("bojler", "uključen", f"planirani sat najnižeg graničnog troška ({cijena['kupnja'] * 100:.1f} c/kWh,"
                         f" sunce {pv:.0f} W)", "plan", ts)
        else:
            self._odluka("bojler", "isključen", "nitko nije prisutan ni očekivan" if "bojler" not in self.raspored
                         else "čeka jeftiniji/sunčaniji sat iz plana", "plan", ts)
        if vlage:
            self._odluka("pumpa", "radi" if self.releji.get("pumpa") else "ne radi",
                         self.navodnjavanje_izlaz.get("razlog", ""), "zastita" if self._zasticeno("pumpa", ts) else "pravilo",
                         ts)
        if self.pastir_izlaz:
            self._odluka("pastir", self.pastir.nacin, (self.pastir.dogadjaji[-1]["poruka"] if self.pastir.nacin != "normalno"
                         and self.pastir.dogadjaji else ("štedni impuls – ograda zdrava s rezervom napona"
                         if self.pastir.snaga < 1 else "puna snaga impulsa")), "pravilo", ts)
        for t, uklj in self.releji.items():
            self._postavi(f"rele_{t}", 1.0 if uklj else 0.0, ts)

        # 7) baterija
        if soc is not None:
            neto = potr - pv
            cmd = None  # None = izmjenjivač sam regulira vlastitu potrošnju (brže i točnije od jezgre)
            nacin_b = self.napredno.get("baterija_nacin", "auto")
            if nacin_b == "rucno" and ts >= self.napredno.get("rucno_do", 0):
                nacin_b = self.napredno["baterija_nacin"] = "auto"
                self._dogadjaj("postavke", {"poruka": "Ručna snaga baterije istekla – vraćen automatski način"}, ts)
            odl = ("vlastita potrošnja", "izmjenjivač pokriva razliku sunca i potrošnje", "plan")
            if nacin_b == "rucno":
                cmd = self.napredno["rucna_snaga_w"]
                odl = (f"ručno {cmd:+.0f} W", "ručno premošćivanje iz naprednih postavki", "rucno")
            elif nacin_b == "vlastita":
                odl = ("vlastita potrošnja", "ručno odabrano: bez arbitraže s mrežom", "rucno")
            elif strategija == "vlastita":
                odl = ("vlastita potrošnja", "referentna strategija", "plan")
            elif strategija == "tou":
                if mreza_dostupna and cijena["izvor"] == "NT" and soc < 0.9:
                    cmd = b["max_punjenje_kw"] * 1000
                    odl = ("puni u NT", "referentna strategija: prisilno punjenje u jeftinoj tarifi", "plan")
            elif strategija == "cjenovni_prag":
                buduce = sorted(p["cijena"] for p in self.plan[h_plan:h_plan + 24]) if self.plan else []
                if buduce and mreza_dostupna:
                    if cijena["kupnja"] <= buduce[len(buduce) // 4]:
                        cmd = b["max_punjenje_kw"] * 1000
                    elif cijena["kupnja"] <= buduce[len(buduce) // 2] and neto > 0:
                        cmd = 0.0
                    odl = ("cjenovni prag", "referentna strategija: puni ispod 25. percentila, čuva ispod medijana", "plan")
            elif mreza_dostupna and cijena["kupnja"] <= 0 and nacin_b != "bez_punjenja_iz_mreze":
                cmd = b["max_punjenje_kw"] * 1000
                odl = ("puni iz mreže", f"negativna cijena ({cijena['kupnja'] * 100:.1f} c/kWh) – mreža plaća potrošnju", "plan")
            elif korak_plana and mreza_dostupna:
                if korak_plana["baterija_kw"] > 0.05 and korak_plana["mreza_kw"] > 0.05 \
                        and nacin_b != "bez_punjenja_iz_mreze" \
                        and self._isplati_cuvati(h_plan, cijena, soc, punjenje=True):
                    cmd = korak_plana["baterija_kw"] * 1000  # planirano punjenje iz jeftine mreže
                    odl = (f"puni iz mreže {cmd:.0f} W", f"jeftino sada ({cijena['kupnja'] * 100:.1f} c), a baterija "
                           "neće dostajati do sljedećeg sunca", "plan")
                elif (korak_plana["baterija_kw"] < -0.05 and korak_plana["mreza_kw"] < -0.05
                      and soc > rezerva + 0.05 and self._isplati_izvoz(h_plan, cijena, soc)):
                    cmd = korak_plana["baterija_kw"] * 1000  # planirano pražnjenje u mrežu (skupi izvoz)
                    odl = (f"prodaje iz baterije {-cmd:.0f} W", f"izvozna cijena {cijena['prodaja'] * 100:.1f} c "
                           "veća je od vrijednosti te energije kasnije", "plan")
                elif neto > 0 and self._isplati_cuvati(h_plan, cijena, soc):
                    cmd = 0.0  # čuvaj bateriju za skuplje sate
                    odl = ("čuva energiju", f"mreža sada {cijena['kupnja'] * 100:.1f} c jeftinija je od energije u bateriji "
                           "(skuplji sati ili trošak ponovnog punjenja i trošenja)", "plan")
            if self.kalibracija.get("faza", "").startswith("mjerenje"):
                cmd = 0.0
                odl = ("miruje", "kalibracija brojila", "kalibracija")
            # zahtjevi operatora mreže (fleksibilnost) – iznad optimizacije, ispod sigurnosnih granica
            for zm in self._aktivni_zahtjevi(ts):
                if zm["vrsta"] == "ogranici_uvoz" and mreza_dostupna and neto > zm["snaga_w"]:
                    cmd = min(cmd if cmd is not None else -neto, -(neto - zm["snaga_w"]))
                    odl = (f"ograničava uvoz na {zm['snaga_w']:.0f} W", f"zahtjev mreže ({zm['izvor']}) do "
                           f"{time.strftime('%H:%M', time.localtime(zm['do']))}", "mreza")
                elif zm["vrsta"] == "ogranici_izvoz" and mreza_dostupna and -neto > zm["snaga_w"]:
                    cmd = max(cmd if cmd is not None else -neto, -neto - zm["snaga_w"])
                    odl = (f"ograničava izvoz na {zm['snaga_w']:.0f} W", f"zahtjev mreže ({zm['izvor']})", "mreza")
                elif zm["vrsta"] == "povecaj_potrosnju" and mreza_dostupna:
                    cmd = max(cmd or 0.0, zm["snaga_w"])
                    odl = (f"povećava potrošnju {zm['snaga_w']:.0f} W", f"zahtjev mreže ({zm['izvor']})", "mreza")
            # proaktivna zabrana punjenja na hladnom (LiFePO4 ispod 0 °C), ne tek kad struja već teče
            t_bat = o.get("baterija_temp_c")
            hladno = t_bat is not None and t_bat < b["temp_punjenje_min_c"] + 0.5
            bez_punjenja = ts < self.zabrana_punjenja_do or soc >= b["soc_max"] or hladno
            # s mrežom: ispod soc_min mreža preuzima. Otočno: nekritična trošila su već isključena (kaskada),
            # pa kritična (hladnjak, usmjernik) smiju bateriju do kritične razine – bolje nego mrak.
            bez_praznjenja = soc <= (b["soc_min"] if mreza_dostupna else b.get("soc_kriticno", b["soc_min"]))
            granica = bez_punjenja or bez_praznjenja
            if granica:
                razlog = ("punjenje zabranjeno na hladnom" if hladno else
                          "zabrana punjenja (temperatura/napon)" if ts < self.zabrana_punjenja_do else
                          f"gornja granica {b['soc_max']:.0%}" if soc >= b["soc_max"] else f"donja granica {b['soc_min']:.0%}")
                odl = (odl[0], odl[1] + f"; sigurnosna granica: {razlog}", "zastita" if odl[2] != "rucno" else "rucno")
            self._odluka("baterija", odl[0], odl[1], odl[2], ts, soc=round(soc, 3), cijena=cijena["kupnja"],
                         plan_kw=korak_plana["baterija_kw"] if korak_plana else None)
            if cmd is None:
                # Na granicama jezgra NE zadaje snagu (zastarjela bi za jedan korak), nego izmjenjivaču postavi
                # samo ograničenje smjera; regulaciju u stvarnom vremenu radi izmjenjivač (SunSpec StorCtl_Mod).
                ogr = (1 if bez_punjenja else 0) | (2 if bez_praznjenja else 0)
                if ogr:
                    self._postavi("baterija_ogranicenje", float(ogr), ts, osvjezi_s=60)
                    self._naredbe_zadnje.pop("baterija_auto", None)
                else:
                    self._postavi("baterija_auto", 1.0, ts, osvjezi_s=60)
                    self._naredbe_zadnje.pop("baterija_ogranicenje", None)
                self._naredbe_zadnje.pop("baterija_snaga_w", None)
            else:
                if bez_punjenja:
                    cmd = min(cmd, 0.0)
                if bez_praznjenja:
                    cmd = max(cmd, 0.0)
                cmd = max(-b["max_praznjenje_kw"] * 1000, min(b["max_punjenje_kw"] * 1000, cmd))
                self._postavi("baterija_snaga_w", round(cmd, -1), ts, osvjezi_s=30)
                self._naredbe_zadnje.pop("baterija_auto", None)
                self._naredbe_zadnje.pop("baterija_ogranicenje", None)

        if mreza_dostupna and strategija == "pametna":
            bez_izvoza = cijena["prodaja"] < 0 or any(zm["vrsta"] == "ogranici_izvoz" and zm["snaga_w"] <= 0
                                                       for zm in self._aktivni_zahtjevi(ts))
            self._postavi("izvoz_zabranjen", 1.0 if bez_izvoza else 0.0, ts)

        # 8) zapis i satni zbroj
        uzorak = {"dt": dt, "pv": pv, "potr": potr, "mreza": mreza_w, "bat": bat_w or 0.0, "soc": soc,
                  "ck": cijena["kupnja"], "cp": cijena["prodaja"], "bojler": o.get("bojler_snaga_w", 0.0),
                  "pumpa": self.releji.get("pumpa", False),
                  "pumpa_w": self.cfg["navodnjavanje"]["pumpa_kw"] * 1000 if self.releji.get("pumpa") else 0.0,
                  "presk": self.navodnjavanje.ustedjeno_min - presk_prije,
                  "pastir_ok": (min((x for x in self.pastir_izlaz.get("naponi", [None])[1:] if x is not None),
                                    default=0) >= self.cfg["pastir"]["min_kv"]) if self.pastir_izlaz else None,
                  "pvp": korak_plana.get("pv_w") if korak_plana else None,
                  "o": {k: v for k, v in o.items()
                        if k in ("baterija_temp_c", "baterija_napon_v", "okolina_temp_c", "bojler_temp_c",
                                 "pumpa_struja_a") or k.startswith(("tlo_", "pastir_v"))}}
        self.dnevnik.zapisi(TELEMETRIJA, uzorak, ts=ts)
        self.povijest.dodaj(ts, self._za_povijest(uzorak))
        self._akumuliraj(uzorak, ts)
        self._dnevno(ts, dt, o, pv)

        if ts - self.zadnja_snimka >= 300:
            self.spremi_snimku(ts)
        if self.kopije.odredista and ts - self.zadnja_kopija >= interval["kopija"]:
            self.napravi_kopiju(ts)
        return {"ts": ts, "nacin": self.nacin, "pastir": self.pastir.nacin}

    def _vrijednost_kwh(self, h: int, soc: float, sigurnost: float = 1.0) -> tuple[float | None, bool]:
        """Koliko vrijedi kWh u bateriji sada? Vraća (vrijednost €/kWh, oskudno).

        - oskudno (baterija ne dostaje do sljedećeg viška sunca): koliko najskuplji sat u kojem bi
          energije nedostajalo,
        - nije oskudno: sunce će je napuniti energijom koja bi se inače izvezla, pa kWh stoji
          izvozna cijena / učinkovitost + trošenje (pražnjenje sada i ponovno punjenje = dva prolaza).
        """
        b = self.cfg["baterija"]
        rezerva = self.parametri.get("rezerva_soc", b["soc_min"])
        dostupno = max(0.0, soc - rezerva) * b["kapacitet_kwh"] * 0.95
        potrebno, cijene_manjka, izvoz_punjenja = 0.0, [], []
        for p in self.plan[h:h + 36]:
            visak = (p.get("pv_w", 0) - p.get("potr_w", 0) * sigurnost) / 1000
            if visak > 0.5 and p is not self.plan[h]:
                izvoz_punjenja.append(self.tarife.cijena(p["ts"] + 1800)["prodaja"])
                if len(izvoz_punjenja) >= 3:
                    break  # sunce opet puni bateriju
                continue
            potrebno += max(0.0, -visak)
            if potrebno > dostupno:
                cijene_manjka.append(p["cijena"])
        if cijene_manjka:
            return max(cijene_manjka), True
        if not izvoz_punjenja:
            return None, False
        return max(0.0, sum(izvoz_punjenja) / len(izvoz_punjenja)) / 0.9025 + 2 * b["trosak_ciklusa_eur_kwh"], False

    def _isplati_cuvati(self, h: int, cijena: dict, soc: float, punjenje: bool = False) -> bool:
        """Je li kupnja iz mreže sada jeftinija od korištenja (ili punjenja) baterije?"""
        vrijednost, oskudno = self._vrijednost_kwh(h, soc)
        if vrijednost is None:
            return False
        faktor = self.cfg["politika"]["cuvanje_faktor"]
        trosenje = self.cfg["baterija"]["trosak_ciklusa_eur_kwh"]
        if punjenje:  # punjenje iz mreže samo kad će energija sigurno trebati u skupljim satima
            return oskudno and vrijednost * 0.9 * faktor - 2 * trosenje > cijena["kupnja"]
        return cijena["kupnja"] < vrijednost * faktor - (trosenje if oskudno else 0.0)

    def _isplati_izvoz(self, h: int, cijena: dict, soc: float) -> bool:
        """Prodati energiju iz baterije u mrežu sada? Samo ako izvozna cijena (uz gubitke i trošenje)
        nadmašuje vrijednost te energije kasnije, i ako to pravila priključka dopuštaju."""
        if not self.cfg["politika"].get("izvoz_iz_baterije", True):
            return False
        # prognoza potrošnje može podcijeniti (npr. hladni val): prodaje se samo ono što preostaje i uz
        # 50 % veću potrošnju od prognozirane – prodaja nikad ne smije ugroziti vlastitu opskrbu
        t_bat = self.zadnje_ocitanje.get("baterija_temp_c")
        if t_bat is not None and t_bat < self.cfg["baterija"]["temp_punjenje_min_c"] + 2.0:
            return False  # na hladnom se prodana energija ne može ponovno napuniti
        vrijednost, _ = self._vrijednost_kwh(h, soc, sigurnost=1.5 if self.navike_naucene else 2.0)
        if vrijednost is None:
            vrijednost = max((p["cijena"] for p in self.plan[h + 1:h + 25]), default=cijena["kupnja"])
        return cijena["prodaja"] * 0.95 - self.cfg["baterija"]["trosak_ciklusa_eur_kwh"] > vrijednost

    def _rezerva_vrha(self, ts: float) -> float:
        """Koliko snage ostaviti za kućne vrhove (štednjak, kuhalo) u ovom satu: iz naučenog profila
        (prosjek iznad osnovnog opterećenja ×1,5), a dok sustav uči – tipična vremena obroka."""
        h = time.localtime(ts).tm_hour
        if self.navike_naucene:
            profil = self.navike.prognoza(ts, 1)[0]
            return min(2000.0, max(200.0, 1.5 * (profil - self.navike.osnova_w)))
        return 1700.0 if h in (7, 8, 9, 12, 13, 14, 18, 19, 20) else 200.0

    # ------------------------------------------------------------------ pametna mreža (fleksibilnost)
    VRSTE_ZAHTJEVA = ("ogranici_uvoz", "ogranici_izvoz", "povecaj_potrosnju")

    def _aktivni_zahtjevi(self, ts: float) -> list[dict]:
        return [z for z in self.zahtjevi_mreze if z["od"] <= ts < z["do"] and not z.get("opozvan")]

    def dodaj_zahtjev_mreze(self, z: dict) -> dict:
        """Zahtjev operatora/agregatora (npr. OpenADR posrednik). Provjerava se i ograničava; vraća upisani zahtjev."""
        ts = self.sat()
        vrsta = z.get("vrsta")
        if vrsta not in self.VRSTE_ZAHTJEVA:
            raise ValueError(f"vrsta mora biti jedna od {self.VRSTE_ZAHTJEVA}")
        snaga = float(z.get("snaga_w", 0))
        od = float(z.get("od", ts))
        do = float(z.get("do", od + 3600))
        if not 0 <= snaga <= 50_000 or not od < do or do - od > 24 * 3600 or do < ts:
            raise ValueError("snaga 0–50000 W, od < do, najviše 24 h, ne u prošlosti")
        zapis = {"id": f"zm-{int(ts * 1000) % 10**10}-{len(self.zahtjevi_mreze)}", "vrsta": vrsta, "snaga_w": snaga,
                 "od": od, "do": do, "izvor": str(z.get("izvor", "operator"))[:40], "primljen": ts}
        self.zahtjevi_mreze = [x for x in self.zahtjevi_mreze if x["do"] > ts][-49:] + [zapis]
        self._dogadjaj("zahtjev_mreze", {"poruka": f"Zahtjev mreže: {vrsta} {snaga:.0f} W "
                                                   f"{time.strftime('%d.%m. %H:%M', time.localtime(od))}–"
                                                   f"{time.strftime('%H:%M', time.localtime(do))} ({zapis['izvor']})",
                                         **zapis}, ts)
        return zapis

    def opozovi_zahtjev_mreze(self, zid: str) -> bool:
        for x in self.zahtjevi_mreze:
            if x["id"] == zid and not x.get("opozvan"):
                x["opozvan"] = self.sat()
                self._dogadjaj("zahtjev_mreze", {"poruka": f"Zahtjev {zid} opozvan", "id": zid})
                return True
        return False

    def fleksibilnost(self) -> dict:
        """Koliko snage sustav sada može ponuditi mreži i koliko dugo (procjena za agregatore)."""
        o, b = self.zadnje_ocitanje, self.cfg["baterija"]
        soc = o.get("baterija_soc") or 0.0
        kap_wh = b["kapacitet_kwh"] * 1000
        rezerva = self.parametri.get("rezerva_soc", b["soc_min"])
        dolje_bat = min(b["max_praznjenje_kw"] * 1000, max(0.0, (soc - rezerva) * kap_wh))
        gore_bat = min(b["max_punjenje_kw"] * 1000, max(0.0, (b["soc_max"] - soc) * kap_wh))
        t_b = o.get("bojler_temp_c")
        bojler_moze = t_b is not None and t_b < 55
        trenutna_fleks = (o.get("bojler_snaga_w") or 0.0) + (750.0 if self.releji.get("pumpa") else 0.0)
        return {
            "smanjenje_uvoza_w": round(dolje_bat + trenutna_fleks),
            "smanjenje_uvoza_h": round(max(0.0, (soc - rezerva) * kap_wh) / max(1.0, dolje_bat), 2) if dolje_bat else 0.0,
            "povecanje_potrosnje_w": round(gore_bat + (2000.0 if bojler_moze else 0.0)),
            "povecanje_potrosnje_h": round(max(0.0, (b["soc_max"] - soc) * kap_wh) / max(1.0, gore_bat), 2) if gore_bat else 0.0,
            "izvori": {"baterija_dolje_w": round(dolje_bat), "baterija_gore_w": round(gore_bat),
                       "bojler_w": 2000 if bojler_moze else 0, "trenutna_fleksibilna_trosila_w": round(trenutna_fleks)},
            "mreza_dostupna": self.mreza_dostupna, "aktivni_zahtjevi": self._aktivni_zahtjevi(self.sat()),
        }

    @staticmethod
    def _za_povijest(d: dict) -> dict:
        """Zapis telemetrije -> imena serija javnog API-ja (povijest.SERIJE)."""
        o = d.get("o", {})
        v = {"pv_w": d.get("pv"), "potrosnja_w": d.get("potr"), "mreza_w": d.get("mreza"), "baterija_w": d.get("bat"),
             "baterija_soc": None if d.get("soc") is None else d["soc"] * 100, "cijena_eur_kwh": d.get("ck"),
             "bojler_w": d.get("bojler"), "pumpa_w": d.get("pumpa_w"), "pv_prognoza_w": d.get("pvp"),
             "bojler_temp_c": o.get("bojler_temp_c"), "okolina_temp_c": o.get("okolina_temp_c")}
        v.update({k: x for k, x in o.items() if k.startswith(("tlo_", "pastir_v"))})
        return v

    def usteda_po_danima(self, dana: int = 30) -> list[dict]:
        """Ušteda po danu (procjena prema osnovici), zadnjih `dana` dana; prošli dani se pamte."""
        po_danu: dict[str, list[dict]] = {}
        for s in self.sati:
            po_danu.setdefault(time.strftime("%Y-%m-%d", time.localtime(s["ts"])), []).append(s)
        danas = time.strftime("%Y-%m-%d", time.localtime(self.sat()))
        out = []
        for dan in sorted(po_danu)[-dana:]:
            if dan in self._usteda_dani and dan != danas:
                out.append(self._usteda_dani[dan])
                continue
            sati = po_danu[dan]
            izv = izvjestaji.sazetak(sati, [], self.cfg, sati[0]["ts"], sati[-1]["ts"] + 3600, {})
            r = {"dan": dan, "usteda_eur": izv["procjena_ustede"]["usteda_eur"],
                 "trosak_eur": izv["procjena_ustede"]["s_upravljanjem_eur"],
                 "osnovica_eur": izv["procjena_ustede"]["osnovica_eur"],
                 "pv_kwh": izv["izmjereno"]["proizvodnja_pv_kwh"], "potrosnja_kwh": izv["izmjereno"]["potrosnja_kwh"],
                 "samoopskrba": izv["izmjereno"]["samoopskrba"], "sati": len(sati)}
            if dan != danas:
                self._usteda_dani[dan] = r
            out.append(r)
        return out

    @property
    def navike_naucene(self) -> bool:
        return len(self.sati) >= 14 * 24

    def _treba_topla_voda(self) -> bool:
        """Udobnost ispred cijene: ispod 42 °C dok su stanari tu ili upravo stižu."""
        t = self.zadnje_ocitanje.get("bojler_temp_c")
        if t is None or t >= 42.0:
            return False
        dolazak = self.parametri.get("sljedeci_dolazak_h")
        return self.prisutni or (dolazak is not None and dolazak <= 2)

    @property
    def prisutni(self) -> bool:
        return self._prisutnost > 0.5

    def _brojilo(self, o: dict, ts: float, dt: float, pv: float) -> None:
        imp = o.get("brojilo_impulsi")
        if imp is None:
            return
        k = self.kalibracija
        prosli = k.get("zadnji_imp")
        k["zadnji_imp"] = imp
        if prosli is not None and imp >= prosli:
            for _ in range(int(imp - prosli)):
                self.brojilo.impuls()
        f = k.get("faza", "ceka")
        mreza = self.cfg["mreza"]["dostupna"]
        if f == "ceka" and self.brojilo.konstanta_izvor == "pretpostavka" and mreza and pv < 50 \
                and not self.releji.get("bojler"):
            k.update({"faza": "mjerenje_0", "od": ts, "imp_od": imp})
            self._dogadjaj("kalibracija", {"poruka": "Kalibracija brojila: mjerim osnovnu potrošnju"}, ts)
        elif f == "mjerenje_0" and ts - k["od"] >= 300:
            k.update({"faza": "mjerenje_s", "f0": (imp - k["imp_od"]) / ((ts - k["od"]) / 3600), "od": ts,
                      "imp_od": imp})
        elif f == "mjerenje_s" and ts - k["od"] >= 300:
            f1 = (imp - k["imp_od"]) / ((ts - k["od"]) / 3600)
            snaga = next((t["snaga_w"] for t in self.cfg["trosila"] if t["id"] == "bojler"), 2000)
            c, izvor = ImpulsnoBrojilo.kalibriraj(k["f0"], f1, snaga)
            self.brojilo.konstanta, self.brojilo.konstanta_izvor = c, izvor
            k.update({"faza": "gotovo", "konstanta": c})
            self._dogadjaj("kalibracija", {"poruka": f"Brojilo kalibrirano: {c:g} imp/kWh ({izvor})"}, ts)
            self.releji["bojler"] = False

    def _dnevno(self, ts: float, dt: float, o: dict, pv: float) -> None:
        dan = time.strftime("%Y-%m-%d", time.localtime(ts))
        dd = self.dnevno
        if self.dan and dan != self.dan:
            pokaz = {"pv_omjer": dd.get("pv_wh", 0) / dd["pv_ocekivano_wh"] if dd.get("pv_ocekivano_wh", 0) > 2000 else None,
                     "pastir_min_kv": dd.get("pastir_min"), "pumpa_struja_a": dd.get("pumpa_i")}
            self.detektor.dnevni_pokazatelji(ts / 86400, pokaz)
            self.odrzavanje = self.detektor.predvidi()
            for z in self.odrzavanje:
                if z["hitno"]:
                    self._dogadjaj("odrzavanje", z, ts)
            self.dnevno = dd = {}
            lt = time.localtime(ts)
            if self.cfg["izvjestaji"]["tjedno"] and lt.tm_wday == 0:
                self.izvjestaj(ts - 7 * 86400, ts, f"tjedni-{dan}")
            if self.cfg["izvjestaji"]["mjesecno"] and lt.tm_mday == 1:
                self.izvjestaj(ts - 31 * 86400, ts, f"mjesecni-{dan}")
        self.dan = dan
        dd["bojler_kwh"] = dd.get("bojler_kwh", 0.0) + o.get("bojler_snaga_w", 0.0) * dt / 3.6e6
        dd["pv_wh"] = dd.get("pv_wh", 0.0) + pv * dt / 3600
        plan = self.plan[self._sat_plana(ts)] if self.plan and 0 <= self._sat_plana(ts) < len(self.plan) else None
        if plan:
            dd["pv_ocekivano_wh"] = dd.get("pv_ocekivano_wh", 0.0) + plan["pv_w"] * dt / 3600
            if pv > 100:
                self.prognoza.uci_naoblaku(pv, ts)
        naponi = [x for k, x in enumerate(self.pastir_izlaz.get("naponi", [])[1:], 1)
                  if x is not None and self.pastir.stanje_dionica[k] in ("ispravna", "slaba")]
        if naponi and self.pastir.nacin == "normalno":
            dd["pastir_min"] = min(dd.get("pastir_min", 99.0), min(naponi))
        if self.releji.get("pumpa") and o.get("pumpa_struja_a", 0) > 2:
            dd["pumpa_i"] = o["pumpa_struja_a"]

    # ------------------------------------------------------------------ snimka, kopije, izvještaji
    def snimka_stanja(self) -> dict:
        return {"detektor": self.detektor.stanje(), "navike": self.navike.stanje(),
                "navodnjavanje": self.navodnjavanje.stanje(), "pastir": self.pastir.stanje(),
                "sinkronizacija": self.sinkronizacija.stanje(), "releji": self.releji,
                "zastita_do": self.zastita_do, "zabrana_punjenja_do": self.zabrana_punjenja_do,
                "agregat": self.agregat, "dan": self.dan, "dnevno": self.dnevno, "zadnji_ts": self.zadnji_ts,
                "brojilo": {"konstanta": self.brojilo.konstanta if self.brojilo.konstanta_izvor != "pretpostavka"
                            else None, "izvor": self.brojilo.konstanta_izvor},
                "kalibracija": self.kalibracija, "zadnja_kopija": self.zadnja_kopija,
                "izvjestaji": self.izvjestaji_izradjeni[-50:], "ai": self.ai.stanje(), "napredno": self.napredno,
                "ai_zadnje_ucenje": self._ai_zadnje_ucenje,
                "zahtjevi_mreze": [z for z in self.zahtjevi_mreze if z["do"] > (self.zadnji_ts or 0)]}

    def spremi_snimku(self, ts: float | None = None) -> None:
        self.dnevnik.sinkroniziraj()
        self.snimka.spremi(self.snimka_stanja(), self.dnevnik.slijed)
        self.zadnja_snimka = ts or self.sat()

    def napravi_kopiju(self, ts: float | None = None) -> list[dict]:
        self.spremi_snimku(ts)
        r = self.kopije.napravi(self.dnevnik.segmenti() + self.arhiva.segmenti())
        self.zadnja_kopija = ts or self.sat()
        for x in r:
            if not x["ok"]:
                self._dogadjaj("kopija", {"poruka": f"Kopija na {x['odrediste']} nije uspjela: {x['greska']}",
                                          "ozbiljnost": "upozorenje"})
        return r

    def izvjestaj(self, od: float, do: float, ime: str | None = None, izvezi: bool = True) -> dict:
        sati = [s for s in self.sati if od <= s["ts"] < do]
        dog = [z for z in self.arhiva.citaj(0, {"pastir", "zastita", "anomalija", "sigurno_stanje"})
               if od <= z["t"] < do]
        izv = izvjestaji.sazetak(sati, dog, self.cfg, od, do,
                                 {"uredaj": self.trezor.id_uredaja(), "odrzavanje": self.odrzavanje})
        if izvezi:
            ime = ime or f"izvjestaj-{time.strftime('%Y%m%d-%H%M', time.localtime(do))}"
            datoteke = izvjestaji.izvezi(izv, self.trezor, self.mapa / "izvjestaji", ime)
            self.izvjestaji_izradjeni.append(ime)
            self._dogadjaj("izvjestaj", {"poruka": f"Izvještaj {ime} izrađen",
                                         "datoteke": {k: str(v) for k, v in datoteke.items()}})
        return izv

    def sigurno_stanje(self) -> None:
        """Pozvano iz nadzornika: pastir ostaje pod naponom, fleksibilna trošila isključena."""
        self.u_sigurnom = True
        ts = self.sat()
        for t in ("pumpa", "bojler"):
            self.zastita_do[t] = ts + 900
            self._postavi(f"rele_{t}", 0.0, ts, osvjezi_s=0)
        for z in self.ventili:
            self._postavi(f"ventil_{z}", 0.0, ts, osvjezi_s=0)
        self._postavi("pastir_snaga", 1.0, ts, osvjezi_s=0)

    def zatvori(self) -> None:
        self.spremi_snimku()
        self.dnevnik.zatvori()
        self.arhiva.zatvori()

    # ------------------------------------------------------------------ za sučelje
    def usteda(self, ts: float) -> dict:
        if self._kes_ustede and ts - self._kes_ustede[0] < 600:
            return self._kes_ustede[1]
        lt = time.localtime(ts)
        pocetak_dana = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))
        pocetak_mj = time.mktime((lt.tm_year, lt.tm_mon, 1, 0, 0, 0, 0, 0, -1))
        out = {}
        for ime, od in (("danas", pocetak_dana), ("mjesec", pocetak_mj), ("ukupno", 0)):
            izv = self.izvjestaj(od, ts + 1, izvezi=False) if self.sati else None
            out[ime] = izv["procjena_ustede"] | {"samoopskrba": izv["izmjereno"]["samoopskrba"],
                                                 "pv_kwh": izv["izmjereno"]["proizvodnja_pv_kwh"]} if izv else None
        self._kes_ustede = (ts, out)
        return out

    def stanje(self) -> dict:
        ts = self.sat()
        o = self.zadnje_ocitanje
        return {
            "vrijeme": ts, "id": self.trezor.id_uredaja(), "nacin": self.nacin, "sigurno_stanje": self.u_sigurnom,
            "energija": {k: o.get(k) for k in ("pv_snaga_w", "potrosnja_w", "baterija_soc", "baterija_snaga_w",
                                               "baterija_temp_c", "baterija_napon_v", "okolina_temp_c")},
            "mreza_dostupna": self.cfg["mreza"]["dostupna"],
            "cijena": self.tarife.cijena(ts), "parametri": self.parametri,
            "plan": self.plan[:36], "raspored": self.raspored,
            "usteda": self.usteda(ts),
            "pastir": {"nacin": self.pastir.nacin, "dionice": self.pastir.stanje_dionica[1:],
                       "naponi": self.pastir_izlaz.get("naponi"), "snaga": self.pastir.snaga,
                       "povratni_vod": self.pastir.r_zatvoren, "dogadjaji": self.pastir.dogadjaji[-8:],
                       "baterija": o.get("pastir_baterija_soc")},
            "navodnjavanje": {"zone": {k: {"vlaga": z.zadnja_vlaga, "prag": z.prag, "cilj": z.cilj}
                                       for k, z in self.navodnjavanje.zone.items()},
                              "odluka": self.navodnjavanje_izlaz, "aktivna": self.navodnjavanje.aktivna},
            "anomalije": [a.kao_dict() for a in self.detektor.aktivne.values()],
            "odrzavanje": self.odrzavanje,
            "releji": self.releji, "zastita": {k: v for k, v in self.zastita_do.items() if v > ts},
            "brojilo": {"konstanta": self.brojilo.konstanta, "izvor": self.brojilo.konstanta_izvor,
                        "kalibracija": self.kalibracija.get("faza"), "kwh": round(self.brojilo.energija_kwh, 3)},
            "uredaji": [u.opis() | {"dostupan": u.id not in self.offline_uredaji} for u in self.uredaji],
            "oblak": {"ukljuceno": self.sinkronizacija.ukljuceno, "zadnji_uspjeh": self.sinkronizacija.zadnji_uspjeh,
                      "greska": self.sinkronizacija.greska, "pokazivac": self.sinkronizacija.pokazivac},
            "prognoza": {"izvor": "prognoza" if self.prognoza.sati else "procjena", "greska": self.prognoza.greska},
            "kopije": list(self.kopije.zadnje.values()), "oporavak": self.oporavak,
            "izvjestaji": self.izvjestaji_izradjeni[-10:],
            "odluke": self.odluke, "napredno": self.napredno,
            "ai": {"aktivan": self.ai_aktivan, "provjera": self.ai_provjera, "kvaliteta": self.ai.kvaliteta(),
                   "prognoza": getattr(self, "prognoza_info", {}).get("izvor")},
        }
