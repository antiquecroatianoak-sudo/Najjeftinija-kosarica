"""Javni API v1 – stabilno, verzionirano sučelje za ugradnju u pametne mreže, kućnu automatiku i vlastita sučelja.

Načela:
- resursi su imenice (`/pregled`, `/bojler`, `/povijest` …); JSON, UTF-8, vremena u UNIX sekundama, snage u W,
  energija u kWh, novac u EUR; nepoznata polja klijent smije zanemariti (unaprijed kompatibilno),
- svaka ruta ima OPSEG prava; uloga tokena određuje opsege (stanar / administrator / integracija),
- uživo: Server-Sent Events na `/api/v1/uzivo` (radi kroz proxyje, bez dodatnih biblioteka),
- specifikacija: `/api/v1/openapi.json` (OpenAPI 3.1), generirana iz iste tablice ruta – ne može odstupati od koda.
"""
from __future__ import annotations

import json
import time

from . import izvjestaji
from .povijest import SERIJE, je_poznata

VERZIJA_API = "1.0.0"

ULOGE: dict[str, set[str]] = {
    "stanar": {"citanje", "naredbe"},
    "integracija": {"citanje", "mreza"},          # operator mreže / agregator / kućna automatika
    "administrator": {"citanje", "naredbe", "dijagnostika", "upravljanje", "mreza"},
}

RASPONI = {"1h": 3600, "6h": 6 * 3600, "24h": 86400, "48h": 2 * 86400, "7d": 7 * 86400, "30d": 30 * 86400}
KORAK_ZA_RASPON = {"1h": 60, "6h": 300, "24h": 900, "48h": 1800, "7d": 3600, "30d": 6 * 3600}


class GreskaApi(Exception):
    def __init__(self, status: int, poruka: str):
        super().__init__(poruka)
        self.status, self.poruka = status, poruka


# ------------------------------------------------------------------ resursi (čiste funkcije nad jezgrom)
def _o(j) -> dict:
    return j.zadnje_ocitanje or {}


def tok(j) -> dict:
    o = _o(j)
    pv, potr = o.get("pv_snaga_w") or 0.0, o.get("potrosnja_w") or 0.0
    bat = o.get("baterija_snaga_w") or 0.0
    return {"vrijeme": j.sat(), "pv_w": round(pv), "potrosnja_w": round(potr),
            "mreza_w": round(potr - pv + bat) if j.mreza_dostupna else 0, "baterija_w": round(bat),
            "bojler_w": round(o.get("bojler_snaga_w") or 0.0), "pumpa_w": 750 if j.releji.get("pumpa") else 0,
            "mreza_dostupna": j.mreza_dostupna, "baterija_soc": o.get("baterija_soc")}


def bojler(j) -> dict:
    o = _o(j)
    t = o.get("bojler_temp_c")
    h = j._sat_plana(j.sat()) if j.plan else 0
    sljedece = next((p["ts"] for i, p in enumerate(j.plan) if i > h and i in j.raspored.get("bojler", [])), None)
    return {"temp_c": t, "spremna_topla_voda": None if t is None else t >= 42.0, "grije": bool(j.releji.get("bojler")),
            "snaga_w": o.get("bojler_snaga_w"), "energija_danas_kwh": round(j.dnevno.get("bojler_kwh", 0.0), 2),
            "sljedece_planirano_grijanje": sljedece, "odluka": j.odluke.get("bojler"),
            "rucno_do": j.rucno.get("bojler", (None, None))[1]}


def solar(j) -> dict:
    o = _o(j)
    ts = j.sat()
    lt = time.localtime(ts)
    pocetak_dana = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))
    prog = j.prognoza.niz(pocetak_dana, 24)
    trend = j.detektor.trendovi.get("pv_omjer")
    return {"snaga_w": o.get("pv_snaga_w"), "danas_kwh": round(j.dnevno.get("pv_wh", 0.0) / 1000, 2),
            "prognoza_danas_kwh": round(sum(p["pv_w"] for p in prog) / 1000, 1),
            "izvor_prognoze": prog[0]["izvor"] if prog else None, "instalirano_kwp": j.cfg["fotonapon"]["kwp"],
            "ucinak_prema_ocekivanom": round(trend.tocke[-1][1], 3) if trend and trend.tocke else None,
            "odrzavanje": [z for z in j.odrzavanje if z["pokazatelj"] == "pv_omjer"]}


