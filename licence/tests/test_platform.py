import base64
import hashlib
import hmac
import io
import json
import os
import tempfile
import threading
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from helpers import ECB_XML, FakeSender, fake_resolve, license_data as lic, make_app, org_with_admin
from licence_app.banking.feeds import parse_camt053, parse_csv
from licence_app.config import ConfigError, load_settings
from licence_app.maintenance import Scheduler, backup, run_database, run_usage_and_notifications
from licence_app.models import LicenseStatus, ValidationError
from licence_app.rates import parse_ecb
from licence_app.security import (LoginLimiter, Tokenizer, hash_password, mask_sensitive, parse_basic,
                                  verify_password)
from licence_app.transfer import commit, export_csv, preview
from licence_app.usage import notify_expiring
from licence_app.webhooks import RETRY_SCHEDULE, WebhookService, post, sign, validate_url
from licence_app.xmlsafe import UnsafeXML, fromstring


class Base(unittest.TestCase):
    def setUp(self):
        self.sender = FakeSender()
        self.app = make_app(sender=self.sender)
        self.org, _ = org_with_admin(self.app)
        self.ws = self.app.workspace(self.org, "ana")

    def tearDown(self):
        self.app.close()


class UsageTest(Base):
    def test_ingest_tokenises_users_and_reports_unknown(self):
        slack = self.ws.licenses.create(lic(name="Slack", usage_key="slack"))
        res = self.ws.usage.ingest({"events": [
            {"license": "slack", "user": "Ana@Firma.hr"},
            {"license": slack.id, "user": "ivo@firma.hr", "at": "2026-11-10T08:00:00Z"},
            {"license": "nepoznato", "user": "x"},
            {"license": "slack"},
            {"license": "slack", "user": "a", "at": "2099-01-01T00:00:00Z"}]})
        self.assertEqual(res["accepted"], 2)
        self.assertEqual(res["unknown"], ["nepoznato"])
        self.assertEqual([e["index"] for e in res["errors"]], [3, 4])
        stored = [r["user_token"] for r in self.app.db.query("SELECT user_token FROM usage_events")]
        self.assertNotIn("ana@firma.hr", " ".join(stored))
        self.assertEqual(stored[0], Tokenizer("k" * 40).user("ana@firma.hr"))   # case-insensitive token
        view = self.ws.licenses.view([slack])[0]
        self.assertEqual(view["active_users_30d"], 2)
        for bad in ({}, {"events": []}, {"events": [{}] * 1001}):
            with self.assertRaises(ValidationError):
                self.ws.usage.ingest(bad)

    def test_automatic_status_both_directions(self):
        old = (datetime.now(timezone.utc) - timedelta(days=45)).strftime("%Y-%m-%d %H:%M:%S")
        slack = self.ws.licenses.create(lic(name="Slack", usage_key="slack"))
        manual = self.ws.licenses.create(lic(name="Manual", usage_key="manual", auto_status=False))
        untracked = self.ws.licenses.create(lic(name="Untracked"))
        self.app.db.execute("UPDATE licenses SET tracking_since = ?", (old,))
        changed = self.ws.usage.auto_inactivate()
        self.assertEqual(changed, [slack.id])                     # manual and untracked untouched
        self.assertIs(self.ws.licenses.get(slack.id).status, LicenseStatus.INACTIVE)
        self.assertIs(self.ws.licenses.get(manual.id).status, LicenseStatus.ACTIVE)
        self.assertIs(self.ws.licenses.get(untracked.id).status, LicenseStatus.ACTIVE)
        self.assertEqual(self.ws.usage.auto_inactivate(), [])     # idempotent
        notes = self.app.notifications.list(self.org.id)
        self.assertEqual(notes[0]["kind"], "license.auto_inactive")

        res = self.ws.usage.ingest({"events": [{"license": "slack", "user": "ana"}]})
        self.assertEqual(res["reactivated"], [slack.id])
        self.assertIs(self.ws.licenses.get(slack.id).status, LicenseStatus.ACTIVE)
        audit = [a["action"] for a in self.app.audit.recent(self.org.id)]
        self.assertIn("auto_inactivate", audit)
        self.assertIn("auto_reactivate", audit)

    def test_recent_use_keeps_license_active(self):
        slack = self.ws.licenses.create(lic(name="Slack", usage_key="slack"))
        old = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%d %H:%M:%S")
        self.app.db.execute("UPDATE licenses SET tracking_since = ?", (old,))
        self.ws.usage.ingest({"events": [{"license": "slack", "user": "ana",
                                          "at": (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()}]})
        self.assertEqual(self.ws.usage.auto_inactivate(), [])
        self.assertIs(self.ws.licenses.get(slack.id).status, LicenseStatus.ACTIVE)


class NotificationWebhookTest(Base):
    def test_expiring_notices_are_deduplicated_and_queue_webhooks(self):
        hook = self.app.webhooks.create(self.org.id, {"url": "https://example.com/hook",
                                                      "events": ["license.expiring"]})
        self.assertTrue(hook["secret"].startswith("whsec_"))
        self.ws.licenses.create(lic(name="Idle", status="inactive", start_date="2025-01-20"))   # 20.11.
        self.assertEqual(notify_expiring(self.ws.licenses), 1)
        self.assertEqual(notify_expiring(self.ws.licenses), 0)    # same renewal -> no repeat
        note = self.app.notifications.list(self.org.id)[0]["message"]
        self.assertIn("otkažite prije naplate", note)
        stats = self.app.webhooks.deliver_due()
        self.assertEqual(stats["sent"], 1)
        self.assertEqual(self.sender.calls[0]["event"], "license.expiring")
        self.assertEqual(self.sender.calls[0]["body"]["data"]["name"], "Idle")
        self.assertEqual(self.app.notifications.unread(self.org.id), 1)
        self.app.notifications.mark_read(self.org.id)
        self.assertEqual(self.app.notifications.unread(self.org.id), 0)

    def test_retries_then_fails(self):
        self.sender.status = 500
        self.app.webhooks.create(self.org.id, {"url": "https://example.com/h"})
        self.ws.licenses.create(lic())
        self.assertEqual(self.app.webhooks.deliver_due()["retry"], 1)
        for _ in RETRY_SCHEDULE:
            self.app.db.execute("UPDATE webhook_deliveries SET next_attempt_at = datetime('now', '-1 second')")
            self.app.webhooks.deliver_due()
        row = self.app.db.one("SELECT status, attempts, last_error FROM webhook_deliveries")
        self.assertEqual((row["status"], row["attempts"], row["last_error"]), ("failed", 6, "HTTP 500"))

    def test_url_validation_blocks_ssrf(self):
        for url in ("http://example.com/x", "https://127.0.0.1/x", "https://localhost/x", "https://10.0.0.5/",
                    "https://169.254.169.254/latest/meta-data", "https://user:pw@example.com/", "ftp://example.com"):
            with self.assertRaises(ValidationError, msg=url):
                validate_url(url, allow_private=False, resolve=fake_resolve)
        with self.assertRaises(ValidationError):
            self.app.webhooks.create(self.org.id, {"url": "https://example.com", "events": ["nope"]})

    def test_real_delivery_is_signed(self):
        received = {}

        class Receiver(BaseHTTPRequestHandler):
            def do_POST(self):
                received["body"] = self.rfile.read(int(self.headers["Content-Length"]))
                received["headers"] = dict(self.headers)
                self.send_response(204)
                self.end_headers()

            def log_message(self, *a):
                pass

        srv = HTTPServer(("127.0.0.1", 0), Receiver)
        threading.Thread(target=srv.handle_request, daemon=True).start()
        url = f"http://127.0.0.1:{srv.server_address[1]}/hook"
        with self.assertRaises(ValueError):                       # blocked unless explicitly allowed
            post(url, "s", "ping", "1", b"{}", allow_private=False)
        service = WebhookService(self.app.webhook_store, allow_private=True)   # real sender
        hook = service.create(self.org.id, {"url": url})
        self.app.webhook_store.enqueue(hook["id"], "ping", {"event": "ping"})
        self.assertEqual(service.deliver_due()["sent"], 1)
        srv.server_close()
        h = received["headers"]
        expected = sign(hook["secret"], h["X-LicensePulse-Timestamp"], received["body"])
        self.assertTrue(hmac.compare_digest(h["X-LicensePulse-Signature"], expected))
        self.assertEqual(h["X-LicensePulse-Event"], "ping")


class RatesTest(Base):
    def test_ecb_parse_refresh_manual_and_convert(self):
        day, rates = parse_ecb(ECB_XML)
        self.assertEqual((str(day), rates["USD"]), ("2026-11-11", Decimal("1.0800")))
        self.app.rates.refresh()
        conv = self.app.rates.convert(Decimal("108"), "USD", "EUR")
        self.assertEqual((conv.amount, conv.rate_date), (Decimal("100"), "2026-11-11"))
        self.assertAlmostEqual(float(self.app.rates.convert(Decimal("84"), "GBP", "USD").amount), 108.0)
        self.assertIsNone(self.app.rates.convert(Decimal(1), "XYZ", "EUR").amount)   # never guessed
        self.app.rates.set_manual("BAM", "1.95583")
        self.app.rates.set_manual("USD", "1.10")
        self.app.rates.refresh()                                  # the feed does not override a manual rate
        self.assertEqual(self.app.rates.table()["USD"]["per_eur"], Decimal("1.10"))
        for cur, val in (("EUR", "1"), ("US", "1"), ("CHF", "-2"), ("CHF", "abc")):
            with self.assertRaises(ValidationError):
                self.app.rates.set_manual(cur, val)

    def test_xml_with_dtd_is_refused(self):
        bomb = b'<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;">]><r>&b;</r>'
        with self.assertRaises(UnsafeXML):
            fromstring(bomb)
        with self.assertRaises(UnsafeXML):
            parse_ecb(bomb)


def make_xlsx(rows):
    """Minimal XLSX (shared strings + numbers) built with the standard library."""
    strings, index = [], {}
    def ref(c, r):
        return f"{chr(65 + c)}{r}"
    cells = []
    for r, row in enumerate(rows, start=1):
        xs = []
        for c, v in enumerate(row):
            if isinstance(v, (int, float)):
                xs.append(f'<c r="{ref(c, r)}"><v>{v}</v></c>')
            else:
                if v not in index:
                    index[v] = len(strings)
                    strings.append(v)
                xs.append(f'<c r="{ref(c, r)}" t="s"><v>{index[v]}</v></c>')
        cells.append(f'<row r="{r}">{"".join(xs)}</row>')
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/workbook.xml", f'<workbook {ns} xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Licence" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml" Type="x"/></Relationships>')
        z.writestr("xl/sharedStrings.xml", f'<sst {ns}>' + "".join(f"<si><t>{s}</t></si>" for s in strings) + "</sst>")
        z.writestr("xl/worksheets/sheet1.xml", f'<worksheet {ns}><sheetData>{"".join(cells)}</sheetData></worksheet>')
    return buf.getvalue()


class TransferTest(Base):
    CSV = ("Naziv;Kategorija;Cijena;Valuta;Naplata;Datum početka;Status\n"
           "Slack Pro;Komunikacija;43,75 €;EUR;Mjesečno;1.3.2025.;Aktivna\n"
           "Figma;Dizajn;1.234,50;usd;godišnje;15.01.2025;neaktivna\n"
           "Zoom;Komunikacija;41,97;EUR;kvartalno;2025-02-20;otkazana\n").encode("cp1250")

    def test_csv_preview_mapping_and_commit(self):
        p = preview("licence.csv", self.CSV)
        self.assertEqual(p["format"], "csv")
        self.assertEqual(p["rows"], 3)
        self.assertEqual(p["mapping"], {"name": 0, "category": 1, "cost": 2, "currency": 3, "billing_cycle": 4,
                                        "start_date": 5, "status": 6, "usage_key": None})
        res = commit(self.ws.licenses, "licence.csv", self.CSV, p["mapping"])
        self.assertEqual((res["created"], res["committed"]), (3, True))
        figma = next(l for l in self.ws.licenses.list() if l.name == "Figma")
        self.assertEqual((str(figma.cost), figma.currency, figma.billing_cycle.value, str(figma.start_date),
                          figma.status.value), ("1234.50", "USD", "yearly", "2025-01-15", "inactive"))
        again = commit(self.ws.licenses, "licence.csv", self.CSV, p["mapping"])
        self.assertEqual((again["created"], again["skipped_duplicates"]), (0, 3))

    def test_all_or_nothing_and_skip_invalid(self):
        bad = self.CSV + "Loše;X;abc;EUR;mjesečno;1.1.2025;aktivna\n".encode("cp1250")
        p = preview("x.csv", bad)
        res = commit(self.ws.licenses, "x.csv", bad, p["mapping"])
        self.assertEqual((res["committed"], res["created"], res["errors"][0]["line"]), (False, 0, 5))
        self.assertEqual(self.ws.licenses.list(), [])
        res = commit(self.ws.licenses, "x.csv", bad, p["mapping"], skip_invalid=True)
        self.assertEqual((res["committed"], res["created"], res["error_count"]), (True, 3, 1))

    def test_defaults_and_missing_mapping(self):
        data = "App,Price,Since\nJira,8.15,2025-04-01\n".encode()
        p = preview("x.csv", data)
        with self.assertRaises(ValidationError):
            commit(self.ws.licenses, "x.csv", data, p["mapping"])
        res = commit(self.ws.licenses, "x.csv", data, p["mapping"],
                     {"category": "Razvoj", "currency": "EUR", "billing_cycle": "monthly"})
        self.assertEqual(res["created"], 1)

    def test_xlsx_with_excel_dates(self):
        content = make_xlsx([["Name", "Category", "Cost", "Currency", "Billing", "Start date"],
                             ["Notion", "Produktivnost", 96, "EUR", "Annual", 45621],
                             ["GitHub", "Razvoj", 20.5, "USD", "monthly", "2024-09-10"]])
        p = preview("licence.xlsx", content)
        self.assertEqual((p["format"], p["rows"]), ("xlsx", 2))
        res = commit(self.ws.licenses, "licence.xlsx", content, p["mapping"])
        self.assertEqual(res["created"], 2)
        notion = next(l for l in self.ws.licenses.list() if l.name == "Notion")
        self.assertEqual((str(notion.start_date), notion.billing_cycle.value), ("2024-11-25", "yearly"))

    def test_cost_normalisation_rejects_garbage(self):
        from licence_app.transfer import norm_cost
        self.assertEqual(norm_cost("1.234,50 €"), "1234.50")
        self.assertEqual(norm_cost("EUR 9,99"), "9.99")
        self.assertEqual(norm_cost("$1,299.00"), "1299.00")
        self.assertEqual(norm_cost("-20,00"), "-20.00")
        for raw in ("=1+1", "12a", "1 2 3 x"):
            with self.assertRaises(ValidationError, msg=raw):
                from licence_app.models import License
                License.create(lic(cost=norm_cost(raw)))

    def test_bad_files(self):
        for name, data in (("x.xls", b"\xd0\xcf\x11\xe0"), ("x.xlsx", b"PK\x03\x04garbage"), ("x.csv", b"")):
            with self.assertRaises(ValidationError, msg=name):
                preview(name, data)

    def test_export_neutralises_formulas(self):
        self.ws.licenses.create(lic(name="=HYPERLINK(\"http://x\")", category="+cmd"))
        out = export_csv(self.ws.licenses.view(self.ws.licenses.list())).decode("utf-8-sig")
        self.assertIn("'=HYPERLINK", out)
        self.assertIn(";'+cmd;", out)


CAMT = """<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.02"><BkToCstmrStmt><Stmt>
 <Acct><Id><IBAN>HR1210010051863000160</IBAN></Id></Acct>
 <Ntry><Amt Ccy="EUR">43.75</Amt><CdtDbtInd>DBIT</CdtDbtInd><BookgDt><Dt>2026-10-01</Dt></BookgDt>
  <AcctSvcrRef>REF-1</AcctSvcrRef><NtryDtls><TxDtls><RltdPties><Cdtr><Nm>SLACK TECHNOLOGIES</Nm></Cdtr></RltdPties>
  <RmtInf><Ustrd>Slack Pro kartica 4111 1111 1111 1234</Ustrd></RmtInf></TxDtls></NtryDtls></Ntry>
 <Ntry><Amt Ccy="EUR">95.00</Amt><CdtDbtInd>DBIT</CdtDbtInd><BookgDt><Dt>2026-10-01</Dt></BookgDt>
  <AcctSvcrRef>REF-2</AcctSvcrRef><NtryDtls><TxDtls><RltdPties><Cdtr><Nm>ADOBE SYSTEMS</Nm></Cdtr></RltdPties></TxDtls></NtryDtls></Ntry>
 <Ntry><Amt Ccy="EUR">15.00</Amt><CdtDbtInd>DBIT</CdtDbtInd><BookgDt><Dt>2026-09-12</Dt></BookgDt>
  <AcctSvcrRef>REF-3</AcctSvcrRef><NtryDtls><TxDtls><RltdPties><Cdtr><Nm>MIRO</Nm></Cdtr></RltdPties></TxDtls></NtryDtls></Ntry>
 <Ntry><Amt Ccy="EUR">15.00</Amt><CdtDbtInd>DBIT</CdtDbtInd><BookgDt><Dt>2026-10-12</Dt></BookgDt>
  <AcctSvcrRef>REF-4</AcctSvcrRef><NtryDtls><TxDtls><RltdPties><Cdtr><Nm>MIRO</Nm></Cdtr></RltdPties></TxDtls></NtryDtls></Ntry>
 <Ntry><Amt Ccy="EUR">500.00</Amt><CdtDbtInd>CRDT</CdtDbtInd><BookgDt><Dt>2026-10-02</Dt></BookgDt>
  <AcctSvcrRef>REF-5</AcctSvcrRef></Ntry>
</Stmt></BkToCstmrStmt></Document>""".encode()


class BankingTest(Base):
    def test_camt_import_tokenises_masks_dedupes_and_matches(self):
        slack = self.ws.licenses.create(lic(name="Slack Pro", cost="43.75", start_date="2025-03-01"))
        adobe = self.ws.licenses.create(lic(name="Adobe Creative Cloud", cost="71.99", start_date="2024-06-01",
                                            category="Dizajn"))
        stats = self.ws.bank.import_statement("izvod.xml", CAMT, "Poslovni račun")
        self.assertEqual((stats["format"], stats["imported"], stats["matched"]), ("camt.053", 5, 1))
        self.assertEqual(stats["recurring_unknown"], 1)            # MIRO twice, not registered
        txs = {t["counterparty"]: t for t in self.ws.bank.transactions()}
        self.assertEqual((txs["SLACK TECHNOLOGIES"]["status"], txs["SLACK TECHNOLOGIES"]["license_id"]),
                         ("matched", slack.id))
        self.assertEqual(txs["ADOBE SYSTEMS"]["status"], "suggested")   # name + date fit, amount does not
        self.assertEqual(txs["ADOBE SYSTEMS"]["license_id"], adobe.id)
        dump = "\n".join(str(tuple(r)) for t in ("bank_accounts", "bank_transactions")
                         for r in self.app.db.query(f"SELECT * FROM {t}"))
        self.assertNotIn("HR1210010051863000160", dump)            # IBAN never stored
        self.assertNotIn("4111 1111 1111 1234", dump)              # card number masked
        self.assertIn("•••• 1234", dump)
        self.assertEqual(self.ws.bank.import_statement("izvod.xml", CAMT)["duplicates"], 5)

        self.ws.bank.resolve(txs["ADOBE SYSTEMS"]["id"], "match", adobe.id)
        drift = self.ws.bank.price_drift()
        self.assertEqual([(d["name"], d["paid"]) for d in drift], [("Adobe Creative Cloud", "95.00")])
        with self.assertRaises(ValidationError):
            self.ws.bank.resolve(txs["MIRO"]["id"], "explode")
        self.assertEqual(self.app.notifications.list(self.org.id)[0]["kind"], "bank.unmatched_recurring")

    def test_other_org_cannot_touch_transactions(self):
        self.ws.bank.import_statement("izvod.xml", CAMT)
        other, _ = org_with_admin(self.app, "beta", "bruno")
        other_ws = self.app.workspace(other)
        self.assertEqual(other_ws.bank.transactions(), [])
        tx = self.ws.bank.transactions()[0]
        from licence_app.service import NotFound
        with self.assertRaises(NotFound):
            other_ws.bank.resolve(tx["id"], "ignore")

    def test_csv_statement(self):
        data = ("Datum;Primatelj;Opis;Isplata;Uplata;Valuta\n"
                "01.10.2026;GitHub, Inc.;GITHUB TEAM;20,00;;USD\n"
                "02.10.2026;Kupac;Račun 12;;100,00;EUR\n"
                "Ukupno;;;20,00;100,00;\n").encode("cp1250")
        txs = parse_csv(data, "HR1210010051863000160")
        self.assertEqual([(str(t.amount), t.currency) for t in txs], [("-20.00", "USD"), ("100.00", "EUR")])

    def test_camt_requires_statement(self):
        with self.assertRaises(ValidationError):
            parse_camt053(b"<Document><Other/></Document>")


class SecurityTest(unittest.TestCase):
    def test_passwords(self):
        h = hash_password("tajna-lozinka-123", iterations=1000)
        self.assertTrue(verify_password("tajna-lozinka-123", h))
        self.assertFalse(verify_password("kriva", h))
        self.assertFalse(verify_password("x", "garbage"))
        self.assertNotIn("tajna", h)

    def test_limiter_backoff(self):
        lim = LoginLimiter(free=3, base_seconds=10)
        lim.failed("ip:1")
        lim.failed("ip:1")
        self.assertEqual(lim.retry_after("ip:1"), 0)
        lim.failed("ip:1")
        self.assertGreater(lim.retry_after("ip:1"), 9)
        lim.failed("ip:1")
        self.assertGreater(lim.retry_after("ip:1"), 19)       # doubles
        lim.succeeded("ip:1")
        self.assertEqual(lim.retry_after("ip:1"), 0)

    def test_basic_parsing_and_masking(self):
        self.assertEqual(parse_basic("Basic " + base64.b64encode(b"ana:a:b").decode()), ("ana", "a:b"))
        for bad in (None, "Bearer x", "Basic !!!", "Basic " + base64.b64encode(b"nocolon").decode()):
            self.assertIsNone(parse_basic(bad))
        self.assertEqual(mask_sensitive("Plaćeno karticom 4111-1111-1111-1234 ok"), "Plaćeno karticom •••• 1234 ok")
        self.assertEqual(mask_sensitive("Na HR12 1001 0051 8630 0016 0"), "Na IBAN •••• 0160")

    def test_production_config_requirements(self):
        with self.assertRaises(ConfigError):
            load_settings({"LICENCE_ENV": "production"})
        with self.assertRaises(ConfigError):
            load_settings({"LICENCE_ENV": "production", "LICENCE_SECRET_KEY": "x" * 40,
                           "LICENCE_WEBHOOK_ALLOW_PRIVATE": "1"})
        with self.assertRaises(ConfigError):
            load_settings({"LICENCE_ENV": "production", "LICENCE_SECRET_KEY": "x" * 40,
                           "LICENCE_ADMIN_PASSWORD": "short"})
        with self.assertRaises(ConfigError):
            load_settings({"LICENCE_PORT": "abc"})
        s = load_settings({"LICENCE_ENV": "production", "LICENCE_SECRET_KEY": "x" * 40, "LICENCE_HSTS": "1"})
        self.assertEqual((s.host, s.hsts), ("0.0.0.0", True))


class MaintenanceTest(Base):
    def test_tasks_run_and_failures_are_contained(self):
        self.ws.licenses.create(lic(name="Idle", status="inactive", start_date="2025-01-20"))
        stats = run_usage_and_notifications(self.app)
        self.assertEqual(stats["notices"], 1)
        db = run_database(self.app)
        self.assertEqual(db["quick_check"], "ok")
        scheduler = Scheduler(self.app, tasks=[("boom", 1, lambda a: 1 / 0), ("ok", 1, lambda a: {"n": 1})])
        scheduler.tick()
        self.assertFalse(scheduler.status["boom"]["ok"])
        self.assertTrue(scheduler.status["ok"]["ok"])

    def test_backup_and_rotation(self):
        with tempfile.TemporaryDirectory() as d:
            app = make_app(os.path.join(d, "live.db"))
            org_with_admin(app)
            for i in range(4):
                path = app.db.backup(Path(d, "b", f"licence-2026010{i}-000000.db"))
            newest = backup(app, Path(d, "b"), keep=2)
            files = sorted(p.name for p in Path(d, "b").glob("licence-*.db"))
            self.assertEqual(len(files), 2)
            self.assertIn(newest.name, files)
            import sqlite3
            self.assertEqual(sqlite3.connect(newest).execute("SELECT count(*) FROM users").fetchone()[0], 1)
            app.close()


if __name__ == "__main__":
    unittest.main()
