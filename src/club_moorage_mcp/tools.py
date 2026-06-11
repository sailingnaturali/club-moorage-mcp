"""Pure-Python implementations of the MCP tools. No I/O beyond the Store."""

from __future__ import annotations

from dataclasses import asdict

from pilotbook_mcp.models import Anchorage
from pilotbook_mcp.scoring import rank_anchorages as _rank_anchorages

from club_moorage_mcp.geo import within_radius
from club_moorage_mcp.models import Moorage
from club_moorage_mcp.store import Store


def _matches_clubs(club: str, clubs: list[str] | None) -> bool:
    return clubs is None or club in clubs


def _relationship(m: Moorage) -> str:
    """None == an RVYC-owned outstation; reciprocals set it explicitly."""
    return m.relationship or "outstation"


def _is_available(m: Moorage) -> bool:
    """A discontinued reciprocal (available: false) is no longer somewhere you can moor."""
    return m.available is not False


def _selectable(m: Moorage, clubs: list[str] | None, relationship: str | None) -> bool:
    return (
        _matches_clubs(m.club, clubs)
        and (relationship is None or _relationship(m) == relationship)
        and _is_available(m)
    )


def list_moorage(
    store: Store, clubs: list[str] | None = None, relationship: str | None = None,
) -> dict:
    return {
        "moorage": [
            {
                "name": m.name,
                "club": m.club,
                "relationship": _relationship(m),
                "region": m.region,
                "island": m.island,
                "locale": m.locale,
                "lat": m.lat,
                "lon": m.lon,
                "moorage": m.moorage,
                "max_loa_ft": m.max_loa_ft,
                "raft_max": m.raft_max,
                "mooring_buoys": m.mooring_buoys,
                "free_nights": m.free_nights,
                "fits_vaan": m.fits_vaan,
            }
            for m in store.records
            if _selectable(m, clubs, relationship)
        ]
    }


def find_moorage_near(
    store: Store, lat: float, lon: float, radius_nm: float = 20.0,
    clubs: list[str] | None = None, relationship: str | None = None,
) -> dict:
    candidates = [m for m in store.records if _selectable(m, clubs, relationship)]
    hits = within_radius(candidates, lat, lon, radius_nm)
    return {
        "moorage": [
            {
                "name": m.name,
                "club": m.club,
                "relationship": _relationship(m),
                "distance_nm": round(dist, 2),
                "lat": m.lat,
                "lon": m.lon,
                "moorage": m.moorage,
                "max_loa_ft": m.max_loa_ft,
                "mooring_buoys": m.mooring_buoys,
                "free_nights": m.free_nights,
                "fits_vaan": m.fits_vaan,
            }
            for m, dist in hits
        ]
    }


def get_moorage(store: Store, name: str) -> dict:
    m = store.get(name)
    if m is None:
        return {"found": False, "name": name}
    record = {k: v for k, v in asdict(m).items()}
    club = store.get_club(m.club)
    club_rules = None
    if club is not None:
        club_rules = {
            "club": club.club,
            "name": club.name,
            "max_nights": club.max_nights,
            "checkout": club.checkout,
            "quiet_hours": club.quiet_hours,
            "burgee_required": club.burgee_required,
            "reciprocal": club.reciprocal,
            "source_url": club.source_url,
            "rules": club.prose,
        }
    return {"found": True, "moorage": record, "club_rules": club_rules}


def _not_ranked_reason(m: Moorage) -> str:
    if "anchoring" in m.moorage or "mooring_buoys" in m.moorage:
        return "no overnight-comfort assessment authored for this moorage"
    return "dock moorage — not an anchoring/comfort decision"


def rank_moorage(store: Store, names: list[str], forecast: list[dict]) -> dict:
    rankable: list[Anchorage] = []
    not_ranked: list[dict] = []
    unknown: list[str] = []
    for n in names:
        m = store.get(n)
        if m is None:
            unknown.append(n)
        elif m.holding is None:           # carries no comfort fields → not an overnight-comfort call
            not_ranked.append({"name": m.name, "reason": _not_ranked_reason(m)})
        else:
            rankable.append(
                Anchorage(
                    name=m.name,
                    source=m.club,
                    exposed_sectors=m.exposed_sectors,
                    holding=m.holding,
                )
            )
    ranked = _rank_anchorages(rankable, forecast) if rankable else []
    return {"ranked": ranked, "not_ranked": not_ranked, "unknown": unknown}
