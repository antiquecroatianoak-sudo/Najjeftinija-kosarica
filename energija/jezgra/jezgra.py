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
from .prognoza import Prognoza
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
        self._prisutnost = 0.0
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
        if a["ts"] in self._zakljuceni:
            return  # već zapisano prije pada (ponavljanje)
        self._zakljuceni.add(a["ts"])
        self.sati.append(a)
        del self.sati[:-24 * 400]
        self.arhiva.zapisi("sat", a, kriticno=True, ts=a["ts"] + 3600)

    # ------------------------------------------------------------------ plan
    def _planiraj(self, ts: float, soc: float) -> None:
        self.tarife.osvjezi(ts, self.dohvati_tarife and (lambda: self.dohvati_tarife(ts)))
        self.prognoza.osvjezi(ts, self.dohvati_prognozu and (lambda: self.dohvati_prognozu(ts)))
        H = 36
        cijene = self.tarife.niz(ts, H)
        prog = self.prognoza.niz(ts, H)
        pv = [p["pv_w"] for p in prog]
        potr = self.navike.prognoza(ts, H)
        zadaci = []
        bojler = next((t for t in self.cfg["trosila"] if t["id"] == "bojler"), None)
        if bojler:
            # topla voda samo kad netko jest ili se (prema naučenim navikama) uskoro očekuje
            dolazak = self.parametri.get("bojler_spreman_do_h")
            ostalo = max(0.0, bojler["energija_kwh_dan"] - self.dnevno.get("bojler_kwh", 0.0))
            if self.prisutni:
                zadaci.append({"id": "bojler", "snaga_w": bojler["snaga_w"], "energija_kwh": ostalo,
                               "od_h": 0, "do_h": 12})
            elif dolazak is not None and dolazak <= 30:
                zadaci.append({"id": "bojler", "snaga_w": bojler["snaga_w"], "energija_kwh": bojler["energija_kwh_dan"],
                               "od_h": max(0, dolazak - 24), "do_h": max(1, dolazak)})
        pumpa_kwh = self.navodnjavanje.potrebna_energija_kwh(24)
        if pumpa_kwh > 0:
            zadaci.append({"id": "pumpa", "snaga_w": self.cfg["navodnjavanje"]["pumpa_kw"] * 1000,
                           "energija_kwh": pumpa_kwh, "od_h": 0, "do_h": 24})
        ukupno, self.raspored = smjesti_fleksibilna(potr, pv, cijene, zadaci, soc, self.cfg)
        self.plan = planiraj_bateriju(ukupno, pv, cijene, soc, self.cfg,
                                      self.parametri.get("rezerva_soc", self.cfg["baterija"]["soc_min"]), ts)
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
        mreza_dostupna = self.cfg["mreza"]["dostupna"]
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
            for t in n.trosila:
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
        rezerva = self.parametri.get("rezerva_soc", b["soc_min"])
        opt = resursi.opterecenje()
        visak = pv - potr
        self.nacin = resursi.odaberi_nacin(soc, rezerva, visak, opt["load1"], opt["jezgri"], opt.get("cpu_temp_c"))
        interval = resursi.INTERVALI[self.nacin]
        if soc is not None and (not self.plan or ts - self.plan_ts >= interval["plan"] or self._sat_plana(ts) >= len(self.plan)):
            self._planiraj(ts, soc)
        h_plan = self._sat_plana(ts)
        korak_plana = self.plan[h_plan] if 0 <= h_plan < len(self.plan) else None
        cijena = self.tarife.cijena(ts)

        # 3) kaskada niske baterije (otočni rad)
        if soc is not None and not mreza_dostupna:
            for t in self.cfg["trosila"]:
                if t["prioritet"] >= 3 and soc < rezerva or t["prioritet"] >= 2 and soc < b["soc_min"]:
                    if not self._zasticeno(t["id"], ts):
                        self._dogadjaj("zastita", {"trosilo": t["id"], "uzrok": "niska_baterija",
                                                   "poruka": f"Baterija {soc:.0%} – isključeno: {t['naziv']}"}, ts)
                    self.zastita_do[t["id"]] = ts + 900

        # 4) električni pastir
        n = self.pastir.n
        v = [o.get(f"pastir_v{k}_kv") for k in range(n + 1)]
        if any(x is not None for x in v):
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
        for z, otv in self.ventili.items():
            self._postavi(f"ventil_{z}", 1.0 if otv else 0.0, ts)

        # 6) bojler i ostala trošila
        bojler_plan = "bojler" in self.raspored and h_plan in self.raspored["bojler"]
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
        for t, uklj in self.releji.items():
            self._postavi(f"rele_{t}", 1.0 if uklj else 0.0, ts)

        # 7) baterija
        if soc is not None:
            neto = potr - pv
            cmd = None  # None = izmjenjivač sam regulira vlastitu potrošnju (brže i točnije od jezgre)
            if korak_plana and mreza_dostupna:
                if korak_plana["baterija_kw"] > 0.05 and korak_plana["mreza_kw"] > 0.05 \
                        and self._isplati_cuvati(h_plan, cijena, soc, punjenje=True):
                    cmd = korak_plana["baterija_kw"] * 1000  # planirano punjenje iz jeftine mreže
                elif neto > 0 and korak_plana["baterija_kw"] > -0.05 and self._isplati_cuvati(h_plan, cijena, soc):
                    cmd = 0.0  # čuvaj bateriju za skuplje sate
            if self.kalibracija.get("faza", "").startswith("mjerenje"):
                cmd = 0.0
            granica = ts < self.zabrana_punjenja_do or soc >= b["soc_max"] or soc <= b["soc_min"]
            if cmd is None and granica:
                cmd = -neto  # na granicama jezgra preuzima i reže smjer koji nije dopušten
            if cmd is None:
                self._postavi("baterija_auto", 1.0, ts, osvjezi_s=60)
                self._naredbe_zadnje.pop("baterija_snaga_w", None)
            else:
                if ts < self.zabrana_punjenja_do or soc >= b["soc_max"]:
                    cmd = min(cmd, 0.0)
                if soc <= b["soc_min"]:
                    cmd = max(cmd, 0.0)
                cmd = max(-b["max_praznjenje_kw"] * 1000, min(b["max_punjenje_kw"] * 1000, cmd))
                self._postavi("baterija_snaga_w", round(cmd, -1), ts, osvjezi_s=30)
                self._naredbe_zadnje.pop("baterija_auto", None)

        # 8) zapis i satni zbroj
        uzorak = {"dt": dt, "pv": pv, "potr": potr, "mreza": mreza_w, "bat": bat_w or 0.0, "soc": soc,
                  "ck": cijena["kupnja"], "cp": cijena["prodaja"], "bojler": o.get("bojler_snaga_w", 0.0),
                  "pumpa": self.releji.get("pumpa", False),
                  "pumpa_w": self.cfg["navodnjavanje"]["pumpa_kw"] * 1000 if self.releji.get("pumpa") else 0.0,
                  "presk": self.navodnjavanje.ustedjeno_min - presk_prije,
                  "pastir_ok": (min((x for x in self.pastir_izlaz.get("naponi", [None])[1:] if x is not None),
                                    default=0) >= self.cfg["pastir"]["min_kv"]) if self.pastir_izlaz else None,
                  "o": {k: o[k] for k in ("baterija_temp_c", "baterija_napon_v", "tlo_z1_vlaga", "tlo_z2_vlaga")
                        if k in o}}
        self.dnevnik.zapisi(TELEMETRIJA, uzorak, ts=ts)
        self._akumuliraj(uzorak, ts)
        self._dnevno(ts, dt, o, pv)

        if ts - self.zadnja_snimka >= 300:
            self.spremi_snimku(ts)
        if self.kopije.odredista and ts - self.zadnja_kopija >= interval["kopija"]:
            self.napravi_kopiju(ts)
        return {"ts": ts, "nacin": self.nacin, "pastir": self.pastir.nacin}

    def _isplati_cuvati(self, h: int, cijena: dict, soc: float, punjenje: bool = False) -> bool:
        """Kupnja iz mreže sada (umjesto baterije) isplati se samo ako baterija NEĆE dostajati do
        sljedećeg punjenja suncem, a sati u kojima bi nestalo energije skuplji su od sadašnjeg
        za gubitke i trošenje baterije. Inače bi sačuvanu energiju sunce ionako "pregazilo"."""
        b = self.cfg["baterija"]
        rezerva = self.parametri.get("rezerva_soc", b["soc_min"])
        dostupno = max(0.0, soc - rezerva) * b["kapacitet_kwh"] * 0.95
        potrebno, cijene_manjka = 0.0, []
        for p in self.plan[h:h + 36]:
            visak = (p.get("pv_w", 0) - p.get("potr_w", 0)) / 1000
            if visak > 0.5 and p is not self.plan[h]:
                break  # sunce opet puni bateriju
            potrebno += max(0.0, -visak)
            if potrebno > dostupno:
                cijene_manjka.append(p["cijena"])
        if not cijene_manjka:
            return False
        trosenje = (2 if punjenje else 1) * b["trosak_ciklusa_eur_kwh"]
        return max(cijene_manjka) * (0.9 if punjenje else 1.0) - trosenje > cijena["kupnja"]

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
                "izvjestaji": self.izvjestaji_izradjeni[-50:]}

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
        }
