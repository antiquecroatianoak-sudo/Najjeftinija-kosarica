"""Background scheduler: everything that must happen without a person.

One daemon thread runs due tasks in order; a failing task is logged and
retried at its next interval, it never stops the others or the server.

Task                      interval   what
webhooks                  20 s       deliver queued webhooks (retries with backoff)
usage_and_notifications   15 min     auto-inactivate unused licenses, renewal notices
exchange_rates            6 h        refresh ECB rates (if LICENCE_RATES_AUTO)
database                  24 h       quick_check, optimize, WAL checkpoint, backup + rotation,
                                     retention (usage 400 d, audit 730 d, read notices 90 d,
                                     finished deliveries 30 d)
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .app import App
from .usage import notify_expiring

log = logging.getLogger("licence.maintenance")


def run_usage_and_notifications(app: App) -> dict:
    stats = {"auto_inactive": 0, "notices": 0}
    for org in app.orgs.all():
        ws = app.workspace(org, actor="system")
        stats["auto_inactive"] += len(ws.usage.auto_inactivate())
        stats["notices"] += notify_expiring(ws.licenses)
    return stats


def run_rates(app: App) -> dict:
    if not app.settings.rates_auto:
        return {"skipped": "disabled"}
    return app.rates.refresh()


def run_database(app: App) -> dict:
    stats = app.db.optimize()
    if stats["quick_check"] != "ok":
        log.error("db_integrity_problem", extra={"fields": stats})
    stats["purged"] = {
        "usage": app.usage_store.purge_older_than(400),
        "audit": app.audit.purge_older_than(730),
        "notifications": app.notifications.purge_read_older_than(90),
        "deliveries": app.webhook_store.purge_finished_older_than(30),
    }
    if app.settings.backup_dir and app.db.path != ":memory:":
        stats["backup"] = str(backup(app, Path(app.settings.backup_dir), app.settings.backup_keep))
    return stats


def backup(app: App, directory: Path, keep: int) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = app.db.backup(directory / f"licence-{stamp}.db")
    for old in sorted(directory.glob("licence-*.db"))[:-keep]:
        old.unlink()
    return path


class Scheduler:
    def __init__(self, app: App, tasks: list[tuple[str, float, Callable[[App], dict]]] | None = None):
        self.app = app
        self.tasks = tasks or [
            ("webhooks", 20, lambda a: a.webhooks.deliver_due()),
            ("usage_and_notifications", 900, run_usage_and_notifications),
            ("exchange_rates", 6 * 3600, run_rates),
            ("database", 24 * 3600, run_database),
        ]
        self.status: dict[str, dict] = {}
        self._next = {name: 0.0 for name, _, _ in self.tasks}
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def run_task(self, name: str) -> dict:
        fn = next(f for n, _, f in self.tasks if n == name)
        started = time.monotonic()
        try:
            result = fn(self.app)
            self.status[name] = {"ok": True, "at": _now(), "ms": int((time.monotonic() - started) * 1000),
                                 "result": result}
            if result and any(v for v in result.values() if isinstance(v, int)):
                log.info("task_done", extra={"fields": {"task": name, **{k: v for k, v in result.items()
                                                                          if not isinstance(v, dict)}}})
        except Exception as e:
            self.status[name] = {"ok": False, "at": _now(), "error": f"{type(e).__name__}: {e}"[:300]}
            log.exception("task_failed", extra={"fields": {"task": name}})
        return self.status[name]

    def tick(self) -> None:
        now = time.monotonic()
        for name, interval, _ in self.tasks:
            if self._stop.is_set():
                return
            if now >= self._next[name]:
                self._next[name] = now + interval
                self.run_task(name)

    def start(self) -> None:
        def loop():
            while not self._stop.is_set():
                self.tick()
                self._stop.wait(5)
        self._thread = threading.Thread(target=loop, name="maintenance", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=10)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
