"""Moorage and Club records with markdown-frontmatter (de)serialization."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields

import yaml

_FENCE = "---"


def _from_markdown(cls, text: str):
    if not text.startswith(_FENCE):
        raise ValueError("markdown must start with a '---' frontmatter fence")
    _, fm, body = text.split(_FENCE, 2)
    data = yaml.safe_load(fm) or {}
    known = {f.name for f in fields(cls)} - {"prose"}
    kwargs = {k: v for k, v in data.items() if k in known}
    return cls(prose=body.lstrip("\n"), **kwargs)


def _to_markdown(self) -> str:
    data = {k: v for k, v in asdict(self).items() if k != "prose"}
    data = {k: v for k, v in data.items() if v not in (None, [], "")}
    fm = yaml.safe_dump(data, sort_keys=False, allow_unicode=True).strip()
    return f"{_FENCE}\n{fm}\n{_FENCE}\n{self.prose}"


@dataclass
class Moorage:
    name: str
    club: str
    lat: float | None = None
    lon: float | None = None
    region: str | None = None
    island: str | None = None
    country: str | None = None
    address: str | None = None
    source_url: str | None = None
    moorage: list[str] = field(default_factory=list)     # dock | mooring_buoys | anchoring
    max_loa_ft: int | None = None
    raft_max: int | None = None
    mooring_buoys: int | None = None
    mooring_buoy_notes: str | None = None
    anchoring_notes: str | None = None
    slip: str | None = None
    shore_power: str | None = None
    potable_water: bool | None = None
    pumpout: bool | None = None
    vhf_channel: str | None = None
    phone: str | None = None
    amenities: list[str] = field(default_factory=list)
    booking: str | None = None
    booking_url: str | None = None
    confirmation_required: bool | None = None
    pilotbook_anchorage: str | None = None               # cross-link to nearest pilot-book anchorage
    exposed_sectors: list[str] = field(default_factory=list)   # only on overnight-capable stations
    holding: str | None = None                           # good | fair | poor | variable
    swing_room: str | None = None                        # ample | adequate | limited | tight
    last_updated: str | None = None
    confidence: str | None = None
    court_type_id: int | None = None                     # RVYC court-booking API id (783 Long Harbour, 781 Friday Harbor); only the reservable outstations
    # --- relationship + reciprocal-club fields ---------------------------------
    # `relationship` distinguishes an RVYC-owned outstation from a partner club that
    # hosts visiting RVYC members. None == "outstation" (the bundled RVYC three).
    relationship: str | None = None                      # None/"outstation" | "reciprocal"
    available: bool | None = None                        # False == reciprocal discontinued (kept for context)
    coords_approx: bool | None = None                    # coords from research, not the RVYC map pin
    locale: str | None = None                            # town/area label for reciprocals (cf. island)
    loa_note: str | None = None                          # non-LOA size limit (shallow channel, etc.)
    power: bool | str | None = None                      # reciprocal dock power: True/False or a note ("$4/day")
    water: bool | str | None = None
    vhf: str | None = None                               # reciprocal arrival hail (cf. vhf_channel)
    reservation_required: bool | None = None
    free_nights: int | None = None                       # reciprocal terms — these vary per club
    nightly_fee: str | None = None
    facility_fee: str | None = None
    max_stay: str | None = None
    insurance_min: str | None = None
    fits_vaan: bool | str | None = None                  # True | False | "borderline" (49ft beamy cat)
    flags: list[str] = field(default_factory=list)       # gotchas: verify-before-arrival, CBP port, etc.
    prose: str = ""

    from_markdown = classmethod(_from_markdown)
    to_markdown = _to_markdown


@dataclass
class Club:
    club: str
    name: str
    source_url: str | None = None
    rules_url: str | None = None
    max_nights: int | None = None
    checkout: str | None = None
    quiet_hours: str | None = None
    burgee_required: bool | None = None
    reciprocal: bool | None = None
    prose: str = ""

    from_markdown = classmethod(_from_markdown)
    to_markdown = _to_markdown