def pastir(j) -> dict:
    p = j.pastir
    nap = j.pastir_izlaz.get("naponi") or []
    return {"nacin": p.nacin, "snaga_impulsa": p.snaga, "povratni_vod": p.r_zatvoren,
            "dionice": [{"dionica": k, "stanje": p.stanje_dionica[k], "kv": nap[k] if k < len(nap) else None,
                         "sklopka_zatvorena": p.sklopke[k]} for k in range(1, p.n + 1)],
            "izlaz_aparata_kv": nap[0] if nap else None, "baterija_aparata": _o(j).get("pastir_baterija_soc"),
            "dostupnost": (p.ispravno_s / p.ukupno_s) if p.ukupno_s else None, "dogadjaji": p.dogadjaji[-10:],
            "prag_kv": j.cfg["pastir"]["min_kv"]}


def navodnjavanje(j) -> dict:
    n = j.navodnjavanje
    return {"zone": [{"zona": k, "vlaga": z.zadnja_vlaga, "prag": z.prag, "cilj": z.cilj,
                      "zadnje_zalijevanje": z.zadnje_zalijevanje or None, "susenje_po_h": round(z.susenje_po_h, 3)}
                     for k, z in sorted(n.zone.items())],
            "aktivna_zona": n.aktivna, "pumpa": bool(j.releji.get("pumpa")),
            "kisa_12h_mm": j.prognoza.kisa_sljedecih(j.sat(), 12), "usteda_vode_min": round(n.ustedjeno_min, 1),
            "odluka": j.odluke.get("pumpa"), "zadnja_zalijevanja": n.dnevnik[-10:]}


def baterija(j) -> dict:
    o, b = _o(j), j.cfg["baterija"]
    trend = j.detektor.trendovi.get("baterija_otpor_mohm")
    return {"soc": o.get("baterija_soc"), "snaga_w": o.get("baterija_snaga_w"), "temp_c": o.get("baterija_temp_c"),
            "napon_v": o.get("baterija_napon_v"), "kapacitet_kwh": b["kapacitet_kwh"],
            "rezerva_soc": j.parametri.get("rezerva_soc"), "granice": {"min": b["soc_min"], "max": b["soc_max"]},
            "unutarnji_otpor_mohm": round(trend.tocke[-1][1], 1) if trend and trend.tocke else None,
            "odluka": j.odluke.get("baterija")}


def _status(j) -> list[dict]:
    """Pokazatelji automatike za sučelje: stanje (ok/upozorenje/kvar/info) + što radi automatika."""
    out = []
    p = j.pastir.nacin
    out.append({"podsustav": "pastir", "stanje": "ok" if p == "normalno" else "upozorenje" if p in ("prekid", "test")
                else "kvar", "tekst": {"normalno": "Ograda pod naponom", "izolirano": "Kvar izoliran, ostatak radi",
                                       "prekid": "Prekid žice – napaja se s druge strane",
                                       "trazenje": "Traži se kvar", "kvar_aparata": "Kvar aparata",
                                       "test": "Provjera izolirane dionice"}.get(p, p), "automatski": p != "normalno"})
    t = _o(j).get("bojler_temp_c")
    if t is not None:
        out.append({"podsustav": "bojler", "stanje": "ok" if t >= 42 else "info",
                    "tekst": "Topla voda spremna" if t >= 42 else ("Grije se" if j.releji.get("bojler")
                                                                   else "Voda se hladi – grijanje planirano"),
                    "automatski": True})
    n = j.navodnjavanje
    out.append({"podsustav": "navodnjavanje", "stanje": "info" if n.aktivna else "ok",
                "tekst": f"Zalijeva zonu {n.aktivna}" if n.aktivna else (j.navodnjavanje_izlaz or {}).get("razlog", "–"),
                "automatski": True})
    if not j.mreza_dostupna and j.cfg["mreza"]["dostupna"]:
        out.append({"podsustav": "mreza", "stanje": "upozorenje", "tekst": "Ispad mreže – otočni rad", "automatski": True})
    for a in j.detektor.aktivne.values():
        out.append({"podsustav": a.kanal.split("_")[0], "stanje": "kvar" if a.ozbiljnost == "kriticno" else "upozorenje",
                    "tekst": a.poruka, "automatski": bool(a.trosila)})
    for zm in j._aktivni_zahtjevi(j.sat()):
        out.append({"podsustav": "mreza", "stanje": "info", "tekst": f"Zahtjev mreže: {zm['vrsta']} {zm['snaga_w']:.0f} W",
                    "automatski": True})
    return out


