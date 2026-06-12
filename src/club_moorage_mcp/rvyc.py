"""RVYC outstation live availability via the ClubHouseOnline court-booking API.

Credential-gated and inert without RVYC_USERNAME / RVYC_PASSWORD. Every failure
degrades to an Availability with numbers=None and a reason string; nothing here
raises out to the MCP tools. Member names from the API are never retained.

API + login map: infrastructure/docs/rvyc-outstation-booking-api.md (private).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone


@dataclass
class Availability:
    outstation: str
    date: str                          # ISO, as the agent supplied it
    total_slips: int | None = None
    available_slips: int | None = None
    fully_booked: bool | None = None
    checked_at: str | None = None      # ISO-8601 UTC timestamp of the live check
    reason: str | None = None          # set only when the numbers are None

    def as_dict(self) -> dict:
        return asdict(self)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_day_availability(body: dict, outstation: str, date: str) -> Availability:
    """Turn one GetSchedule JSON body into name-free availability counts.

    A slip is 'free' for the date if it has at least one available block.
    """
    schedule = (body.get("data") or {}).get("schedule") or []
    total = len(schedule)
    free = 0
    for slip in schedule:
        blocks = slip.get("blocks") or []
        if any(b.get("status") == "available" for b in blocks):
            free += 1
    return Availability(
        outstation=outstation,
        date=date,
        total_slips=total,
        available_slips=free,
        fully_booked=(free == 0),
        checked_at=_now_iso(),
    )
