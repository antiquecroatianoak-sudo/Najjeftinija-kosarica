"""Import (CSV, XLSX) with field mapping, and CSV export.

Flow: preview(file) -> headers, sample rows, suggested mapping;
commit(file, mapping, defaults) -> validates every row first; by default
nothing is imported if any row is invalid (all-or-nothing), optionally
invalid rows are skipped. Duplicates (same name, case-insensitive) can be
skipped. Everything runs in one transaction.

XLSX is read with the standard library (zip + XML): first worksheet, shared
strings, inline strings and numbers; date cells (Excel serial numbers) in the
start_date column are converted.
"""
from __future__ import annotations

import csv
import io
import re
import unicodedata
import zipfile
from datetime import date, datetime, timedelta
from typing import Any

from .models import License, ValidationError, money_str
from .service import LicenseService
from .xmlsafe import UnsafeXML, fromstring, local

MAX_FILE = 5 * 1024 * 1024
MAX_ROWS = 5000
MAX_UNZIPPED = 60 * 1024 * 1024

FIELDS = ("name", "category", "cost", "currency", "billing_cycle", "start_date", "status", "usage_key")
REQUIRED = ("name", "category", "cost", "currency", "billing_cycle", "start_date")

_SYNONYMS = {
    "name": ["naziv", "name", "ime", "aplikacija", "application", "app", "software", "softver", "product", "proizvod", "licenca", "license", "pretplata", "subscription", "tool", "alat", "vendor"],
    "category": ["kategorija", "category", "vrsta", "type", "grupa", "group", "department", "odjel"],
    "cost": ["trosak", "cijena", "iznos", "cost", "price", "amount", "fee", "naknada", "trosak po ciklusu"],
    "currency": ["valuta", "currency", "cur", "ccy"],
    "billing_cycle": ["ciklus", "ciklus naplate", "naplata", "billing", "billing cycle", "period", "frequency", "interval", "plan"],
    "start_date": ["datum pocetka", "pocetak", "datum", "start", "start date", "started", "since", "od", "date", "renewal start"],
    "status": ["status", "stanje", "state", "aktivna", "active"],
    "usage_key": ["usage key", "kljuc koristenja", "sso", "sso key", "app id", "kljuc"],
}

_CYCLES = {
    "monthly": ["monthly", "month", "mjesecno", "mjesecna", "mjesec", "mj", "mj.", "m", "mo", "1m"],
    "quarterly": ["quarterly", "quarter", "tromjesecno", "tromjesecna", "kvartalno", "kvartal", "q", "3m"],
    "yearly": ["yearly", "annual", "annually", "year", "godisnje", "godisnja", "godina", "god", "y", "yr", "12m"],
}
_STATUSES = {
    "active": ["active", "aktivna", "aktivno", "aktivan", "da", "yes", "y", "1", "true", "u upotrebi"],
    "inactive": ["inactive", "neaktivna", "neaktivno", "neaktivan", "unused", "ne koristi se", "idle"],
    "cancelled": ["cancelled", "canceled", "otkazana", "otkazano", "otkazan", "ne", "no", "0", "false", "ended", "istekla"],
}


def fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _lookup(table: dict[str, list[str]], value: str) -> str | None:
    key = fold(value)
    for target, words in table.items():
        if key in (fold(w) for w in words):
            return target
    return None


# --- reading files ------------------------------------------------------------

def read_table(filename: str, content: bytes) -> tuple[str, list[str], list[list[Any]]]:
    if len(content) > MAX_FILE:
        raise ValidationError({"file": "Datoteka je veća od 5 MB."})
    name = (filename or "").lower()
    if name.endswith(".xlsx") or content[:2] == b"PK":
        headers, rows = _read_xlsx(content)
        fmt = "xlsx"
    elif name.endswith((".csv", ".txt")) or not name:
        headers, rows = _read_csv(content)
        fmt = "csv"
    else:
        raise ValidationError({"file": "Podržani formati: CSV i XLSX (Excel). Stari .xls spremite kao .xlsx."})
    if not headers:
        raise ValidationError({"file": "Datoteka nema zaglavlje ili je prazna."})
    if len(rows) > MAX_ROWS:
        raise ValidationError({"file": f"Najviše {MAX_ROWS} redaka po uvozu."})
    return fmt, headers, rows


def _decode(content: bytes) -> str:
    for enc in ("utf-8-sig", "cp1250"):   # cp1250: Croatian Excel CSV exports
        try:
            return content.decode(enc)
        except UnicodeDecodeError:
            continue
    return content.decode("latin-1")


