"""Pure-Python implementations of the MCP tools. No I/O beyond the Store."""

from __future__ import annotations

from dataclasses import asdict

from pilotbook_mcp.models import Anchorage
from pilotbook_mcp.scoring import rank_anchorages as _rank_anchorages

from club_moorage_mcp.geo import within_radius
from club_moorage_mcp.models import Outstation
from club_moorage_mcp.store import Store


def _matches_clubs(club: str, clubs: list[str] | None) -> bool:
    return clubs is None or club in clubs


def _relationship(o: Outstation) -> str:
    """None == an RVYC-owned outstation; reciprocals set it explicitly."""
    return o.relationship or "outstation"


def _is_available(o: Outstation) -> bool:
    """A discontinued reciprocal (available: false) is no longer somewhere you can moor."""
    return o.available is not False


def _selectable(o: Outstation, clubs: list[str] | None, relationship: str | None) -> bool:
    return (
        _matches_clubs(o.club, clubs)
        and (relationship is None or _relationship(o) == relationship)
        and _is_available(o)
    )


def list_outstations(
    store: Store, clubs: list[str] | None = None, relationship: str | None = None,
) -> dict:
    return {
        "outstations": [
            {
                "name": o.name,
                "club": o.club,
                "relationship": _relationship(o),
                "region": o.region,
                "island": o.island,
                "locale": o.locale,
                "lat": o.lat,
                "lon": o.lon,
                "moorage": o.moorage,
                "max_loa_ft": o.max_loa_ft,
                "raft_max": o.raft_max,
                "mooring_buoys": o.mooring_buoys,
                "free_nights": o.free_nights,
                "fits_vaan": o.fits_vaan,
            }
            for o in store.outstations
            if _selectable(o, clubs, relationship)
        ]
    }


def find_outstations_near(
    store: Store, lat: float, lon: float, radius_nm: float = 20.0,
    clubs: list[str] | None = None, relationship: str | None = None,
) -> dict:
    candidates = [o for o in store.outstations if _selectable(o, clubs, relationship)]
    hits = within_radius(candidates, lat, lon, radius_nm)
    return {
        "outstations": [
            {
                "name": o.name,
                "club": o.club,
                "relationship": _relationship(o),
                "distance_nm": round(dist, 2),
                "lat": o.lat,
                "lon": o.lon,
                "moorage": o.moorage,
                "max_loa_ft": o.max_loa_ft,
                "mooring_buoys": o.mooring_buoys,
                "free_nights": o.free_nights,
                "fits_vaan": o.fits_vaan,
            }
            for o, dist in hits
        ]
    }


def get_outstation(store: Store, name: str) -> dict:
    o = store.get(name)
    if o is None:
        return {"found": False, "name": name}
    record = {k: v for k, v in asdict(o).items()}
    club = store.get_club(o.club)
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
    return {"found": True, "outstation": record, "club_rules": club_rules}


def _not_ranked_reason(o: Outstation) -> str:
    if "anchoring" in o.moorage or "mooring_buoys" in o.moorage:
        return "no overnight-comfort assessment authored for this station"
    return "dock moorage — not an anchoring/comfort decision"


def rank_outstations(store: Store, names: list[str], forecast: list[dict]) -> dict:
    rankable: list[Anchorage] = []
    not_ranked: list[dict] = []
    unknown: list[str] = []
    for n in names:
        o = store.get(n)
        if o is None:
            unknown.append(n)
        elif o.holding is None:           # carries no comfort fields → not an overnight-comfort call
            not_ranked.append({"name": o.name, "reason": _not_ranked_reason(o)})
        else:
            rankable.append(
                Anchorage(
                    name=o.name,
                    source=o.club,
                    exposed_sectors=o.exposed_sectors,
                    holding=o.holding,
                )
            )
    ranked = _rank_anchorages(rankable, forecast) if rankable else []
    return {"ranked": ranked, "not_ranked": not_ranked, "unknown": unknown}
