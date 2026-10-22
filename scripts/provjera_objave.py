"""
Zaštita objave: novi cjenik smije zamijeniti objavljeni samo ako nije stariji i nije bitno slabiji.

Uspoređuje novi site/data/pokrivenost.json s trenutačno objavljenim (GitHub Pages). Objava se zaustavlja (izlazni kod 1:
posao pada prije objave, javna aplikacija ostaje na posljednjem objavljenom cjeniku) kad:
  - objavljeni podaci nisu dostupni za usporedbu (mrežni kvar ne smije oslabiti zaštitu); jedina iznimka je izričit
    ručni način OBJAVA_BEZ_USPOREDBE=1 (npr. prva objava), uz uvjet da novi ima potvrđenih ponuda;
  - novi nema nijednu ponudu potvrđenu službenim cjenikom, a objavljeni ih ima;
  - novi je za raniji dan od objavljenoga, osim uskog oporavka (dolje);
  - novi ima manje od polovice potvrđenih ponuda objavljenoga (zaštita od pada obuhvata, ne dokaz točnosti cijena).

Uski oporavak preranog cjenika: lanci objavljuju do 8:00, pa je očekivani službeni dan prije 8:00 (Europe/Zagreb)
jučerašnji, a od 8:00 današnji. Ako objavljeni cjenik nosi dan KASNIJI od očekivanog (uvezen prerano, prije nego su
lanci objavili), novi smije zamijeniti objavljeni samo ako nosi točno očekivani dan i ima VIŠE potvrđenih ponuda.
Svaki drugi stariji dan ostaje odbijen; datumi se ne prepisuju.

Pokretanje:  python scripts/provjera_objave.py
"""

import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

OBJAVLJENO = "https://antiquecroatianoak-sudo.github.io/Najjeftinija-kosarica/data/pokrivenost.json"
NOVO = Path(__file__).resolve().parent.parent / "site" / "data" / "pokrivenost.json"
NAJMANJI_UDIO = 0.5
SAT_OBJAVE = 8  # lanci objavljuju dnevne cjenike do 8:00


def ocekivani_dan(sada: datetime) -> str:
    """Službeni dan koji bi u tom trenutku trebao biti dostupan (Europe/Zagreb)."""
    sada = sada.astimezone(ZoneInfo("Europe/Zagreb"))
    return (sada.date() - timedelta(days=1) if sada.hour < SAT_OBJAVE else sada.date()).isoformat()


def odluka(objavljeno: dict | None, novo: dict, sada: datetime, bez_usporedbe: bool = False) -> tuple[bool, str]:
    """(smije li se objaviti, obrazloženje)."""
    n_prov, n_dat = int(novo.get("provjereno_prema_sluzbenom_izvoru") or 0), str(novo.get("datum") or "")
    opis = f"novi cjenik {n_dat}: {n_prov} potvrđenih od {novo.get('ukupno_ponuda', 0)} ponuda"
    if not objavljeno:
        if not bez_usporedbe:
            return False, opis + "; objavljeni cjenik nije dostupan za usporedbu (zaštita se ne slabi zbog kvara)"
        return (n_prov > 0, opis + "; ručno: objava bez usporedbe" + ("" if n_prov > 0 else ", ali nema potvrđenih ponuda"))
    s_prov, s_dat = int(objavljeno.get("provjereno_prema_sluzbenom_izvoru") or 0), str(objavljeno.get("datum") or "")
    ocekivan = ocekivani_dan(sada)
    opis += f"; objavljeni {s_dat}: {s_prov} potvrđenih; očekivani službeni dan {ocekivan}"
    if n_dat and s_dat and n_dat < s_dat:
        if s_dat > ocekivan and n_dat == ocekivan and n_prov > s_prov:
            return True, opis + "; oporavak preranog cjenika (objavljeni nosi dan kasniji od očekivanog, novi očekivani dan s više potvrđenih)"
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
    smije, razlog = odluka(objavljeno, novo, datetime.now(ZoneInfo("Europe/Zagreb")),
                           os.environ.get("OBJAVA_BEZ_USPOREDBE") == "1")
    print(("Objava dopuštena: " if smije else "OBJAVA ZAUSTAVLJENA (ostaje posljednji objavljeni cjenik): ") + razlog)
    sys.exit(0 if smije else 1)


if __name__ == "__main__":
    main()
