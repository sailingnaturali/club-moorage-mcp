"""Radius filtering for outstations, reusing pilotbook's great-circle distance."""

from __future__ import annotations

from pilotbook_mcp.geo import haversine_nm

from club_moorage_mcp.models import Moorage


def within_radius(
    outstations: list[Moorage], lat: float, lon: float, radius_nm: float
) -> list[tuple[Moorage, float]]:
    """Moorages within radius_nm of (lat, lon), sorted nearest-first."""
    out: list[tuple[Moorage, float]] = []
    for o in outstations:
        if o.lat is None or o.lon is None:
            continue
        d = haversine_nm(lat, lon, o.lat, o.lon)
        if d <= radius_nm:
            out.append((o, d))
    out.sort(key=lambda pair: pair[1])
    return out
