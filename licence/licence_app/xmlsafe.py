"""Parsing XML from outside (ECB feed, bank statements, XLSX parts).

DTDs are refused outright: no entity expansion ("billion laughs") and no
external entities. Input size is capped by the callers.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET


class UnsafeXML(ValueError):
    pass


def fromstring(data: bytes, max_bytes: int = 20 * 1024 * 1024) -> ET.Element:
    if len(data) > max_bytes:
        raise UnsafeXML("XML je prevelik.")
    head = data[:4096].upper()
    if b"<!DOCTYPE" in head or b"<!ENTITY" in data.upper():
        raise UnsafeXML("XML s DTD/ENTITY deklaracijama nije dopušten.")
    try:
        return ET.fromstring(data)
    except ET.ParseError as e:
        raise UnsafeXML(f"Neispravan XML: {e}") from None


def local(tag: str) -> str:
    """Tag name without namespace."""
    return tag.rsplit("}", 1)[-1]
