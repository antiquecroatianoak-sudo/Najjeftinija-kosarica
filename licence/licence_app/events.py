"""Domain events -> notifications and webhook deliveries.

Services publish events; this module turns them into stored notifications
(shown in the app) and queued webhook deliveries (sent by the scheduler).
Queueing is a local DB write, so a slow receiver never slows a request.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .stores import NotificationStore, WebhookStore

EVENTS = (
    "license.created", "license.updated", "license.deleted",
    "license.expiring", "license.auto_inactive", "license.reactivated",
    "bank.matched", "bank.unmatched_recurring",
)


class EventBus:
    def __init__(self, notifications: NotificationStore, webhooks: WebhookStore):
        self.notifications = notifications
        self.webhooks = webhooks

    def publish(self, org_id: str, event: str, data: dict[str, Any], *,
                notify: str | None = None, dedupe_key: str | None = None,
                license_id: str | None = None) -> bool:
        """Returns False if a deduplicated notification already existed (nothing sent)."""
        if notify is not None:
            fresh = self.notifications.add(org_id, event, dedupe_key or f"{event}:{datetime.now(timezone.utc).isoformat()}",
                                           notify, license_id)
            if not fresh:
                return False
        payload = {"event": event, "organization_id": org_id,
                   "occurred_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "data": data}
        for hook in self.webhooks.subscribers(org_id, event):
            self.webhooks.enqueue(hook["id"], event, payload)
        return True
