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