def pregled(j) -> dict:
    """Sažetak za jednostavni prikaz stanara (jedan poziv = cijeli zaslon)."""
    u = j.usteda(j.sat())
    return {"vrijeme": j.sat(), "nacin_rada": j.nacin, "sigurno_stanje": j.u_sigurnom,
            "cijena": j.tarife.cijena(j.sat()), "usteda": {k: (v or {}).get("usteda_eur") for k, v in u.items()},
            "samoopskrba_mjesec": (u.get("mjesec") or {}).get("samoopskrba"), "tok": tok(j),
            "bojler": {k: v for k, v in bojler(j).items() if k in ("temp_c", "spremna_topla_voda", "grije")},
            "baterija": {k: v for k, v in baterija(j).items() if k in ("soc", "snaga_w", "rezerva_soc")},
            "solar": {k: v for k, v in solar(j).items() if k in ("snaga_w", "danas_kwh", "prognoza_danas_kwh")},
            "pastir": {"nacin": j.pastir.nacin, "dionice": j.pastir.stanje_dionica[1:]},
            "navodnjavanje": {"aktivna_zona": j.navodnjavanje.aktivna,
                              "zone": {k: z.zadnja_vlaga for k, z in j.navodnjavanje.zone.items()}},
            "status": _status(j)}


def dijagnostika(j) -> dict:
    from . import resursi
    nadzor = getattr(j, "nadzor", None)
    segmenti = j.dnevnik.segmenti()
    return {"vrijeme": j.sat(), "id": j.trezor.id_uredaja(), "nacin_rada": j.nacin, "sigurno_stanje": j.u_sigurnom,
            "uredaji": [u.opis() | {"dostupan": u.id not in j.offline_uredaji, "greska": j.offline_uredaji.get(u.id)}
                        for u in j.uredaji],
            "zadaci": nadzor.stanje() if nadzor else None, "resursi": resursi.opterecenje(),
            "ai": {"aktivan": j.ai_aktivan, "provjera": j.ai_provjera, "kvaliteta": j.ai.kvaliteta()},
            "anomalije": [a.kao_dict() for a in j.detektor.aktivne.values()], "odrzavanje": j.odrzavanje,
            "zastita": {k: v for k, v in j.zastita_do.items() if v > j.sat()}, "releji": j.releji,
            "dnevnik": {"segmenata": len(segmenti), "bajtova": sum(p.stat().st_size for p in segmenti),
                        "slijed": j.dnevnik.slijed, "oporavak": j.oporavak},
            "kopije": list(j.kopije.zadnje.values()),
            "oblak": {"ukljuceno": j.sinkronizacija.ukljuceno, "zadnji_uspjeh": j.sinkronizacija.zadnji_uspjeh,
                      "greska": j.sinkronizacija.greska, "pokazivac": j.sinkronizacija.pokazivac},
            "prognoza": {"greska": j.prognoza.greska, "sati": len(j.prognoza.sati)},
            "tarife": {"greska": j.tarife.greska, "dinamicka": bool(j.tarife.cijene)},
            "brojilo": {"konstanta": j.brojilo.konstanta, "izvor": j.brojilo.konstanta_izvor},
            "napredno": j.napredno, "plan": j.plan[:36]}


