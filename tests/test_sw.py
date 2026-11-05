"""Service worker smije dirati samo vlastiti opseg i cacheove s prefiksom 'kosarica-'."""
import re
import unittest
from pathlib import Path

SW = (Path(__file__).resolve().parent.parent / "app" / "sw.js").read_text(encoding="utf-8")


class ServiceWorker(unittest.TestCase):
    def test_prefiks(self):
        self.assertIn("const PREFIKS = 'kosarica-';", SW)
        for ime in re.findall(r"const (?:APLIKACIJA|PODACI|POSLOVNICE) = `?'?([^;]+);", SW):
            self.assertIn("PREFIKS", ime)

    def test_brise_samo_svoje(self):
        self.assertIn("i.startsWith(PREFIKS) && !vazeci.has(i)", SW)
        self.assertNotIn("caches.keys()).map", SW)

    def test_samo_vlastiti_opseg(self):
        self.assertIn("if (!uOpsegu(url)) return;", SW)


if __name__ == "__main__":
    unittest.main()


class VerzijaAplikacije(unittest.TestCase):
    def test_verzija_u_aplikaciji_jednaka_verziji_service_workera(self):
        """Prikazana verzija mora biti ona koju service worker instalira – inače kupac ne zna koju verziju ima."""
        import re
        korijen = Path(__file__).resolve().parent.parent / "app"
        sw = re.search(r"const VERZIJA = '([^']+)'", (korijen / "sw.js").read_text()).group(1)
        app = re.search(r"VERZIJA_APLIKACIJE = '([^']+)'", (korijen / "js" / "greske.js").read_text()).group(1)
        self.assertEqual(sw, app)

    def test_nova_verzija_uzima_svjeze_datoteke(self):
        sw = (Path(__file__).resolve().parent.parent / "app" / "sw.js").read_text()
        self.assertIn("cache: 'reload'", sw)
