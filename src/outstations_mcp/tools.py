"""Pure-Python implementations of the MCP tools. No I/O beyond the Store."""

from __future__ import annotations

from outstations_mcp.geo import within_radius
from outstations_mcp.store import Store


def _matches_clubs(club: str, clubs: list[str] | None) -> bool:
    return clubs is None or club in clubs


def list_outstations(store: Store, clubs: list[str] | None = None) -> dict:
    return {
        "outstations": [
            {
                "name": o.name,
                "club": o.club,
                "region": o.region,
                "island": o.island,
                "lat": o.lat,
                "lon": o.lon,
                "moorage": o.moorage,
                "max_loa_ft": o.max_loa_ft,
                "raft_max": o.raft_max,
                "mooring_buoys": o.mooring_buoys,
            }
            for o in store.outstations
            if _matches_clubs(o.club, clubs)
        ]
    }


def find_outstations_near(
    store: Store, lat: float, lon: float, radius_nm: float = 20.0,
    clubs: list[str] | None = None,
) -> dict:
    candidates = [o for o in store.outstations if _matches_clubs(o.club, clubs)]
    hits = within_radius(candidates, lat, lon, radius_nm)
    return {
        "outstations": [
            {
                "name": o.name,
                "club": o.club,
                "distance_nm": round(dist, 2),
                "lat": o.lat,
                "lon": o.lon,
                "moorage": o.moorage,
                "max_loa_ft": o.max_loa_ft,
                "mooring_buoys": o.mooring_buoys,
            }
            for o, dist in hits
        ]
    }
