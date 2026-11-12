"""Nadzor i upravljanje električnim pastirom (ograda) s automatskom izolacijom kvara.

Topologija: aparat (energizer) -> dionice 1..n u nizu. Na početku svake dionice k je
visokonaponska sklopka S_k (relej za ogradu), na kraju svake dionice mjerač napona
impulsa V_k (kV). V_0 je napon na izlazu aparata. Opcionalno povratni vod: kraj dionice n
spojen natrag na aparat preko sklopke R (prsten) – omogućuje napajanje s druge strane.

Prepoznavanje (potvrda u 2 uzastopna očitanja, da jedan loš impuls ne pokrene akciju):
- kratki spoj / jak odvod: pada napon cijele ograde, uključujući V_0 (aparat je preopterećen),
- prekid žice u dionici k: V_{k-1} je dobar, V_k ≈ 0, aparat nije opterećen,
- slaba ograda (vegetacija): napon ispod `min_kv`, ali iznad praga kvara.

Automatska reakcija, bez ručne intervencije:
- kratki spoj: binarno traženje otvaranjem sklopki (log2 n koraka); pokvarena dionica se
  odspoji s obje strane, a dionice iza nje napajaju se kroz povratni vod,
- prekid: zatvara se povratni vod, pa su sve dionice (i obje polovice prekinute) pod naponom,
- svakih `ponovni_test_min` minuta izolirana dionica se nakratko ponovno spaja; ako je kvar
  nestao (grana pala s žice pa maknuta), vraća se normalan rad,
- snaga aparata: štedni način dok je ograda zdrava s rezervom napona, puna snaga kod
  slabljenja; vlastita mala baterija aparata puni se iz glavne samo kad ima viška sunca
  ili kad joj prijeti pražnjenje (zaštita stoke uvijek ima prednost).
"""
from __future__ import annotations


