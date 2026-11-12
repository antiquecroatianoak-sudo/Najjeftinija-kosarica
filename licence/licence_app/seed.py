"""Demo data (made up) for first run with --demo."""
from __future__ import annotations

from .service import LicenseService

DEMO = [
    {"name": "Slack Pro", "category": "Komunikacija", "cost": "43.75", "currency": "EUR",
     "billing_cycle": "monthly", "start_date": "2025-03-01", "status": "active"},
    {"name": "Figma Professional", "category": "Dizajn", "cost": "540", "currency": "USD",
     "billing_cycle": "yearly", "start_date": "2025-01-15", "status": "active"},
    {"name": "GitHub Team", "category": "Razvoj", "cost": "20", "currency": "USD",
     "billing_cycle": "monthly", "start_date": "2024-09-10", "status": "active"},
    {"name": "Adobe Creative Cloud", "category": "Dizajn", "cost": "71.99", "currency": "EUR",
     "billing_cycle": "monthly", "start_date": "2024-06-01", "status": "inactive"},
    {"name": "Zoom Pro", "category": "Komunikacija", "cost": "41.97", "currency": "EUR",
     "billing_cycle": "quarterly", "start_date": "2025-02-20", "status": "inactive"},
    {"name": "Notion Plus", "category": "Produktivnost", "cost": "96", "currency": "EUR",
     "billing_cycle": "yearly", "start_date": "2024-11-25", "status": "active"},
    {"name": "Trello Standard", "category": "Produktivnost", "cost": "5", "currency": "EUR",
     "billing_cycle": "monthly", "start_date": "2023-04-01", "status": "cancelled"},
]


def seed_demo(service: LicenseService) -> None:
    for item in DEMO:
        service.create(item)