# ------------------------------------------------------------------ rute
def _povijest(j, upit) -> dict:
    imena = [s for s in (upit.get("serije", ["pv_w,potrosnja_w"])[0]).split(",") if s]
    if not imena or len(imena) > 12 or not all(je_poznata(s) for s in imena):
        raise GreskaApi(400, f"serije: do 12 imena iz {sorted(SERIJE)} ili pastir_v<k>_kv / tlo_<zona>_vlaga")
    do = j.sat()
    raspon = upit.get("raspon", ["24h"])[0]
    if raspon not in RASPONI:
        raise GreskaApi(400, f"raspon: jedan od {list(RASPONI)}")
    od = do - RASPONI[raspon]
    korak = int(upit.get("korak", [KORAK_ZA_RASPON[raspon]])[0])
    r = j.povijest.serija(imena, od, do, korak, j.sati)
    return r | {"jedinice": {s: SERIJE.get(s, ("kV" if s.startswith("pastir") else "%", "", False))[0] for s in imena}}


def _naredba(j, uloga, t) -> dict:
    akcija = (t or {}).get("akcija")
    ts = j.sat()
    if akcija == "topla_voda_sada":  # stanar: zagrij odmah (60 min), zaštita i dalje ima prednost
        j.rucno["bojler"] = (True, ts + 3600)
        j._dogadjaj("naredba", {"poruka": "Stanar: topla voda odmah (60 min)", "uloga": uloga})
        return {"ok": True, "do": ts + 3600}
    if akcija == "trosilo":
        if uloga != "administrator":
            raise GreskaApi(403, "samo administrator")
        tr = t.get("trosilo")
        if tr not in ("bojler", "uticnice", "hladnjak"):
            raise GreskaApi(400, "trosilo: bojler | uticnice | hladnjak (pastir i pumpa nisu ručni)")
        minuta = max(1, min(240, int(t.get("minuta", 30))))
        j.rucno[tr] = (bool(t.get("ukljuci")), ts + minuta * 60)
        j._dogadjaj("naredba", {"poruka": f"Ručno: {tr} {'uključeno' if t.get('ukljuci') else 'isključeno'} {minuta} min"})
        return {"ok": True}
    if akcija == "otkazi_rucno":
        j.rucno.pop(t.get("trosilo", ""), None)
        return {"ok": True}
    raise GreskaApi(400, "akcija: topla_voda_sada | trosilo | otkazi_rucno")


def _postavke(j, metoda, t):
    if metoda == "POST":
        try:
            j.postavi_napredno(t or {})
        except (ValueError, TypeError) as e:
            raise GreskaApi(400, str(e))
    return {"napredno": j.napredno, "ai_aktivan": j.ai_aktivan, "provjera": j.ai_provjera}


def _zahtjevi(j, metoda, upit, t):
    if metoda == "POST":
        try:
            return j.dodaj_zahtjev_mreze(t or {})
        except (ValueError, TypeError) as e:
            raise GreskaApi(400, str(e))
    if metoda == "DELETE":
        if not j.opozovi_zahtjev_mreze(upit.get("id", [""])[0]):
            raise GreskaApi(404, "nema takvog aktivnog zahtjeva")
        return {"ok": True}
    return {"zahtjevi": [z for z in j.zahtjevi_mreze if z["do"] > j.sat()]}


def _izvjestaj(j, upit):
    dana = max(1.0, min(366.0, float(upit.get("dana", ["7"])[0])))
    do = j.sat()
    izv = j.izvjestaj(do - dana * 86400, do, izvezi=False)
    return {"izvjestaj": izv, "potpis": izvjestaji.potpisi(izv, j.trezor)}


