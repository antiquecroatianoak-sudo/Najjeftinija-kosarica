"""Configuration from environment variables (12-factor). Every setting has a
safe default for local development; production refuses to start without the
values that protect data (secret key, admin credentials on first run)."""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from pathlib import Path


class ConfigError(RuntimeError):
    pass


def _bool(value: str | None, default: bool) -> bool:
    if value is None or value == "":
        return default
    if value.lower() in ("1", "true", "yes", "on", "da"):
        return True
    if value.lower() in ("0", "false", "no", "off", "ne"):
        return False
    raise ConfigError(f"Neispravna logička vrijednost: {value!r}")


def _int(env: dict, key: str, default: int, lo: int, hi: int) -> int:
    raw = env.get(key)
    try:
        value = default if raw in (None, "") else int(raw)
    except ValueError:
        raise ConfigError(f"{key} mora biti cijeli broj.") from None
    if not lo <= value <= hi:
        raise ConfigError(f"{key} mora biti između {lo} i {hi}.")
    return value


ECB_DAILY = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"


@dataclass(frozen=True)
class Settings:
    env: str = "development"               # development | production
    host: str = "127.0.0.1"
    port: int = 8000
    db_path: str = "licence.db"
    secret_key: str = ""                    # HMAC key for tokenisation and webhook ids
    log_level: str = "INFO"
    log_format: str = "json"                # json | text
    access_log: bool = True
    trust_proxy: bool = False               # honour X-Forwarded-For / -Proto (behind a reverse proxy)
    hsts: bool = False                      # send Strict-Transport-Security (only behind TLS)
    backup_dir: str | None = None
    backup_keep: int = 7
    rates_auto: bool = True                 # refresh ECB reference rates in the background
    rates_url: str = ECB_DAILY
    webhook_allow_private: bool = False     # allow webhooks to private/loopback addresses (dev/tests)
    maintenance: bool = True                # run the background scheduler
    bootstrap_org: str | None = None
    bootstrap_user: str | None = None
    bootstrap_password: str | None = None

    @property
    def production(self) -> bool:
        return self.env == "production"


def load_settings(env: dict | None = None, **overrides) -> Settings:
    env = dict(os.environ if env is None else env)
    mode = env.get("LICENCE_ENV", "development")
    if mode not in ("development", "production"):
        raise ConfigError("LICENCE_ENV mora biti development ili production.")
    db_path = env.get("LICENCE_DB", "licence.db")
    values = dict(
        env=mode,
        host=env.get("LICENCE_HOST", "0.0.0.0" if mode == "production" else "127.0.0.1"),
        port=_int(env, "LICENCE_PORT", 8000, 0, 65535),
        db_path=db_path,
        secret_key=env.get("LICENCE_SECRET_KEY", ""),
        log_level=env.get("LICENCE_LOG_LEVEL", "INFO").upper(),
        log_format=env.get("LICENCE_LOG_FORMAT", "json"),
        access_log=_bool(env.get("LICENCE_ACCESS_LOG"), True),
        trust_proxy=_bool(env.get("LICENCE_TRUST_PROXY"), False),
        hsts=_bool(env.get("LICENCE_HSTS"), False),
        backup_dir=env.get("LICENCE_BACKUP_DIR") or None,
        backup_keep=_int(env, "LICENCE_BACKUP_KEEP", 7, 1, 365),
        rates_auto=_bool(env.get("LICENCE_RATES_AUTO"), True),
        rates_url=env.get("LICENCE_RATES_URL", ECB_DAILY),
        webhook_allow_private=_bool(env.get("LICENCE_WEBHOOK_ALLOW_PRIVATE"), False),
        maintenance=_bool(env.get("LICENCE_MAINTENANCE"), True),
        bootstrap_org=env.get("LICENCE_ADMIN_ORG") or None,
        bootstrap_user=env.get("LICENCE_ADMIN_USER") or None,
        bootstrap_password=env.get("LICENCE_ADMIN_PASSWORD") or None,
    )
    values.update({k: v for k, v in overrides.items() if v is not None})
    settings = Settings(**values)

    if settings.log_format not in ("json", "text"):
        raise ConfigError("LICENCE_LOG_FORMAT mora biti json ili text.")
    if settings.production:
        if len(settings.secret_key) < 32:
            raise ConfigError("U produkciji je obavezan LICENCE_SECRET_KEY (najmanje 32 znaka).")
        if settings.webhook_allow_private:
            raise ConfigError("LICENCE_WEBHOOK_ALLOW_PRIVATE nije dopušten u produkciji.")
        if settings.bootstrap_password is not None and len(settings.bootstrap_password) < 12:
            raise ConfigError("LICENCE_ADMIN_PASSWORD mora imati najmanje 12 znakova.")
    elif not settings.secret_key:
        settings = _with_dev_key(settings)
    return settings


def _with_dev_key(settings: Settings) -> Settings:
    """Development without a key: keep a random one next to the database, so
    tokens stay stable across restarts. Never used in production."""
    from dataclasses import replace
    if settings.db_path == ":memory:":
        return replace(settings, secret_key=secrets.token_hex(32))
    key_file = Path(settings.db_path + ".key")
    if key_file.exists():
        key = key_file.read_text().strip()
    else:
        key = secrets.token_hex(32)
        key_file.write_text(key)
        key_file.chmod(0o600)
    return replace(settings, secret_key=key)
