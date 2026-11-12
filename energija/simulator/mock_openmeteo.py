"""Lažni Open-Meteo poslužitelj za izoliranu provjeru (bez interneta).

Odgovara na `/v1/forecast` u istom obliku kao pravi servis (hourly: time, shortwave_radiation,
temperature_2m, precipitation, cloud_cover; timeformat=unixtime), s determinističkim podacima
iz modela simulacije. Provjerava obavezne parametre upita (400 ako nedostaju), a `/zahtjevi`
vraća zapis primljenih upita, pa provjera može dokazati da je jezgra stvarno pitala za prognozu.
Opcija `--kvar N`: prvih N zahtjeva vraća 503 (provjera zamjenskog rada bez prognoze).
"""
from __future__ import annotations

import argparse
import json
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from jezgra import konfig
from jezgra.simulacija import Lokacija

OBAVEZNO = {"latitude", "longitude", "hourly"}
VARIJABLE = {"shortwave_radiation", "temperature_2m", "precipitation", "cloud_cover"}


def posluzitelj(host: str = "127.0.0.1", port: int = 0, kvar: int = 0) -> ThreadingHTTPServer:
    lok = Lokacija(konfig.ucitaj("/nepostojece"), time.time(), sjeme=7)
    zahtjevi: list[dict] = []
    stanje = {"kvar": kvar}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _json(self, kod: int, v) -> None:
            b = json.dumps(v).encode()
            self.send_response(kod)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            u = urllib.parse.urlparse(self.path)
            q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
            if u.path == "/zahtjevi":
                return self._json(200, zahtjevi)
            if u.path != "/v1/forecast":
                return self._json(404, {"error": True, "reason": "nema"})
            zahtjevi.append({"t": time.time(), "upit": q})
            if stanje["kvar"] > 0:
                stanje["kvar"] -= 1
                return self._json(503, {"error": True, "reason": "privremeno nedostupno (simulirani kvar)"})
            if not OBAVEZNO <= q.keys() or not VARIJABLE <= set(q["hourly"].split(",")):
                return self._json(400, {"error": True, "reason": "nedostaju parametri"})
            v = lok.prognoza_api(time.time())
            v.update({"latitude": float(q["latitude"]), "longitude": float(q["longitude"]), "timezone": "GMT"})
            return self._json(200, v)

    srv = ThreadingHTTPServer((host, port), H)
    srv.zahtjevi = zahtjevi
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--kvar", type=int, default=0)
    a = ap.parse_args()
    posluzitelj("0.0.0.0", a.port, a.kvar)
    print(f"Lažni Open-Meteo na :{a.port}/v1/forecast", flush=True)
    threading.Event().wait()


if __name__ == "__main__":
    main()
