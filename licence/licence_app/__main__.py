"""License Pulse server and admin CLI.

  python3 -m licence_app serve            run the server (default command)
  python3 -m licence_app create-org NAME SLUG
  python3 -m licence_app create-user ORG_SLUG USERNAME [--admin]   (password from prompt or LICENCE_NEW_PASSWORD)
  python3 -m licence_app create-token ORG_SLUG NAME                 (usage-ingest token, printed once)
  python3 -m licence_app migrate | backup DIR | check | refresh-rates | demo ORG_SLUG

Configuration comes from LICENCE_* environment variables (see config.py / docs/DEPLOY.md).
"""
from __future__ import annotations

import argparse
import getpass
import logging
import os
import signal
import sys
from pathlib import Path

from .api import create_server
from .app import App
from .config import ConfigError, load_settings
from .logs import setup_logging
from .maintenance import Scheduler, backup
from .models import ValidationError
from .seed import seed_demo

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
log = logging.getLogger("licence.main")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="licence_app", description="License Pulse")
    p.add_argument("command", nargs="?", default="serve")
    p.add_argument("args", nargs="*")
    p.add_argument("--host")
    p.add_argument("--port", type=int)
    p.add_argument("--db")
    p.add_argument("--admin", action="store_true")
    p.add_argument("--demo", action="store_true", help="serve: seed demo data into an empty first organization")
    a = p.parse_args(argv)

    try:
        settings = load_settings(host=a.host, port=a.port, db_path=a.db)
    except ConfigError as e:
        print(f"Konfiguracija: {e}", file=sys.stderr)
        return 2
    setup_logging(settings.log_level, settings.log_format)
    app = App(settings)
    try:
        return COMMANDS.get(a.command, _unknown)(app, a)
    except ValidationError as e:
        print("Greška: " + "; ".join(f"{k}: {v}" for k, v in e.errors.items()), file=sys.stderr)
        return 1
    finally:
        app.close()


def _unknown(app: App, a) -> int:
    print(f"Nepoznata naredba: {a.command}", file=sys.stderr)
    return 2


def _org(app: App, slug: str):
    org = app.orgs.by_slug(slug)
    if not org:
        raise ValidationError({"organization": f"Nema organizacije '{slug}'."})
    return org


def cmd_serve(app: App, a) -> int:
    app.bootstrap()
    if a.demo:
        orgs = app.orgs.all()
        if orgs and not app.workspace(orgs[0]).licenses.repo.find():
            seed_demo(app.workspace(orgs[0], "demo").licenses)
    if app.users.count() == 0:
        log.warning("no_users", extra={"fields": {"hint": "Postavite LICENCE_ADMIN_USER i LICENCE_ADMIN_PASSWORD "
                                                          "ili pokrenite create-user."}})
    scheduler = Scheduler(app) if app.settings.maintenance else None
    server = create_server(app, app.settings.host, app.settings.port, WEB_DIR, scheduler)
    if scheduler:
        scheduler.start()

    def stop(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    port = server.server_address[1]
    print(f"License Pulse: http://{app.settings.host}:{port}", flush=True)
    log.info("started", extra={"fields": {"host": app.settings.host, "port": port, "env": app.settings.env,
                                          "schema_version": app.db.version()}})
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        log.info("stopping")
        if scheduler:
            scheduler.stop()
        server.server_close()
    return 0


def cmd_create_org(app: App, a) -> int:
    name, slug = a.args
    org = app.create_organization(name, slug)
    print(f"Organizacija {org.slug} ({org.id})")
    return 0


def cmd_create_user(app: App, a) -> int:
    slug, username = a.args
    password = os.environ.get("LICENCE_NEW_PASSWORD") or getpass.getpass("Lozinka (min. 12 znakova): ")
    user = app.create_user(_org(app, slug).id, username, password, "admin" if a.admin else "member")
    print(f"Korisnik {user.username} ({user.role})")
    return 0


def cmd_create_token(app: App, a) -> int:
    from .security import new_api_token
    slug, name = a.args
    plain, hashed = new_api_token()
    app.tokens.create(_org(app, slug).id, name, hashed)
    print(plain)
    return 0


def cmd_migrate(app: App, a) -> int:
    print(f"Shema: verzija {app.db.version()}")
    return 0


def cmd_backup(app: App, a) -> int:
    print(backup(app, Path(a.args[0]), app.settings.backup_keep))
    return 0


def cmd_check(app: App, a) -> int:
    result = app.db.optimize()
    print(f"Shema {app.db.version()}, provjera: {result['quick_check']}")
    return 0 if result["quick_check"] == "ok" else 1


def cmd_refresh_rates(app: App, a) -> int:
    print(app.rates.refresh())
    return 0


def cmd_demo(app: App, a) -> int:
    seed_demo(app.workspace(_org(app, a.args[0]), "demo").licenses)
    return 0


COMMANDS = {"serve": cmd_serve, "create-org": cmd_create_org, "create-user": cmd_create_user,
            "create-token": cmd_create_token, "migrate": cmd_migrate, "backup": cmd_backup, "check": cmd_check,
            "refresh-rates": cmd_refresh_rates, "demo": cmd_demo}

if __name__ == "__main__":
    sys.exit(main())
