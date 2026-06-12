"""RVYC outstation live availability via the ClubHouseOnline court-booking API.

Credential-gated and inert without RVYC_USERNAME / RVYC_PASSWORD. Every failure
degrades to an Availability with numbers=None and a reason string; nothing here
raises out to the MCP tools. Member names from the API are never retained.

API + login map: infrastructure/docs/rvyc-outstation-booking-api.md (private).
"""

from __future__ import annotations

import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser

import httpx

logger = logging.getLogger(__name__)


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


_LOGIN_PATH = "/login.aspx"
_SCHEDULE = "/api/v1/courts/GetSchedule/{court}/{date}/{length}"
_DEFAULT_LENGTH = 60


class RvycClient:
    """Member-authenticated client for the RVYC court-booking API.

    Construct with an httpx.Client (injected for tests) + credentials. All public
    calls return an Availability and never raise on network/auth/parse failure.
    """

    def __init__(self, http, username: str, password: str, length: int = _DEFAULT_LENGTH) -> None:
        self._http = http
        self._username = username
        self._password = password
        self._length = length
        self._logged_in = False

    def _login(self) -> bool:
        try:
            page = self._http.get(_LOGIN_PATH)
            form = build_login_form(page.text, self._username, self._password)
            self._http.post(_LOGIN_PATH, data=form)
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("RVYC login error: %s", exc)
            self._logged_in = False
            return False
        ok = any(c == ".ASPXFORMSAUTH" for c in self._http.cookies.keys())
        self._logged_in = ok
        if not ok:
            logger.warning("RVYC login did not yield an auth cookie")
        return ok

    def day_availability(self, court_type_id: int, date: str, outstation: str) -> Availability:
        api_date = to_api_date(date)
        path = _SCHEDULE.format(court=court_type_id, date=api_date, length=self._length)
        for attempt in (1, 2):
            if not self._logged_in:
                if not self._login():
                    return unavailable(outstation, date, "could not sign in to RVYC")
            try:
                resp = self._http.get(path)
            except httpx.HTTPError as exc:
                logger.warning("RVYC schedule fetch error: %s", exc)
                return unavailable(outstation, date, "availability lookup failed")
            if resp.status_code == 401 and attempt == 1:
                self._logged_in = False  # stale cookie; re-login and retry once
                continue
            if resp.status_code != 200:
                logger.warning("RVYC schedule HTTP %s", resp.status_code)
                return unavailable(outstation, date, "availability lookup failed")
            try:
                return parse_day_availability(resp.json(), outstation, date)
            except (ValueError, KeyError, TypeError) as exc:
                logger.warning("RVYC schedule parse error: %s", exc)
                return unavailable(outstation, date, "availability lookup failed")
        return unavailable(outstation, date, "could not sign in to RVYC")
