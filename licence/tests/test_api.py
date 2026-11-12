"""HTTP API and full-stack integration (SQLite file -> services -> HTTP)."""
import base64
import os
import tempfile
import threading
import unittest

from helpers import PASSWORD, Running, basic, license_data, make_app, org_with_admin
from test_platform import CAMT

BODY = {"name": "Notion", "category": "Produktivnost", "cost": "96", "currency": "EUR",
        "billing_cycle": "yearly", "start_date": "2024-11-25"}


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


class ApiTest(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        self.org, _ = org_with_admin(self.app)
        self.app.create_user(self.org.id, "marko", PASSWORD, "member")
        self.other, _ = org_with_admin(self.app, "beta", "bruno")
        self.srv = Running(self.app)
        self.call = self.srv.call

    def tearDown(self):
        self.srv.stop()
        self.app.close()

    # --- authentication & protection ------------------------------------------
    def test_authentication_required(self):
        status, body, headers = self.call("GET", "/api/licenses", auth="")
        self.assertEqual(status, 401)
        self.assertIn('Basic realm="License Pulse"', headers["www-authenticate"])
        self.assertEqual(self.call("GET", "/api/licenses", password="kriva-lozinka-xx")[0], 401)
        self.assertEqual(self.call("GET", "/api/health", auth="")[0], 200)
        self.assertEqual(self.call("GET", "/", auth="")[0], 401)           # the page itself asks for login
        self.assertEqual(self.call("GET", "/css/app.css", auth="")[0], 200)  # assets are public
        self.assertEqual(self.call("GET", "/")[0], 200)

    def test_brute_force_is_throttled(self):
        for _ in range(5):
            self.assertEqual(self.call("GET", "/api/me", user="nobody", password="x" * 12)[0], 401)
        status, _, headers = self.call("GET", "/api/me", user="nobody", password="x" * 12)
        self.assertEqual(status, 429)
        self.assertIn("retry-after", headers)

    def test_csrf_protection(self):
        status, body, _ = self.call("POST", "/api/licenses", BODY, headers={"X-Requested-With": None})
        self.assertEqual((status, body["error"]["code"]), (403, "csrf"))
        status, _, _ = self.call("POST", "/api/licenses", BODY, headers={"Origin": "https://evil.example"})
        self.assertEqual(status, 403)
        self.assertEqual(self.call("POST", "/api/licenses", BODY)[0], 201)

    def test_tenant_isolation_over_http(self):
        _, created, _ = self.call("POST", "/api/licenses", BODY)
        lid = created["id"]
        self.assertEqual(self.call("GET", f"/api/licenses/{lid}", user="bruno")[0], 404)
        self.assertEqual(self.call("PATCH", f"/api/licenses/{lid}", {"status": "cancelled"}, user="bruno")[0], 404)
        self.assertEqual(self.call("DELETE", f"/api/licenses/{lid}", user="bruno")[0], 404)
        self.assertEqual(self.call("GET", "/api/licenses", user="bruno")[1]["items"], [])
        self.assertEqual(self.call("GET", f"/api/licenses/{lid}")[1]["status"], "active")

    def test_admin_only_routes(self):
        for method, path, body in (("GET", "/api/users", None), ("POST", "/api/tokens", {"name": "x"}),
                                   ("PATCH", "/api/organization", {"name": "X"}), ("GET", "/api/audit", None),
                                   ("POST", "/api/webhooks", {"url": "https://example.com"})):
            self.assertEqual(self.call(method, path, body, user="marko")[0], 403, path)
        self.assertEqual(self.call("GET", "/api/licenses", user="marko")[0], 200)

    def test_security_headers_and_request_id(self):
        for path in ("/", "/api/me", "/js/main.js"):
            _, _, h = self.call("GET", path)
            self.assertIn("default-src 'self'", h["content-security-policy"])
            self.assertEqual(h["x-frame-options"], "DENY")
            self.assertEqual(h["x-content-type-options"], "nosniff")
            self.assertTrue(h["x-request-id"])
        self.assertEqual(self.call("GET", "/api/me", headers={"X-Request-Id": "abc123"})[2]["x-request-id"], "abc123")
        self.assertEqual(self.call("GET", "/../licence_app/app.py")[0], 404)

    def test_bad_requests(self):
        self.assertEqual(self.call("POST", "/api/licenses", raw=b"{nope")[0], 400)
        self.assertEqual(self.call("POST", "/api/licenses", raw=b"[]")[0], 422)
        self.assertEqual(self.call("POST", "/api/licenses", raw=b"x=1", headers={"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.call("POST", "/api/licenses", raw=b"x" * (65 * 1024))[0], 413)
        self.assertEqual(self.call("DELETE", "/api/licenses")[0], 405)
        self.assertEqual(self.call("GET", "/api/nope")[0], 404)
        self.assertEqual(self.call("GET", "/api/licenses?status=weird")[0], 422)
        self.assertEqual(self.call("GET", "/api/bank/connect")[0], 501)    # live bank API not configured

    # --- organization, users, tokens --------------------------------------------
    def test_organization_branding_and_users(self):
        status, org, _ = self.call("PATCH", "/api/organization", {"name": "Acme Grupa", "accent": "#0a7d33",
                                                                    "reference_currency": "usd"})
        self.assertEqual((status, org["name"], org["reference_currency"]), (200, "Acme Grupa", "USD"))
        self.assertEqual(self.call("GET", "/api/me")[1]["organization"]["accent"], "#0a7d33")
        self.assertEqual(self.call("PATCH", "/api/organization", {"accent": "red"})[0], 422)
        status, user, _ = self.call("POST", "/api/users", {"username": "iva", "password": "kratka"})
        self.assertEqual(status, 422)
        status, user, _ = self.call("POST", "/api/users", {"username": "iva", "password": PASSWORD})
        self.assertEqual(status, 201)
        self.assertEqual(self.call("GET", "/api/me", user="iva")[1]["organization"]["name"], "Acme Grupa")
        me = self.call("GET", "/api/me")[1]["user"]
        self.assertEqual(self.call("DELETE", f"/api/users/{me['id']}")[0], 422)  # not yourself

    def test_password_change_invalidates_cache(self):
        self.assertEqual(self.call("GET", "/api/me", user="marko")[0], 200)
        new = "nova-dugacka-lozinka-2"
        self.assertEqual(self.call("POST", "/api/me/password", {"current": "x", "password": new}, user="marko")[0], 422)
        self.assertEqual(self.call("POST", "/api/me/password", {"current": PASSWORD, "password": new}, user="marko")[0], 204)
        self.assertEqual(self.call("GET", "/api/me", user="marko")[0], 401)
        self.assertEqual(self.call("GET", "/api/me", user="marko", password=new)[0], 200)

    def test_usage_token_flow(self):
        self.call("POST", "/api/licenses", {**BODY, "usage_key": "notion", "status": "inactive"})
        status, tok, _ = self.call("POST", "/api/tokens", {"name": "Okta"})
        self.assertTrue(tok["token"].startswith("lp_"))
        token = tok["token"]
        events = {"events": [{"license": "notion", "user": "ana@acme.hr"}]}
        self.assertEqual(self.call("POST", "/api/usage", events, auth="Bearer lp_wrong")[0], 401)
        status, res, _ = self.call("POST", "/api/usage", events, auth=f"Bearer {token}",
                                   headers={"X-Requested-With": None})
        self.assertEqual((status, res["accepted"], len(res["reactivated"])), (202, 1, 1))
        # tokens only work for usage ingestion
        self.assertEqual(self.call("GET", "/api/licenses", auth=f"Bearer {token}")[0], 401)
        items = self.call("GET", "/api/licenses")[1]["items"]
        self.assertEqual((items[0]["status"], items[0]["active_users_30d"]), ("active", 1))
        self.assertIn(token[:3], "lp_")
        stored = self.app.db.scalar("SELECT token_hash FROM api_tokens")
        self.assertNotEqual(stored, token)

    # --- data flows -----------------------------------------------------------------
    def test_import_export_roundtrip(self):
        csv_data = ("Naziv;Kategorija;Cijena;Valuta;Naplata;Datum početka\n"
                    "Slack;Komunikacija;43,75;EUR;mjesečno;1.3.2025.\n"
                    "Miro;Dizajn;=1+1;EUR;mjesečno;1.3.2025.\n").encode()
        status, prev, _ = self.call("POST", "/api/import/preview", {"filename": "a.csv", "content_base64": b64(csv_data)})
        self.assertEqual((status, prev["rows"]), (200, 2))
        status, res, _ = self.call("POST", "/api/import/commit", {"filename": "a.csv", "content_base64": b64(csv_data),
                                                                  "mapping": prev["mapping"]})
        self.assertEqual((status, res["committed"], res["error_count"]), (422, False, 1))
        status, res, _ = self.call("POST", "/api/import/commit", {"filename": "a.csv", "content_base64": b64(csv_data),
                                                                  "mapping": prev["mapping"], "skip_invalid": True})
        self.assertEqual((status, res["created"]), (201, 1))
        status, body, h = self.call("GET", "/api/export.csv")
        self.assertEqual(status, 200)
        self.assertIn("attachment", h["content-disposition"])
        text = body.decode("utf-8-sig")
        self.assertTrue(text.startswith("id;name;category;cost"))
        self.assertIn(";Slack;Komunikacija;43.75;EUR;", text)
        self.assertEqual(self.call("POST", "/api/import/preview", {"filename": "a.csv", "content_base64": "%%%"})[0], 422)

    def test_bank_import_and_resolve(self):
        self.call("POST", "/api/licenses", license_data(name="Slack Pro", cost="43.75", start_date="2025-03-01"))
        status, stats, _ = self.call("POST", "/api/bank/import", {"filename": "izvod.xml", "content_base64": b64(CAMT)})
        self.assertEqual((status, stats["matched"]), (201, 1))
        txs = self.call("GET", "/api/bank/transactions?status=unmatched")[1]["items"]
        miro = next(t for t in txs if t["counterparty"] == "MIRO")
        self.assertEqual(self.call("POST", f"/api/bank/transactions/{miro['id']}", {"action": "ignore"})[1]["status"], "ignored")
        self.assertEqual(self.call("POST", f"/api/bank/transactions/{miro['id']}", {"action": "ignore"}, user="bruno")[0], 404)
        insights = self.call("GET", "/api/bank/insights")[1]
        self.assertIn("summary", insights)

    def test_dashboard_analytics_rates_notifications(self):
        self.call("POST", "/api/licenses", license_data(name="Figma", cost="540", currency="USD", billing_cycle="yearly"))
        self.call("POST", "/api/licenses", license_data(name="Idle", status="inactive", start_date="2025-01-20"))
        d = self.call("GET", "/api/dashboard")[1]
        self.assertEqual(d["roi"]["missing_rates"], ["USD"])
        self.assertEqual(self.call("POST", "/api/rates/refresh")[0], 200)
        self.assertEqual(self.call("PUT", "/api/rates/BAM", {"per_eur": "1.95583"})[0], 200)
        d = self.call("GET", "/api/dashboard?days=10")[1]
        self.assertEqual((d["roi"]["missing_rates"], d["window_days"]), ([], 10))
        self.assertEqual(d["reference_total"]["monthly"], "51.67")    # 540/12/1.08 + 10
        self.assertEqual(len(self.call("GET", "/api/analytics")[1]["forecast"]), 12)
        from licence_app.maintenance import run_usage_and_notifications
        run_usage_and_notifications(self.app)
        n = self.call("GET", "/api/notifications")[1]
        self.assertEqual(n["unread"], 1)
        self.call("POST", "/api/notifications/read", {})
        self.assertEqual(self.call("GET", "/api/notifications")[1]["unread"], 0)

    def test_webhook_management(self):
        status, hook, _ = self.call("POST", "/api/webhooks", {"url": "https://example.com/in", "events": ["license.created"]})
        self.assertEqual(status, 201)
        self.assertNotIn("secret", self.call("GET", "/api/webhooks")[1]["items"][0])   # shown once only
        self.assertEqual(self.call("POST", "/api/webhooks", {"url": "https://127.0.0.1/x"})[0], 422)
        self.call("POST", "/api/licenses", BODY)
        self.assertEqual(self.call("POST", f"/api/webhooks/{hook['id']}/test")[0], 202)
        self.app.webhooks.deliver_due()
        deliveries = self.call("GET", f"/api/webhooks/{hook['id']}/deliveries")[1]["items"]
        self.assertEqual(sorted(d["event"] for d in deliveries), ["license.created", "ping"])
        self.assertEqual(self.call("DELETE", f"/api/webhooks/{hook['id']}")[0], 204)


class LifecycleIntegrationTest(unittest.TestCase):
    """Entry -> display -> usage -> detection -> bank -> delete, on a file DB with restarts."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.dir.name, "licence.db")
        self.app = make_app(self.db)
        org_with_admin(self.app)
        self.srv = Running(self.app)

    def tearDown(self):
        self.srv.stop()
        self.app.close()
        self.dir.cleanup()

    def restart(self):
        self.srv.stop()
        self.app.close()
        self.app = make_app(self.db)
        self.srv = Running(self.app)

    def test_lifecycle(self):
        call = self.srv.call
        status, created, _ = call("POST", "/api/licenses", {
            "name": "Šifre Tim", "category": "Sigurnost", "cost": "29,97", "currency": "eur",
            "billing_cycle": "quarterly", "start_date": "2025-02-20", "usage_key": "sifre"})
        self.assertEqual((status, created["monthly_cost"]), (201, "9.99"))
        lid = created["id"]
        self.assertEqual(call("GET", "/api/licenses?q=%C5%A1ifre")[1]["items"][0]["id"], lid)
        self.assertEqual(call("GET", "/api/dashboard")[1]["expiring"][0]["days"], 8)

        self.restart()
        call = self.srv.call
        self.assertEqual(call("GET", f"/api/licenses/{lid}")[1]["name"], "Šifre Tim")

        # nobody used it for 45 days -> automatically inactive -> savings on the dashboard
        self.app.db.execute("UPDATE licenses SET tracking_since = datetime('now', '-45 days')")
        from licence_app.maintenance import run_usage_and_notifications
        self.assertEqual(run_usage_and_notifications(self.app)["auto_inactive"], 1)
        d = call("GET", "/api/dashboard")[1]
        self.assertEqual([i["id"] for i in d["inactive"]["items"]], [lid])
        self.assertEqual(d["roi"]["monthly_loss"], "9.99")
        # someone logs in again -> active
        tok = call("POST", "/api/tokens", {"name": "SSO"})[1]["token"]
        call("POST", "/api/usage", {"events": [{"license": "sifre", "user": "ivo"}]}, auth=f"Bearer {tok}")
        self.assertEqual(call("GET", f"/api/licenses/{lid}")[1]["status"], "active")

        self.assertEqual(call("DELETE", f"/api/licenses/{lid}")[0], 204)
        self.restart()
        self.assertEqual(self.srv.call("GET", f"/api/licenses/{lid}")[0], 404)
        self.assertEqual(self.app.db.optimize()["quick_check"], "ok")

    def test_concurrent_writes(self):
        errors = []

        def worker(n):
            for i in range(8):
                status, _, _ = self.srv.call("POST", "/api/licenses", license_data(name=f"T{n}-{i}", cost="1"))
                if status != 201:
                    errors.append(status)

        threads = [threading.Thread(target=worker, args=(n,)) for n in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        self.assertEqual(self.srv.call("GET", "/api/dashboard")[1]["totals"][0]["monthly"], "48.00")


if __name__ == "__main__":
    unittest.main()
