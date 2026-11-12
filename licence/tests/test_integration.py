"""Integration: real SQLite file + service + HTTP API, full license lifecycle,
including a server restart (data must survive) and concurrent writes."""
import http.client
import json
import os
import tempfile
import threading
import unittest
from datetime import date
from pathlib import Path

from licence_app.api import create_server
from licence_app.repository import SQLiteLicenseRepository
from licence_app.service import LicenseService

WEB = Path(__file__).resolve().parent.parent / "web"
TODAY = date(2026, 11, 12)


class Running:
    """A server on a random port backed by an SQLite file."""

    def __init__(self, db_path):
        self.repo = SQLiteLicenseRepository(db_path)
        service = LicenseService(self.repo, today=lambda: TODAY)
        self.server = create_server(service, port=0, static_dir=WEB, verbose=False)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.repo.close()

    def call(self, method, path, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        data = json.dumps(body).encode() if body is not None else None
        conn.request(method, path, body=data,
                     headers={"Content-Type": "application/json"} if data else {})
        res = conn.getresponse()
        raw = res.read()
        headers = dict(res.getheaders())
        conn.close()
        return res.status, (json.loads(raw) if raw and "json" in headers.get("Content-Type", "") else raw), headers


class LifecycleTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.dir.name, "licence.db")
        self.app = Running(self.db)

    def tearDown(self):
        self.app.stop()
        self.dir.cleanup()

    def restart(self):
        self.app.stop()
        self.app = Running(self.db)

    def test_entry_to_display_lifecycle(self):
        call = self.app.call
        # 1. entry
        status, created, _ = call("POST", "/api/licenses", {
            "name": "Šifre Tim", "category": "Sigurnost", "cost": "29,97", "currency": "eur",
            "billing_cycle": "quarterly", "start_date": "2025-02-20"})
        self.assertEqual(status, 201)
        self.assertEqual((created["cost"], created["currency"], created["monthly_cost"]),
                         ("29.97", "EUR", "9.99"))
        lid = created["id"]

        # 2. display: list, search (Unicode), meta, dashboard
        _, listing, _ = call("GET", "/api/licenses?q=%C5%A1ifre")  # "šifre"
        self.assertEqual([i["id"] for i in listing["items"]], [lid])
        _, meta, _ = call("GET", "/api/meta")
        self.assertEqual(meta["categories"], ["Sigurnost"])
        _, dash, _ = call("GET", "/api/dashboard")
        self.assertEqual(dash["totals"], [{"currency": "EUR", "monthly": "9.99", "yearly": "119.88", "count": 1}])
        self.assertEqual([e["id"] for e in dash["expiring"]], [lid])  # renews 20.11.2026
        self.assertEqual(dash["expiring"][0]["days"], 8)

        # 3. persistence across restart
        self.restart()
        call = self.app.call
        self.assertEqual(call("GET", f"/api/licenses/{lid}")[1], created)

        # 4. mark unused -> detected as inactive, counted as possible savings
        call("PATCH", f"/api/licenses/{lid}", {"status": "inactive"})
        _, dash, _ = call("GET", "/api/dashboard?days=5")
        self.assertEqual([i["id"] for i in dash["inactive"]["items"]], [lid])
        self.assertEqual(dash["inactive"]["waste"][0]["monthly"], "9.99")
        self.assertEqual(dash["expiring"], [])  # outside 5-day window

        # 5. cancel -> no longer billed anywhere
        call("PATCH", f"/api/licenses/{lid}", {"status": "cancelled"})
        _, dash, _ = call("GET", "/api/dashboard")
        self.assertEqual((dash["totals"], dash["inactive"]["items"], dash["expiring"]), ([], [], []))
        self.assertEqual(dash["counts"]["cancelled"], 1)

        # 6. full edit, then delete
        status, edited, _ = call("PUT", f"/api/licenses/{lid}", {
            "name": "Šifre Tim", "category": "Sigurnost", "cost": "120", "currency": "EUR",
            "billing_cycle": "yearly", "start_date": "2026-01-01", "status": "active"})
        self.assertEqual((status, edited["monthly_cost"]), (200, "10.00"))
        self.assertEqual(call("DELETE", f"/api/licenses/{lid}")[0], 204)
        self.restart()
        self.assertEqual(self.app.call("GET", f"/api/licenses/{lid}")[0], 404)
        self.assertEqual(self.app.call("GET", "/api/licenses")[1], {"items": []})

    def test_concurrent_creates_are_all_stored(self):
        errors = []

        def worker(n):
            for i in range(10):
                status, _, _ = self.app.call("POST", "/api/licenses", {
                    "name": f"T{n}-{i}", "category": "Test", "cost": "1", "currency": "EUR",
                    "billing_cycle": "monthly", "start_date": "2025-01-01"})
                if status != 201:
                    errors.append(status)

        threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        _, dash, _ = self.app.call("GET", "/api/dashboard")
        self.assertEqual(dash["totals"][0]["monthly"], "80.00")

    def test_security_headers(self):
        for path in ("/", "/api/health"):
            _, _, headers = self.app.call("GET", path)
            self.assertIn("default-src 'self'", headers["Content-Security-Policy"])
            self.assertEqual(headers["X-Frame-Options"], "DENY")


if __name__ == "__main__":
    unittest.main()