def _read_csv(content: bytes) -> tuple[list[str], list[list[Any]]]:
    text = _decode(content)
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
    except csv.Error:
        class dialect(csv.excel):  # local subclass: never mutate csv.excel itself
            delimiter = ";" if sample.count(";") > sample.count(",") else ","
    reader = csv.reader(io.StringIO(text), dialect)
    rows = [r for r in reader if any(c.strip() for c in r)]
    if not rows:
        return [], []
    return [h.strip() for h in rows[0]], rows[1:]


def _col_index(ref: str) -> int:
    letters = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1


def _read_xlsx(content: bytes) -> tuple[list[str], list[list[Any]]]:
    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        raise ValidationError({"file": "Neispravna XLSX datoteka."}) from None
    if sum(i.file_size for i in zf.infolist()) > MAX_UNZIPPED:
        raise ValidationError({"file": "XLSX je prevelik nakon raspakiranja."})
    names = set(zf.namelist())
    try:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in names:
            for si in fromstring(zf.read("xl/sharedStrings.xml")):
                shared.append("".join(t.text or "" for t in si.iter() if local(t.tag) == "t"))
        sheet = _first_sheet(zf, names)
        root = fromstring(zf.read(sheet))
    except (UnsafeXML, KeyError) as e:
        raise ValidationError({"file": f"Neispravan XLSX: {e}"}) from None

    table: list[list[Any]] = []
    for row in (el for el in root.iter() if local(el.tag) == "row"):
        cells: dict[int, Any] = {}
        for c in row:
            if local(c.tag) != "c" or "r" not in c.attrib:
                continue
            kind = c.attrib.get("t")
            v = next((x.text for x in c if local(x.tag) == "v"), None)
            if kind == "s" and v is not None:
                value: Any = shared[int(v)] if int(v) < len(shared) else ""
            elif kind == "inlineStr":
                value = "".join(t.text or "" for t in c.iter() if local(t.tag) == "t")
            elif kind in ("str", "b", "e"):
                value = v or ""
            elif v is not None:
                value = float(v) if re.search(r"[.eE]", v) else int(v)
            else:
                value = ""
            cells[_col_index(c.attrib["r"])] = value
        if cells:
            width = max(cells) + 1
            table.append([cells.get(i, "") for i in range(width)])
    table = [r for r in table if any(str(c).strip() for c in r)]
    if not table:
        return [], []
    return [str(h).strip() for h in table[0]], table[1:]


def _first_sheet(zf: zipfile.ZipFile, names: set[str]) -> str:
    if "xl/workbook.xml" in names and "xl/_rels/workbook.xml.rels" in names:
        wb = fromstring(zf.read("xl/workbook.xml"))
        first = next((s for s in wb.iter() if local(s.tag) == "sheet"), None)
        if first is not None:
            rid = next((v for k, v in first.attrib.items() if local(k) == "id"), None)
            rels = fromstring(zf.read("xl/_rels/workbook.xml.rels"))
            for rel in rels:
                if rel.attrib.get("Id") == rid:
                    target = rel.attrib["Target"].lstrip("/")
                    return target if target.startswith("xl/") else f"xl/{target}"
    sheets = sorted(n for n in names if re.match(r"xl/worksheets/sheet\d+\.xml$", n))
    if not sheets:
        raise KeyError("nema radnog lista")
    return sheets[0]


# --- mapping & normalisation ----------------------------------------------------

def suggest_mapping(headers: list[str]) -> dict[str, int | None]:
    folded = [fold(h) for h in headers]
    mapping: dict[str, int | None] = {}
    used: set[int] = set()
    for field in FIELDS:
        choice = None
        for syn in (fold(s) for s in _SYNONYMS[field]):
            for i, h in enumerate(folded):
                if i not in used and (h == syn or (len(syn) > 3 and syn in h)):
                    choice = i
                    break
            if choice is not None:
                break
        mapping[field] = choice
        if choice is not None:
            used.add(choice)
    return mapping


def _excel_date(serial: float) -> date:
    return date(1899, 12, 30) + timedelta(days=int(serial))


def norm_date(value: Any) -> str:
    if isinstance(value, (int, float)) and 20000 < value < 80000:
        return _excel_date(value).isoformat()
    text = str(value).strip().rstrip(".")
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d. %m. %Y", "%d.%m.%y", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    if re.fullmatch(r"\d{5}(\.0+)?", text):
        return _excel_date(float(text)).isoformat()
    return text  # model validation reports it


_CURRENCY_MARKS = re.compile(r"(?i)\s|€|\$|£|\b(eur|usd|gbp|chf|hrk|kn)\b")


