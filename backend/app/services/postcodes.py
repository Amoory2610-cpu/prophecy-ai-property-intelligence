"""UK postcode normalisation and area derivation."""

from __future__ import annotations

import re

_POSTCODE_RE = re.compile(r"^([A-Z]{1,2}[0-9][A-Z0-9]?)\s*([0-9][A-Z]{2})$")
_OUTWARD_RE = re.compile(r"^[A-Z]{1,2}[0-9][A-Z0-9]?$")
_SECTOR_RE = re.compile(r"^([A-Z]{1,2}[0-9][A-Z0-9]?)\s*([0-9])$")


def normalise(postcode: str | None) -> str | None:
    """Return ``"SW1A 1AA"`` style postcodes, or ``None`` if blank or not a UK format."""
    if postcode is None:
        return None
    compact = re.sub(r"\s+", "", postcode.upper())
    if not compact:
        return None
    m = _POSTCODE_RE.match(compact)
    return f"{m.group(1)} {m.group(2)}" if m else None


def district(postcode: str | None) -> str | None:
    """Outward code, e.g. ``"M14"`` from ``"M14 5RG"``."""
    pc = normalise(postcode)
    return pc.split(" ")[0] if pc else None


def sector(postcode: str | None) -> str | None:
    """Postcode sector, e.g. ``"M14 5"`` from ``"M14 5RG"``."""
    pc = normalise(postcode)
    return pc[:-2] if pc else None


def parse_area(query: str) -> tuple[str, str] | None:
    """Classify a user's area query as a postcode ``sector`` or ``district``.

    Returns ``(kind, value)`` or ``None`` when it is not a postcode area (it is then
    treated as a local authority or town name by the caller).
    """
    q = re.sub(r"\s+", " ", query.strip().upper())
    if not q:
        return None
    full = normalise(q)
    if full:
        return "sector", full[:-2]
    m = _SECTOR_RE.match(q)
    if m:
        return "sector", f"{m.group(1)} {m.group(2)}"
    if _OUTWARD_RE.match(q):
        return "district", q
    return None
