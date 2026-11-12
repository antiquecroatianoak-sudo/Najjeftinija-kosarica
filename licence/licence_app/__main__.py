"""Run: python3 -m licence_app [--host 127.0.0.1] [--port 8000] [--db licence.db] [--demo]"""
from __future__ import annotations

import argparse
from pathlib import Path

from .api import create_server
from .repository import SQLiteLicenseRepository
from .seed import seed_demo
from .service import LicenseService

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


def main() -> None:
    parser = argparse.ArgumentParser(description="Praćenje softverskih licenci")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db", default="licence.db", help="SQLite datoteka (':memory:' za privremeno)")
    parser.add_argument("--demo", action="store_true", help="dodaj primjer licenci ako je baza prazna")
    args = parser.parse_args()

    repo = SQLiteLicenseRepository(args.db)
    service = LicenseService(repo)
    if args.demo and not repo.list():
        seed_demo(service)

    server = create_server(service, args.host, args.port, static_dir=WEB_DIR)
    print(f"Licence: http://{args.host}:{server.server_address[1]}  (baza: {args.db})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        repo.close()


if __name__ == "__main__":
    main()
