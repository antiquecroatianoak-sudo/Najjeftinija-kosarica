"""
Zaštita objave: novi cjenik smije zamijeniti objavljeni samo ako nije stariji i nije bitno slabiji.

Uspoređuje novi site/data/pokrivenost.json s trenutačno objavljenim (GitHub Pages). Objava se zaustavlja (izlazni kod 1,
posao pada prije objave, pa javna aplikacija ostaje na posljednjem valjanom cjeniku) kad:
  - novi cjenik nema nijednu ponudu potvrđenu službenim cjenikom, a objavljeni ih ima;
  - novi cjenik je za raniji dan od objavljenoga;
  - novi ima manje od polovice potvrđenih ponuda objavljenoga (npr. mrežni kvar ili cjenici još nisu objavljeni).
Ako objavljeni podaci nisu dostupni (prva objava, mreža), traži se samo da novi ima potvrđenih ponuda.

Pokretanje:  python scripts/provjera_objave.py
"""

import json
import sys
import urllib.request
from pathlib import Path

OBJAVLJENO = "https://antiquecroatianoak-sudo.github.io/Najjeftinija-kosarica/data/pokrivenost.json"
NOVO = Path(__file__).resolve().parent.parent / "site" / "data" / "pokrivenost.json"
NAJMANJI_UDIO = 0.5


def odluka(objavljeno: dict | None, novo: dict) -> tuple[bool, str]:
    """(smije li se objaviti, obrazloženje)."""
    n_prov, n_dat = int(novo.get("provjereno_prema_sluzbenom_izvoru") or 0), str(novo.get("datum") or "")
    opis = f"novi cjenik {n_dat}: {n_prov} potvrđenih od {novo.get('ukupno_ponuda', 0)} ponuda"
    if not objavljeno:
        return (n_prov > 0, opis + ("" if n_prov > 0 else "; nema potvrđenih ponuda, a objavljeni podaci nisu dostupni za usporedbu"))
    s_prov, s_dat = int(objavljeno.get("provjereno_prema_sluzbenom_izvoru") or 0), str(objavljeno.get("datum") or "")
    opis += f"; objavljeni {s_dat}: {s_prov} potvrđenih"
    if n_dat and s_dat and n_dat < s_dat:
        return False, opis + "; novi je za raniji dan"
    if s_prov > 0 and n_prov == 0:
        return False, opis + "; novi nema nijednu potvrđenu ponudu"
    if s_prov > 0 and n_prov < NAJMANJI_UDIO * s_prov:
        return False, opis + f"; manje od {int(NAJMANJI_UDIO * 100)} % potvrđenih ponuda objavljenoga"
    return True, opis


def main():
    novo = json.loads(NOVO.read_text(encoding="utf-8"))
    try:
        with urllib.request.urlopen(urllib.request.Request(OBJAVLJENO, headers={"Cache-Control": "no-cache"}), timeout=60) as r:
            objavljeno = json.loads(r.read())
    except Exception as e:  # noqa: BLE001
        print(f"Objavljeni cjenik nije dostupan za usporedbu: {str(e)[:160]}")
        objavljeno = None
    smije, razlog = odluka(objavljeno, novo)
    print(("Objava dopuštena: " if smije else "OBJAVA ZAUSTAVLJENA (ostaje posljednji objavljeni cjenik): ") + razlog)
    sys.exit(0 if smije else 1)


if __name__ == "__main__":
    main()
