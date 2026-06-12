"""RVYC outstation live availability via the ClubHouseOnline court-booking API.

Credential-gated and inert without RVYC_USERNAME / RVYC_PASSWORD. Every failure
degrades to an Availability with numbers=None and a reason string; nothing here
raises out to the MCP tools. Member names from the API are never retained.

API + login map: infrastructure/docs/rvyc-outstation-booking-api.md (private).
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser


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


def resolve_credentials() -> tuple[str, str] | None:
    user = os.environ.get("RVYC_USERNAME")
    pw = os.environ.get("RVYC_PASSWORD")
    if user and pw:
        return user, pw
    return None


def to_api_date(iso_date: str) -> str:
    """'2026-06-20' -> '20260620'. The API 400s on any other format."""
    dt = datetime.strptime(iso_date, "%Y-%m-%d")
    return dt.strftime("%Y%m%d")


def unavailable(outstation: str, date: str, reason: str) -> Availability:
    """Availability with no live numbers, carrying a reason string."""
    return Availability(outstation=outstation, date=date, reason=reason)


class _InputCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.inputs: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "input":
            self.inputs.append({k: (v or "") for k, v in attrs})


def build_login_form(login_html: str, username: str, password: str) -> dict[str, str]:
    """Build the WebForms POST body from the login page HTML + credentials.

    Echoes every hidden input, fills the UserName/Password controls, and includes
    the submit button name. Raises ValueError if the username control is absent
    (page shape changed or we were served something else).
    """
    parser = _InputCollector()
    parser.feed(login_html)
    form: dict[str, str] = {}
    user_key = pass_key = button_key = None
    for inp in parser.inputs:
        name = inp.get("name")
        if not name:
            continue
        itype = inp.get("type", "")
        if name.endswith("$UserName"):
            user_key = name
        elif name.endswith("$Password"):
            pass_key = name
        elif name.endswith("$LoginButton"):
            button_key = name
            form[name] = inp.get("value", "Log in")
        elif itype == "hidden":
            form[name] = inp.get("value", "")
    if user_key is None or pass_key is None:
        raise ValueError("login form missing UserName/Password controls")
    form[user_key] = username
    form[pass_key] = password
    if button_key is None:
        raise ValueError("login form missing LoginButton control")
    return form
