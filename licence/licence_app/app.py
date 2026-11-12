"""Composition root: builds every layer once and hands out per-organization
workspaces. The HTTP layer, CLI, scheduler and tests all go through here.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Callable

from .banking.service import BankService
from .config import Settings
from .db import Database
from .events import EventBus
from .models import Organization, ValidationError, parse_org_fields
from .rates import RateService, http_fetch
from .repository import SQLiteLicenseRepository
from .security import (LoginLimiter, Tokenizer, VerifiedCache, dummy_verify, hash_password, parse_basic,
                       parse_bearer, password_problem, token_hash, verify_password)
from .service import LicenseService
from .stores import (AuditLog, NotificationStore, OrganizationStore, PriceHistoryStore, RateStore, TokenStore,
                     UsageStore, User, UserStore, WebhookStore)
from .usage import UsageService
from .webhooks import WebhookService, post, resolve_public

log = logging.getLogger("licence.app")


class AuthError(Exception):
    def __init__(self, status: int, message: str, retry_after: float = 0):
        super().__init__(message)
        self.status, self.message, self.retry_after = status, message, retry_after


@dataclass(frozen=True)
class Principal:
    org: Organization
    user: User | None = None
    token_scope: str | None = None

    @property
    def actor(self) -> str:
        return self.user.username if self.user else f"token:{self.token_scope}"

    @property
    def is_admin(self) -> bool:
        return bool(self.user and self.user.is_admin)


@dataclass
class Workspace:
    org: Organization
    licenses: LicenseService
    usage: UsageService
    bank: BankService


class App:
    def __init__(self, settings: Settings, *, today: Callable[[], date] = date.today,
                 rate_fetch=http_fetch, webhook_sender=post, webhook_resolve=resolve_public):
        self.settings = settings
        self.db = Database(settings.db_path)
        self.today = today
        self.orgs = OrganizationStore(self.db)
        self.users = UserStore(self.db)
        self.tokens = TokenStore(self.db)
        self.audit = AuditLog(self.db)
        self.usage_store = UsageStore(self.db)
        self.prices = PriceHistoryStore(self.db)
        self.notifications = NotificationStore(self.db)
        self.webhook_store = WebhookStore(self.db)
        self.events = EventBus(self.notifications, self.webhook_store)
        self.rates = RateService(RateStore(self.db), settings.rates_url, rate_fetch)
        self.webhooks = WebhookService(self.webhook_store, settings.webhook_allow_private, webhook_sender,
                                       webhook_resolve)
        self.tokenizer = Tokenizer(settings.secret_key)
        self.verified = VerifiedCache()
        self.limiter = LoginLimiter()

    def close(self) -> None:
        self.db.close()

    # --- tenants & users --------------------------------------------------------
    def create_organization(self, name: str, slug: str, **fields) -> Organization:
        data = parse_org_fields({"name": name, "slug": slug, **fields}, partial=False)
        if self.orgs.by_slug(data["slug"]):
            raise ValidationError({"slug": "Organizacija s tom oznakom već postoji."})
        return self.orgs.create(**data)

    def update_organization(self, principal: Principal, data) -> Organization:
        fields = parse_org_fields(data, partial=True)
        if "slug" in fields and fields["slug"] != principal.org.slug and self.orgs.by_slug(fields["slug"]):
            raise ValidationError({"slug": "Oznaka je zauzeta."})
        org = self.orgs.update(principal.org.id, fields)
        self.audit.record(org.id, principal.actor, "update", "organization", org.id, fields)
        return org

    def create_user(self, org_id: str, username: str, password: str, role: str = "member") -> User:
        errors = {}
        if not username or len(username) > 80 or ":" in username:
            errors["username"] = "Korisničko ime: 1–80 znakova, bez dvotočke."
        elif self.users.by_username(username):
            errors["username"] = "Korisničko ime je zauzeto."
        if (problem := password_problem(password or "")):
            errors["password"] = problem
        if role not in ("admin", "member"):
            errors["role"] = "Uloga: admin ili member."
        if errors:
            raise ValidationError(errors)
        return self.users.create(org_id, username, hash_password(password), role)

    def bootstrap(self) -> None:
        """Create the first organization and admin from LICENCE_ADMIN_* (idempotent)."""
        s = self.settings
        if not (s.bootstrap_user and s.bootstrap_password):
            return
        if self.users.by_username(s.bootstrap_user):
            return
        name = s.bootstrap_org or "Moja organizacija"
        slug = "".join(ch if ch.isalnum() else "-" for ch in name.lower()).strip("-")[:40] or "org"
        org = self.orgs.by_slug(slug) or self.orgs.by_slug("default") or self.create_organization(name, slug)
        self.create_user(org.id, s.bootstrap_user, s.bootstrap_password, "admin")
        log.info("bootstrap_admin_created", extra={"fields": {"organization": org.slug, "user": s.bootstrap_user}})

    # --- authentication -----------------------------------------------------------
    def authenticate(self, authorization: str | None, client: str, *, allow_token: bool = False) -> Principal:
        bearer = parse_bearer(authorization)
        if bearer and allow_token:
            wait = self.limiter.retry_after(f"ip:{client}")
            if wait > 0:
                raise AuthError(429, "Previše neuspjelih pokušaja. Pokušajte kasnije.", wait)
            row = self.tokens.lookup(token_hash(bearer))
            if not row:
                self.limiter.failed(f"ip:{client}")
                raise AuthError(401, "Neispravan token.")
            return Principal(self.orgs.get(row["organization_id"]), token_scope=row["scope"])

        creds = parse_basic(authorization)
        if not creds:
            raise AuthError(401, "Potrebna je prijava.")
        username, password = creds
        keys = (f"ip:{client}", f"user:{username.casefold()}")
        wait = self.limiter.retry_after(*keys)
        if wait > 0:
            raise AuthError(429, "Previše neuspjelih prijava. Pokušajte kasnije.", wait)
        user = self.users.by_username(username)
        if user and self.verified.hit(username, password, user.password_hash):
            return Principal(self.orgs.get(user.organization_id), user=user)
        if user is None:
            dummy_verify(password)          # same timing as a real check
            ok = False
        else:
            ok = verify_password(password, user.password_hash)
        if not ok:
            self.limiter.failed(*keys)
            log.warning("login_failed", extra={"fields": {"user": username[:80], "client": client}})
            raise AuthError(401, "Neispravno korisničko ime ili lozinka.")
        self.limiter.succeeded(*keys)
        self.verified.add(username, password, user.password_hash)
        return Principal(self.orgs.get(user.organization_id), user=user)

    def change_password(self, principal: Principal, current: str, new: str) -> None:
        user = principal.user
        if user is None or not verify_password(current or "", user.password_hash):
            raise ValidationError({"current": "Trenutačna lozinka nije točna."})
        if (problem := password_problem(new or "")):
            raise ValidationError({"password": problem})
        self.users.set_password(user.id, hash_password(new))
        self.verified.forget_user(user.username)
        self.audit.record(principal.org.id, principal.actor, "change_password", "user", user.id)

    # --- workspaces ---------------------------------------------------------------
    def workspace(self, org: Organization, actor: str = "system") -> Workspace:
        repo = SQLiteLicenseRepository(self.db, org.id)
        licenses = LicenseService(repo, org, rates=self.rates, usage=self.usage_store, prices=self.prices,
                                  audit=self.audit, events=self.events, actor=actor, today=self.today)
        return Workspace(org, licenses, UsageService(licenses, self.usage_store, self.tokenizer),
                         BankService(licenses, self.tokenizer))