class Pastir:
    def __init__(self, cfg: dict, n_dionica: int, povratni_vod: bool, stanje: dict | None = None):
        p = cfg["pastir"]
        self.min_kv, self.kvar_kv = p["min_kv"], p["kvar_kv"]
        self.ponovni_test_s = p["ponovni_test_min"] * 60
        self.eco = p["eco_snaga"]
        self.n = n_dionica
        self.povrat = povratni_vod
        s = stanje or {}
        self.nacin = s.get("nacin", "normalno")       # normalno | trazenje | izolirano | prekid | test
        self.kvar_dionica: int | None = s.get("kvar_dionica")
        self.izolirano_od = s.get("izolirano_od", 0.0)
        self.dogadjaji: list[dict] = s.get("dogadjaji", [])
        self.ispravno_s = s.get("ispravno_s", 0.0)
        self.ukupno_s = s.get("ukupno_s", 0.0)
        self._potvrda: dict[str, int] = {}
        self._lo = self._hi = self._m = 0
        self._prethodni_nacin = None
        self.snaga = s.get("snaga", 1.0)
        self.sklopke = s.get("sklopke") or [True] * (n_dionica + 1)  # indeks 1..n; [0] se ne koristi
        self.r_zatvoren = s.get("r_zatvoren", False)
        if self.nacin == "trazenje" or len(self.sklopke) != n_dionica + 1:  # prekinuto traženje: kreni ispočetka
            self.nacin, self.sklopke, self.r_zatvoren = "normalno", [True] * (n_dionica + 1), False
        self.stanje_dionica = ["?"] * (n_dionica + 1)

    def stanje(self) -> dict:
        return {"nacin": self.nacin if self.nacin != "trazenje" else "normalno",
                "kvar_dionica": self.kvar_dionica, "izolirano_od": self.izolirano_od,
                "dogadjaji": self.dogadjaji[-100:], "ispravno_s": self.ispravno_s, "ukupno_s": self.ukupno_s,
                "snaga": self.snaga, "sklopke": self.sklopke, "r_zatvoren": self.r_zatvoren}

    def _potvrdi(self, kljuc: str, uvjet: bool, puta: int = 2) -> bool:
        self._potvrda[kljuc] = self._potvrda.get(kljuc, 0) + 1 if uvjet else 0
        return self._potvrda[kljuc] >= puta

    def _dogadjaj(self, ts: float, vrsta: str, poruka: str, **x) -> None:
        self.dogadjaji.append({"ts": ts, "vrsta": vrsta, "poruka": poruka, **x})
        del self.dogadjaji[:-100]

    def _normalno(self) -> None:
        self.sklopke = [True] * (self.n + 1)
        self.r_zatvoren = False

    def _izoliraj(self, f: int) -> None:
        """Odspoji dionicu f; ako postoji prsten, dionice iza nje napajaj s druge strane."""
        self.sklopke = [True] * (self.n + 1)
        self.sklopke[f] = False
        self.r_zatvoren = False
        if self.povrat and f < self.n:
            self.sklopke[f + 1] = False
            self.r_zatvoren = True

    def korak(self, ts: float, dt: float, v: list[float | None], baterija_aparata: float | None,
              glavna_soc: float, visak_sunca: bool, rezerva_soc: float) -> dict:
        """v = [V_0, V_1..V_n] u kV. Vraća naredbe i stanje."""
        ok = lambda x: x is not None and x >= self.min_kv  # noqa: E731
        mrtvo = lambda x: x is not None and x < self.kvar_kv  # noqa: E731
        v0 = v[0]

        if self.nacin == "normalno":
            sve_nisko = all(mrtvo(x) for x in v if x is not None)
            if self._potvrdi("kratki", v0 is not None and v0 < self.kvar_kv and sve_nisko):
                self.nacin, self._lo, self._hi = "trazenje", 1, self.n
                self._dogadjaj(ts, "kratki_spoj", "Kratki spoj/jak odvod na ogradi – tražim dionicu")
                self._sljedeci_test(0)
            else:
                prekid = next((k for k in range(1, self.n + 1) if ok(v[k - 1]) and mrtvo(v[k])), None)
                if self._potvrdi("prekid", prekid is not None and ok(v0)) and prekid is not None:
                    self.kvar_dionica, self.izolirano_od = prekid, ts
                    if self.povrat:
                        self.r_zatvoren = True
                        self.nacin = "prekid"
                        self._dogadjaj(ts, "prekid", f"Prekid žice u dionici {prekid} – napajam ostatak kroz povratni vod",
                                       dionica=prekid)
                    else:
                        self._dogadjaj(ts, "prekid", f"Prekid žice u dionici {prekid} – dionice iza nje bez napona",
                                       dionica=prekid)
                        self.nacin = "prekid"
        elif self.nacin == "trazenje":
            oporavak = ok(v0)
            if self._m == 0:  # prvi test: cijela ograda odspojena
                if not oporavak:
                    self._normalno()
                    self.nacin, self.kvar_dionica, self.izolirano_od = "kvar_aparata", 0, ts
                    self._dogadjaj(ts, "kvar_aparata", "Napon nizak i bez spojene ograde – kvar aparata ili priključka")
                else:
                    self._lo, self._hi = 1, self.n
            elif oporavak:
                self._lo = self._m + 1
            else:
                self._hi = self._m
            if self.nacin == "trazenje":
                if self._lo >= self._hi:
                    f = self._lo
                    self.kvar_dionica, self.izolirano_od, self.nacin = f, ts, "izolirano"
                    self._izoliraj(f)
                    zahvaceno = [f] if (self.povrat and f < self.n) or f == self.n else list(range(f, self.n + 1))
                    self._dogadjaj(ts, "izolacija", f"Dionica {f} izolirana; bez napona: {zahvaceno}",
                                   dionica=f, bez_napona=zahvaceno)
                else:
                    self._sljedeci_test((self._lo + self._hi - 1) // 2)
        elif self.nacin in ("izolirano", "prekid", "kvar_aparata") and ts - self.izolirano_od >= self.ponovni_test_s:
            self._prethodni_nacin = self.nacin
            self.nacin = "test"
            self._normalno()
        elif self.nacin == "test":
            f = self.kvar_dionica or 1
            zdravo = ok(v0) and not any(mrtvo(x) for x in v[1:] if x is not None)
            if zdravo:
                self._dogadjaj(ts, "oporavak", f"Dionica {f} ponovno ispravna – vraćen normalan rad", dionica=f)
                self.nacin, self.kvar_dionica = "normalno", None
            else:
                self.nacin, self.izolirano_od = self._prethodni_nacin or "izolirano", ts
                if self.nacin == "izolirano":
                    self._izoliraj(f)
                elif self.nacin == "prekid":
                    self.r_zatvoren = self.povrat

        # stanje dionica i snaga aparata
        for k in range(1, self.n + 1):
            x = v[k]
            if self.nacin in ("izolirano", "test") and k == self.kvar_dionica:
                self.stanje_dionica[k] = "izolirana"
            elif self.nacin == "prekid" and k == self.kvar_dionica and self.povrat:
                self.stanje_dionica[k] = "prekid"
            elif self.nacin == "prekid" and k == self.kvar_dionica:
                self.stanje_dionica[k] = "prekid"
            elif x is None:
                self.stanje_dionica[k] = "nema_mjerenja"
            elif x >= self.min_kv:
                self.stanje_dionica[k] = "ispravna"
            elif x >= self.kvar_kv:
                self.stanje_dionica[k] = "slaba"
            else:
                self.stanje_dionica[k] = "bez_napona"
        pod_naponom = [x for k, x in enumerate(v[1:], 1) if x is not None and self.stanje_dionica[k] != "izolirana"]
        najmanji = min(pod_naponom) if pod_naponom else None
        if self.nacin != "normalno" or najmanji is None:
            self.snaga = 1.0
        elif self.snaga == self.eco:  # histereza: ostani u štednom dok ima rezerve
            self.snaga = self.eco if najmanji > 1.15 * self.min_kv else 1.0
        elif najmanji > 1.5 * self.min_kv:
            self.snaga = self.eco
        self.ukupno_s += dt
        if najmanji is not None and najmanji >= self.min_kv:
            self.ispravno_s += dt

        # punjenje baterije aparata iz glavne baterije
        b = baterija_aparata if baterija_aparata is not None else 1.0
        puni = b < 0.4 or (visak_sunca and b < 0.95) or (glavna_soc > rezerva_soc + 0.15 and b < 0.7)

        slabe = [k for k in range(1, self.n + 1) if self.stanje_dionica[k] == "slaba"]
        return {
            "sklopke": {k: self.sklopke[k] for k in range(1, self.n + 1)},
            "povratni_vod": self.r_zatvoren,
            "snaga": self.snaga,
            "punjenje": puni,
            "nacin": self.nacin,
            "dionice": self.stanje_dionica[1:],
            "slabe": slabe,
            "dostupnost": self.ispravno_s / self.ukupno_s if self.ukupno_s else None,
        }

    def _sljedeci_test(self, m: int) -> None:
        """Spoji dionice 1..m, odspoji m+1..n (otvaranjem S_{m+1})."""
        self._m = m
        self.sklopke = [True] * (self.n + 1)
        self.r_zatvoren = False
        if m < self.n:
            self.sklopke[m + 1] = False
