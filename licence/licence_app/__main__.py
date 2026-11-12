"""Run: python3 -m licence_app [--host 127.0.0.1] [--port 8000] [--db licence.db] [--demo]

Every option can also come from the environment: LICENCE_HOST, LICENCE_PORT, LICENCE_DB.
"""
from __future__ import annotations

import argparse
import os
import signal
from pathlib import Path

from .api import create_server
from .repository import SQLiteLicenseRepository
from .seed import seed_demo
from .service import LicenseService

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


def main() -> None:
    parser = argparse.ArgumentParser(description="Praćenje softverskih licenci")
    env = os.environ.get
    parser.add_argument("--host", default=env("LICENCE_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(env("LICENCE_PORT", "8000")))
    parser.add_argument("--db", default=env("LICENCE_DB", "licence.db"),
                        help="SQLite datoteka (':memory:' za privremeno)")
    parser.add_argument("--quiet", action="store_true", help="bez zapisa svakog zahtjeva")
    parser.add_argument("--demo", action="store_true", help="dodaj primjer licenci ako je baza prazna")
    args = parser.parse_args()

    repo = SQLiteLicenseRepository(args.db)
    service = LicenseService(repo)
    if args.demo and not repo.find():
        seed_demo(service)

    server = create_server(service, args.host, args.port, static_dir=WEB_DIR, verbose=not args.quiet)

    def stop(*_):  # systemd/docker send SIGTERM: shut down cleanly, close the DB
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    print(f"Licence: http://{args.host}:{server.server_address[1]}  (baza: {args.db})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        repo.close()


if __name__ == "__main__":
    main()