# (metoda, put, opseg, funkcija(j, uloga, metoda, upit, tijelo), sažetak)
RUTE = [
    ("GET", "/api/v1/sustav", "citanje", lambda j, u, m, q, t: {
        "id": j.trezor.id_uredaja(), "verzija_api": VERZIJA_API, "uloga": u, "opsezi": sorted(ULOGE[u]),
        "lokacija": j.cfg["lokacija"]["naziv"], "mogucnosti": {
            "pastir": j.pastir.n, "zone_navodnjavanja": sorted(j.navodnjavanje.zone), "mreza": j.cfg["mreza"]["dostupna"],
            "baterija_kwh": j.cfg["baterija"]["kapacitet_kwh"], "pv_kwp": j.cfg["fotonapon"]["kwp"]},
        "serije": {k: {"jedinica": v[0], "opis": v[1], "dulja_razdoblja": v[2]} for k, v in SERIJE.items()},
        "rasponi": list(RASPONI)}, "Identitet, uloga pozivatelja, mogućnosti i dostupne serije"),
    ("GET", "/api/v1/pregled", "citanje", lambda j, u, m, q, t: pregled(j), "Sažetak za stanare (jedan zaslon)"),
    ("GET", "/api/v1/tok", "citanje", lambda j, u, m, q, t: tok(j), "Trenutni tokovi energije"),
    ("GET", "/api/v1/povijest", "citanje", lambda j, u, m, q, t: _povijest(j, q),
     "Vremenske serije: ?serije=pv_w,potrosnja_w&raspon=24h[&korak=s]"),
    ("GET", "/api/v1/usteda", "citanje", lambda j, u, m, q, t: {
        "razdoblja": j.usteda(j.sat()), "po_danima": j.usteda_po_danima(int(q.get("dana", ["30"])[0]))},
     "Ušteda (procjena prema osnovici) po razdobljima i po danima"),
    ("GET", "/api/v1/bojler", "citanje", lambda j, u, m, q, t: bojler(j), "Bojler: temperatura, grijanje, plan"),
    ("GET", "/api/v1/solar", "citanje", lambda j, u, m, q, t: solar(j), "Sunčani paneli: snaga, dnevna proizvodnja, učinak"),
    ("GET", "/api/v1/baterija", "citanje", lambda j, u, m, q, t: baterija(j), "Baterija: napunjenost, snaga, zdravlje"),
    ("GET", "/api/v1/pastir", "citanje", lambda j, u, m, q, t: pastir(j), "Električni pastir po dionicama"),
    ("GET", "/api/v1/navodnjavanje", "citanje", lambda j, u, m, q, t: navodnjavanje(j), "Zone, vlaga, odluke"),
    ("GET", "/api/v1/odluke", "citanje", lambda j, u, m, q, t: {"odluke": j.odluke, "status": _status(j)},
     "Pokazatelji automatike: što sustav radi i zašto"),
    ("GET", "/api/v1/izvjestaj", "citanje", lambda j, u, m, q, t: _izvjestaj(j, q), "Potpisani izvještaj: ?dana=7"),
    ("POST", "/api/v1/naredbe", "naredbe", lambda j, u, m, q, t: _naredba(j, u, t),
     "Naredbe: {akcija: topla_voda_sada} (stanar) | {akcija: trosilo, trosilo, ukljuci, minuta} (administrator)"),
    ("GET", "/api/v1/dijagnostika", "dijagnostika", lambda j, u, m, q, t: dijagnostika(j),
     "Kontrolni centar: uređaji, zadaci, resursi, AI, dnevnik, kopije"),
    ("GET", "/api/v1/dogadjaji", "dijagnostika", lambda j, u, m, q, t: {"dogadjaji": [
        {"ts": z["t"], "vrsta": z["v"], "poruka": z["d"].get("poruka", ""), "ozbiljnost": z["d"].get("ozbiljnost")}
        for z in list(j.arhiva.citaj_od_vremena(j.sat() - float(q.get("sati", ["24"])[0]) * 3600))
        if z["v"] != "sat"][-200:]}, "Zadnji događaji: ?sati=24"),
    ("GET", "/api/v1/postavke", "upravljanje", lambda j, u, m, q, t: _postavke(j, m, t), "Napredne postavke"),
    ("POST", "/api/v1/postavke", "upravljanje", lambda j, u, m, q, t: _postavke(j, m, t),
     "Ručno premošćivanje (sigurnosne granice ostaju)"),
    ("GET", "/api/v1/fleksibilnost", "mreza", lambda j, u, m, q, t: j.fleksibilnost(),
     "Dostupna fleksibilnost za mrežu (W, h)"),
    ("GET", "/api/v1/mreza/zahtjevi", "mreza", lambda j, u, m, q, t: _zahtjevi(j, m, q, t), "Aktivni zahtjevi mreže"),
    ("POST", "/api/v1/mreza/zahtjevi", "mreza", lambda j, u, m, q, t: _zahtjevi(j, m, q, t),
     "Novi zahtjev: {vrsta: ogranici_uvoz|ogranici_izvoz|povecaj_potrosnju, snaga_w, od, do, izvor}"),
    ("DELETE", "/api/v1/mreza/zahtjevi", "mreza", lambda j, u, m, q, t: _zahtjevi(j, m, q, t), "Opoziv: ?id="),
]


