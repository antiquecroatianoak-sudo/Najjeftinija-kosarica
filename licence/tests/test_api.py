import http.client
import json
import threading
import unittest
from datetime import date
from pathlib import Path

from licence_app.api import create_server
from licence_app.repository import InMemoryLicenseRepository
from licence_app.service import LicenseService

WEB = Path(__file__).resolve().parent.parent / "web"
BODY = {"name": "Notion", "category": "Produktivnost", "cost": "96", "currency": "EUR",
        "billing_cycle": "yearly", "start_date": "2024-11-25"}


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        service = LicenseService(InMemoryLicenseRepository(), today=lambda: date(2026, 11, 12))
        cls.server = create_server(service, port=0, static_dir=WEB, verbose=False)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def call(self, method, path, body=None, raw=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        hdrs = {"Content-Type": "application/json"} if data else {}
        hdrs.update(headers or {})
        conn.request(method, path, body=data, headers=hdrs)
        res = conn.getresponse()
        payload = res.read()
        conn.close()
        ctype = res.getheader("Content-Type") or ""
        return res.status, (json.loads(payload) if "json" in ctype else payload)

    def test_full_crud_flow(self):
        status, created = self.call("POST", "/api/licenses", BODY)
        self.assertEqual(status, 201)
        self.assertEqual((created["status"], created["monthly_cost"]), ("active", "8.00"))
        lid = created["id"]

        self.assertEqual(self.call("GET", f"/api/licenses/{lid}"), (200, created))
        status, items = self.call("GET", "/api/licenses?q=notion")
        self.assertIn(lid, [i["id"] for i in items["items"]])

        status, patched = self.call("PATCH", f"/api/licenses/{lid}", {"status": "inactive"})
        self.assertEqual((status, patched["status"]), (200, "inactive"))
        status, dash = self.call("GET", "/api/dashboard")
        self.assertIn(lid, [i["id"] for i in dash["inactive"]["items"]])

        status, put = self.call("PUT", f"/api/licenses/{lid}", {**BODY, "cost": "120"})
        self.assertEqual((status, put["monthly_cost"], put["status"]), (200, "10.00", "active"))

        self.assertEqual(self.call("DELETE", f"/api/licenses/{lid}")[0], 204)
        self.assertEqual(self.call("GET", f"/api/licenses/{lid}")[0], 404)
        self.assertEqual(self.call("DELETE", f"/api/licenses/{lid}")[0], 404)

    def test_validation_error_shape(self):
        status, body = self.call("POST", "/api/licenses", {**BODY, "cost": "-3", "currency": "x"})
        self.assertEqual(status, 422)
        self.assertEqual(body["error"]["code"], "validation_error")
        self.assertEqual(set(body["error"]["fields"]), {"cost", "currency"})

    def test_put_requires_all_fields(self):
        _, created = self.call("POST", "/api/licenses", BODY)
        status, body = self.call("PUT", f"/api/licenses/{created['id']}", {"name": "X"})
        self.assertEqual(status, 422)
        self.assertIn("cost", body["error"]["fields"])

    def test_bad_requests(self):
        self.assertEqual(self.call("POST", "/api/licenses", raw=b"{nope")[0], 400)
        self.assertEqual(self.call("POST", "/api/licenses", raw=b"[]")[0], 422)
        self.assertEqual(self.call("POST", "/api/licenses")[0], 400)
        self.assertEqual(self.call("POST", "/api/licenses", raw=b"x=1",
                                   headers={"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.call("POST", "/api/licenses", raw=b"x" * (65 * 1024))[0], 413)
        self.assertEqual(self.call("DELETE", "/api/licenses")[0], 405)
        self.assertEqual(self.call("GET", "/api/nope")[0], 404)
        self.assertEqual(self.call("GET", "/api/licenses/not-an-id")[0], 404)
        self.assertEqual(self.call("GET", "/api/licenses?status=weird")[0], 422)

    def test_meta_and_health(self):
        self.assertEqual(self.call("GET", "/api/health"), (200, {"status": "ok"}))
        status, meta = self.call("GET", "/api/meta")
        self.assertEqual(meta["billing_cycles"], ["monthly", "quarterly", "yearly"])

    def test_static_files_and_traversal(self):
        status, body = self.call("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"Licence tima", body)
        self.assertEqual(self.call("GET", "/js/main.js")[0], 200)
        self.assertEqual(self.call("GET", "/../licence_app/models.py")[0], 404)
        self.assertEqual(self.call("GET", "/%2e%2e/licence_app/models.py")[0], 404)


if __name__ == "__main__":
    unittest.main()