def norm_cost(value: Any) -> str:
    """'1.234,50 €' -> '1234.50'. Anything that is not a plain amount is returned
    unchanged so model validation rejects it (never extract digits from '=1+1')."""
    if isinstance(value, (int, float)):
        return str(round(value, 2))
    raw = str(value).strip()
    text = _CURRENCY_MARKS.sub("", raw)
    if not re.fullmatch(r"-?\d[\d.,]*", text):   # sign kept: bank statements use negative amounts
        return raw
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".") if text.rfind(",") > text.rfind(".") else text.replace(",", "")
    else:
        text = text.replace(",", ".")
    return text


def _cell(row: list[Any], idx: int | None) -> Any:
    if idx is None or idx >= len(row):
        return ""
    return row[idx]


def normalise_row(row: list[Any], mapping: dict[str, int | None], defaults: dict[str, str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for field in FIELDS:
        raw = _cell(row, mapping.get(field))
        if raw in ("", None):
            raw = defaults.get(field, "")
        if raw in ("", None):
            continue
        if field == "start_date":
            out[field] = norm_date(raw)
        elif field == "cost":
            out[field] = norm_cost(raw)
        elif field == "billing_cycle":
            out[field] = _lookup(_CYCLES, raw) or str(raw)
        elif field == "status":
            out[field] = _lookup(_STATUSES, raw) or str(raw)
        elif field == "currency":
            sym = {"€": "EUR", "$": "USD", "£": "GBP", "kn": "HRK"}.get(str(raw).strip().lower(), str(raw).strip())
            out[field] = sym.upper()
        else:
            out[field] = str(raw).strip()
    return out


def preview(filename: str, content: bytes) -> dict[str, Any]:
    fmt, headers, rows = read_table(filename, content)
    return {"format": fmt, "headers": headers, "rows": len(rows),
            "sample": [[str(c) for c in r] for r in rows[:8]],
            "mapping": suggest_mapping(headers), "fields": list(FIELDS), "required": list(REQUIRED)}


def _parse_mapping(raw: Any, width: int) -> dict[str, int | None]:
    if not isinstance(raw, dict):
        raise ValidationError({"mapping": "Mapiranje mora biti objekt polje -> stupac."})
    mapping: dict[str, int | None] = {}
    for field in FIELDS:
        idx = raw.get(field)
        if idx in (None, "", -1):
            mapping[field] = None
        elif isinstance(idx, int) and not isinstance(idx, bool) and 0 <= idx < width:
            mapping[field] = idx
        else:
            raise ValidationError({"mapping": f"Neispravan stupac za {field}."})
    return mapping


def commit(service: LicenseService, filename: str, content: bytes, mapping_raw: Any,
           defaults_raw: Any = None, *, skip_invalid: bool = False, skip_duplicates: bool = True) -> dict[str, Any]:
    _, headers, rows = read_table(filename, content)
    mapping = _parse_mapping(mapping_raw, len(headers))
    defaults = {k: str(v) for k, v in (defaults_raw or {}).items() if k in FIELDS and v not in (None, "")}
    missing = [f for f in REQUIRED if mapping[f] is None and f not in defaults]
    if missing:
        raise ValidationError({"mapping": f"Povežite stupac ili zadajte vrijednost za: {', '.join(missing)}."})

    existing = {l.name.casefold() for l in service.repo.find()}
    valid, errors, duplicates = [], [], 0
    for line, row in enumerate(rows, start=2):  # line 1 = header
        data = normalise_row(row, mapping, defaults)
        if skip_duplicates and data.get("name", "").casefold() in existing:
            duplicates += 1
            continue
        try:
            License.create(data)   # validate only
        except ValidationError as e:
            errors.append({"line": line, "errors": e.errors})
            continue
        existing.add(data["name"].casefold())
        valid.append(data)
    if errors and not skip_invalid:
        return {"created": 0, "skipped_duplicates": duplicates, "errors": errors[:200],
                "error_count": len(errors), "committed": False}
    with service.repo.db.transaction():
        for data in valid:
            service.create(data)
    return {"created": len(valid), "skipped_duplicates": duplicates, "errors": errors[:200],
            "error_count": len(errors), "committed": True}


# --- export ---------------------------------------------------------------------

EXPORT_COLUMNS = ("id", "name", "category", "cost", "currency", "billing_cycle", "start_date", "status",
                  "monthly_cost", "monthly_ref", "next_renewal", "usage_key", "auto_status", "last_used_at",
                  "active_users_30d")


def _safe_cell(value: Any) -> str:
    """Neutralise spreadsheet formulas (CSV injection)."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def export_csv(rows: list[dict[str, Any]]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    writer.writerow(EXPORT_COLUMNS)
    for r in rows:
        writer.writerow([_safe_cell(r.get(c)) for c in EXPORT_COLUMNS])
    return ("﻿" + buf.getvalue()).encode("utf-8")   # BOM: Excel opens UTF-8 correctly