def obradi(j, uloga: str, metoda: str, put: str, upit: dict, tijelo) -> tuple[int, dict]:
    if put == "/api/v1/openapi.json":
        return 200, openapi()
    kandidati = [r for r in RUTE if r[1] == put]
    if not kandidati:
        return 404, {"greska": "nepoznat resurs", "dokumentacija": "/api/v1/openapi.json"}
    ruta = next((r for r in kandidati if r[0] == metoda), None)
    if ruta is None:
        return 405, {"greska": f"dopuštene metode: {[r[0] for r in kandidati]}"}
    if ruta[2] not in ULOGE.get(uloga, set()):
        return 403, {"greska": f"uloga '{uloga}' nema opseg '{ruta[2]}'"}
    try:
        return 200, ruta[3](j, uloga, metoda, upit, tijelo)
    except GreskaApi as e:
        return e.status, {"greska": e.poruka}


def uzivo_poruka(j) -> str:
    """Jedan SSE događaj s tokom, statusom i najvažnijim brojkama (malo podataka, svake 2 s)."""
    o = j.zadnje_ocitanje or {}
    podaci = {"tok": tok(j), "bojler_temp_c": o.get("bojler_temp_c"), "bojler_grije": bool(j.releji.get("bojler")),
              "pastir": j.pastir.nacin, "pastir_dionice": j.pastir.stanje_dionica[1:],
              "zone": {k: z.zadnja_vlaga for k, z in j.navodnjavanje.zone.items()},
              "cijena": j.tarife.cijena(j.sat())["kupnja"], "status": _status(j)}
    return f"event: stanje\ndata: {json.dumps(podaci, default=str)}\n\n"


def openapi() -> dict:
    putovi: dict[str, dict] = {}
    for metoda, put, opseg, _, opis in RUTE:
        op = {"summary": opis, "security": [{"token": [opseg]}, {"kolacic": [opseg]}],
              "responses": {"200": {"description": "OK", "content": {"application/json": {}}},
                            "401": {"description": "potreban token"}, "403": {"description": "uloga nema opseg"}},
              "x-opseg": opseg}
        if metoda in ("POST",):
            op["requestBody"] = {"content": {"application/json": {"schema": {"type": "object"}}}}
        putovi.setdefault(put, {})[metoda.lower()] = op
    putovi["/api/v1/uzivo"] = {"get": {"summary": "Server-Sent Events: događaj 'stanje' svake 2 s (token u kolačiću "
                                                  "ili ?token=, jer EventSource ne šalje zaglavlja)",
                                       "x-opseg": "citanje", "responses": {"200": {"description": "text/event-stream"}}}}
    putovi["/api/v1/zdravlje"] = {"get": {"summary": "Provjera rada (bez tokena)", "responses": {"200": {"description": "OK"}}}}
    putovi["/api/v1/upari"] = {"post": {"summary": "Uparivanje jednokratnim kodom -> token s ulogom koda",
                                        "requestBody": {"content": {"application/json": {"schema": {
                                            "type": "object", "properties": {"kod": {"type": "string"},
                                                                             "ime": {"type": "string"}}}}}},
                                        "responses": {"200": {"description": "{token, uloga}"}}}}
    putovi["/api/v1/pristup/pozivnice"] = {"post": {"summary": "Administrator: novi jednokratni kod za ulogu "
                                                               "stanar | integracija | administrator",
                                                    "x-opseg": "upravljanje", "responses": {"200": {"description": "{kod, uloga, do}"}}}}
    return {"openapi": "3.1.0",
            "info": {"title": "Energija – lokalna jezgra", "version": VERZIJA_API,
                     "description": "Lokalni API jezgre za upravljanje energijom. Uloge: " +
                                    ", ".join(f"{k} ({', '.join(sorted(v))})" for k, v in ULOGE.items())},
            "servers": [{"url": "/"}],
            "components": {"securitySchemes": {
                "token": {"type": "http", "scheme": "bearer"},
                "kolacic": {"type": "apiKey", "in": "cookie", "name": "energija"}}},
            "paths": putovi}
