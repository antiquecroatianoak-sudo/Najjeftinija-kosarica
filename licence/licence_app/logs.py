"""Structured logging to stdout (one JSON object per line by default), so any
log collector (Docker, journald, Loki, CloudWatch...) can index it.

Use `log.info("event_name", extra={"fields": {...}})`. Never log request
bodies, passwords, tokens or bank data.
"""
from __future__ import annotations

import json
import logging
import sys
import time


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)) + f".{int(record.msecs):03d}Z",
            "level": record.levelname.lower(),
            "logger": record.name,
            "msg": record.getMessage(),
        }
        entry.update(getattr(record, "fields", {}) or {})
        if record.exc_info:
            entry["error"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        fields = getattr(record, "fields", None)
        return f"{base} {json.dumps(fields, ensure_ascii=False, default=str)}" if fields else base


def setup_logging(level: str = "INFO", fmt: str = "json") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if fmt == "json"
                         else TextFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger("licence")
    root.handlers[:] = [handler]
    root.setLevel(level)
    root.propagate = False
