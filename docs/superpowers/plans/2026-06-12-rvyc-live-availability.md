# RVYC Outstation Live Availability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let `club-moorage-mcp` log itself into RVYC's member booking site and report whether the two reservable outstations (Long Harbour, Friday Harbor) are free on a given date, surfaced both as a standalone tool and as optional annotation on the ranking/proximity tools.

**Architecture:** A new self-contained `rvyc.py` module owns an httpx session that scripts the ASP.NET WebForms login, caches the auth cookie, and parses the `GetSchedule` JSON into an `Availability` dataclass. The live layer is credential-gated and inert without `RVYC_USERNAME`/`RVYC_PASSWORD`; every failure degrades to `availability: null` + a reason, never blocking the static moorage answer. A `court_type_id` field added to the `Moorage` model + the two reservable data records drives the mapping.

**Tech Stack:** Python 3.11+, httpx, dataclasses, pytest (asyncio_mode=auto). Tools are pure-Python over `Store`; httpx is mocked via `httpx.MockTransport` in unit tests.

**Reference:** `docs/superpowers/specs/2026-06-12-rvyc-live-availability-design.md` (spec); `infrastructure/docs/rvyc-outstation-booking-api.md` (API map, private repo).

---

## File Structure

- **Create** `src/club_moorage_mcp/rvyc.py` — `Availability` dataclass, `RvycClient` (login + cookie cache + `day_availability`), `parse_day_availability` (pure JSON→counts), `resolve_credentials`. One responsibility: talking to the RVYC booking API and returning name-free availability.
- **Modify** `src/club_moorage_mcp/models.py` — add `court_type_id: int | None = None` to `Moorage`.
- **Modify** `src/club_moorage_mcp/data/outstations/rvyc-long-harbour.md` — add `court_type_id: 783`.
- **Modify** `src/club_moorage_mcp/data/outstations/rvyc-friday-harbor.md` — add `court_type_id: 781`.
- **Modify** `src/club_moorage_mcp/tools.py` — add `check_availability`; thread optional `date` + an availability provider into `find_moorage_near` and `rank_moorage`.
- **Modify** `src/club_moorage_mcp/server.py` — register `check_availability` tool, add `date` to two schemas, wire dispatch + a process-lifetime availability provider.
- **Modify** `pyproject.toml` — add `httpx` dependency.
- **Create** `tests/fixtures/rvyc/schedule_mixed.json`, `schedule_all_booked.json`, `login_form.html` — captured/scrubbed API + login fixtures.
- **Create** `tests/test_rvyc.py` — parsing, login-body assembly, degradation, caching tests.
- **Modify** `tests/test_tools.py` — `check_availability` + `date` annotation tests with a stub provider.

A note on the **availability provider seam**: `tools.py` must stay pure (no network) and easily testable. So the live lookup is passed *into* the tool functions as a callable `availability_provider(court_type_id: int, date: str) -> dict | None`. Production wires `RvycClient.day_availability`; tests pass a stub. This keeps `tools.py` I/O-free exactly as its module docstring promises.

---

## Task 1: Add `court_type_id` to the model and data records

**Files:**
- Modify: `src/club_moorage_mcp/models.py` (Moorage dataclass, after `confidence`)
- Modify: `src/club_moorage_mcp/data/outstations/rvyc-long-harbour.md`
- Modify: `src/club_moorage_mcp/data/outstations/rvyc-friday-harbor.md`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_models.py`:

```python
def test_moorage_round_trips_court_type_id():
    from club_moorage_mcp.models import Moorage
    md = (
        "---\n"
        "name: Long Harbour\n"
        "club: RVYC\n"
        "court_type_id: 783\n"
        "---\n"
        "body\n"
    )
    m = Moorage.from_markdown(md)
    assert m.court_type_id == 783
    assert "court_type_id: 783" in m.to_markdown()


def test_moorage_court_type_id_defaults_none():
    from club_moorage_mcp.models import Moorage
    m = Moorage.from_markdown("---\nname: X\nclub: RVYC\n---\nbody\n")
    assert m.court_type_id is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_models.py::test_moorage_round_trips_court_type_id -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'court_type_id'` (or AttributeError).

- [ ] **Step 3: Add the field**

In `src/club_moorage_mcp/models.py`, in the `Moorage` dataclass, immediately after the line `confidence: str | None = None` add:

```python
    court_type_id: int | None = None                     # RVYC court-booking API id (783 Long Harbour, 781 Friday Harbor); only the reservable outstations
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_models.py -v`
Expected: PASS (both new tests + existing model tests).

- [ ] **Step 5: Add the id to the two reservable records**

In `src/club_moorage_mcp/data/outstations/rvyc-long-harbour.md`, add this line inside the frontmatter, right after `booking: rvyc-online`:

```yaml
court_type_id: 783
```

In `src/club_moorage_mcp/data/outstations/rvyc-friday-harbor.md`, add inside the frontmatter, right after its `booking:` line (check the exact key; it is `booking: rvyc-online`):

```yaml
court_type_id: 781
```

Leave `rvyc-telegraph-harbour.md` and all reciprocals untouched (no `court_type_id`).

- [ ] **Step 6: Verify the data loads**

Run: `uv run python -c "from club_moorage_mcp.store import Store; s=Store.load(); print({m.name: m.court_type_id for m in s.records if m.court_type_id})"`
Expected: `{'Friday Harbor': 781, 'Long Harbour': 783}`

- [ ] **Step 7: Commit**

```bash
git add src/club_moorage_mcp/models.py src/club_moorage_mcp/data/outstations/rvyc-long-harbour.md src/club_moorage_mcp/data/outstations/rvyc-friday-harbor.md tests/test_models.py
git commit -m "feat: add court_type_id to Moorage for RVYC reservable outstations"
```

---

## Task 2: Add httpx dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add the dependency**

In `pyproject.toml`, in the `[project]` `dependencies` list, add `"httpx>=0.27"` after the existing entries so it reads:

```toml
dependencies = [
    "mcp>=1.27.1",
    "pyyaml>=6.0.2",
    "pilotbook-mcp>=0.1.7",
    "httpx>=0.27",
]
```

- [ ] **Step 2: Sync and verify import**

Run: `uv sync && uv run python -c "import httpx; print(httpx.__version__)"`
Expected: prints a version `>= 0.27`.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "build: add httpx dependency for RVYC availability client"
```

---

## Task 3: Pure availability parser

The parser is pure (dict in, dict out) so it is trivially testable without network. `Availability` is the result shape; `parse_day_availability` turns one `GetSchedule` JSON body into it.

**Files:**
- Create: `src/club_moorage_mcp/rvyc.py`
- Create: `tests/fixtures/rvyc/schedule_mixed.json`
- Create: `tests/fixtures/rvyc/schedule_all_booked.json`
- Test: `tests/test_rvyc.py`

- [ ] **Step 1: Create the scrubbed fixtures**

Create `tests/fixtures/rvyc/schedule_mixed.json` (3 slips, 1 booked / 2 available — real structure, member name redacted):

```json
{
  "retCode": 0,
  "errorMessage": null,
  "data": {
    "schedule": [
      {
        "courtName": "LH Slip 01", "courtId": 11160, "externalID": 1,
        "startTime": "2026/06/20 11:00", "endTime": "2026/06/20 23:00",
        "blocks": [
          {"courtId": 11160, "bookingId": 9110688, "status": "booked",
           "startTime": "11:00 AM", "endTime": "11:00 PM", "isSelectable": false,
           "players": ["REDACTED"], "start": "11:00:00", "end": "23:00:00"}
        ]
      },
      {
        "courtName": "LH Slip 02", "courtId": 11161, "externalID": 2,
        "startTime": "2026/06/20 11:00", "endTime": "2026/06/20 23:00",
        "blocks": [
          {"courtId": 11161, "bookingId": 0, "status": "available",
           "startTime": "11:00 AM", "endTime": "11:00 PM", "isSelectable": true,
           "players": [], "start": "11:00:00", "end": "23:00:00"}
        ]
      },
      {
        "courtName": "LH Slip 03", "courtId": 11162, "externalID": 3,
        "startTime": "2026/06/20 11:00", "endTime": "2026/06/20 23:00",
        "blocks": [
          {"courtId": 11162, "bookingId": 0, "status": "available",
           "startTime": "11:00 AM", "endTime": "11:00 PM", "isSelectable": true,
           "players": [], "start": "11:00:00", "end": "23:00:00"}
        ]
      }
    ],
    "bookings": []
  }
}
```

Create `tests/fixtures/rvyc/schedule_all_booked.json` — same as above but every slip's block has `"status": "booked"`, `"isSelectable": false`, `"players": ["REDACTED"]`, `"bookingId": 9110688`. (Copy the file and change slips 02 and 03 to booked.)

- [ ] **Step 2: Write the failing test**

Create `tests/test_rvyc.py`:

```python
import json
from pathlib import Path

from club_moorage_mcp.rvyc import Availability, parse_day_availability

FIX = Path(__file__).parent / "fixtures" / "rvyc"


def _load(name):
    return json.loads((FIX / name).read_text())


def test_parse_mixed_counts_free_slips():
    av = parse_day_availability(_load("schedule_mixed.json"), outstation="Long Harbour", date="2026-06-20")
    assert isinstance(av, Availability)
    assert av.total_slips == 3
    assert av.available_slips == 2
    assert av.fully_booked is False
    assert av.outstation == "Long Harbour"
    assert av.date == "2026-06-20"
    assert av.reason is None
    assert av.checked_at is not None


def test_parse_all_booked_is_fully_booked():
    av = parse_day_availability(_load("schedule_all_booked.json"), outstation="Long Harbour", date="2026-06-20")
    assert av.total_slips == 3
    assert av.available_slips == 0
    assert av.fully_booked is True


def test_parse_never_leaks_player_names():
    # Whatever the parser returns, no member name may appear anywhere in it.
    av = parse_day_availability(_load("schedule_mixed.json"), outstation="Long Harbour", date="2026-06-20")
    assert "REDACTED" not in json.dumps(av.as_dict())
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_rvyc.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'club_moorage_mcp.rvyc'`.

- [ ] **Step 4: Write `rvyc.py` (dataclass + parser only)**

Create `src/club_moorage_mcp/rvyc.py`:

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_rvyc.py -v`
Expected: PASS (all three tests).

- [ ] **Step 6: Commit**

```bash
git add src/club_moorage_mcp/rvyc.py tests/fixtures/rvyc/ tests/test_rvyc.py
git commit -m "feat: name-free RVYC schedule parser + Availability dataclass"
```

---

## Task 4: Credential resolution + date conversion + unavailable-reason helper

Small pure helpers used by the client and tools. Kept separate so they are unit-testable without httpx.

**Files:**
- Modify: `src/club_moorage_mcp/rvyc.py`
- Test: `tests/test_rvyc.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_rvyc.py`:

```python
import pytest
from club_moorage_mcp.rvyc import resolve_credentials, to_api_date, unavailable


def test_resolve_credentials_reads_env(monkeypatch):
    monkeypatch.setenv("RVYC_USERNAME", "user")
    monkeypatch.setenv("RVYC_PASSWORD", "pass")
    assert resolve_credentials() == ("user", "pass")


def test_resolve_credentials_none_when_unset(monkeypatch):
    monkeypatch.delenv("RVYC_USERNAME", raising=False)
    monkeypatch.delenv("RVYC_PASSWORD", raising=False)
    assert resolve_credentials() is None


def test_to_api_date_converts_iso():
    assert to_api_date("2026-06-20") == "20260620"


def test_to_api_date_rejects_bad():
    with pytest.raises(ValueError):
        to_api_date("06/20/2026")


def test_unavailable_builds_reason_only_availability():
    av = unavailable("Telegraph Harbour", "2026-06-20", "first-come-first-served; book via telegraphharbour.com")
    assert av.total_slips is None
    assert av.available_slips is None
    assert av.fully_booked is None
    assert av.reason == "first-come-first-served; book via telegraphharbour.com"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_rvyc.py -k "credentials or api_date or unavailable" -v`
Expected: FAIL — `ImportError: cannot import name 'resolve_credentials'`.

- [ ] **Step 3: Add the helpers**

In `src/club_moorage_mcp/rvyc.py`, add `import os` at the top (with the other imports) and append:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_rvyc.py -v`
Expected: PASS (all tests so far).

- [ ] **Step 5: Commit**

```bash
git add src/club_moorage_mcp/rvyc.py tests/test_rvyc.py
git commit -m "feat: RVYC credential/date/unavailable helpers"
```

---

## Task 5: Login body assembly

The ASP.NET login is a POST to `/login.aspx` echoing hidden fields (`__VIEWSTATE`, `__VIEWSTATEGENERATOR`, `__EVENTVALIDATION`, etc.) plus the username/password under long control names, plus the submit button name. `build_login_form` is a pure function: login-page HTML + creds → the POST body dict. Testing it against a captured form keeps the brittle scraping isolated and verifiable.

**Files:**
- Modify: `src/club_moorage_mcp/rvyc.py`
- Create: `tests/fixtures/rvyc/login_form.html`
- Test: `tests/test_rvyc.py`

- [ ] **Step 1: Create the login-form fixture**

Create `tests/fixtures/rvyc/login_form.html` with a minimal form carrying the real control names:

```html
<!DOCTYPE html><html><body>
<form method="post" action="/login.aspx" id="form">
<input type="hidden" name="__VIEWSTATE" id="__VIEWSTATE" value="VS_TOKEN_ABC" />
<input type="hidden" name="__VIEWSTATEGENERATOR" id="__VIEWSTATEGENERATOR" value="GEN123" />
<input type="hidden" name="__EVENTVALIDATION" id="__EVENTVALIDATION" value="EV_TOKEN_XYZ" />
<input type="hidden" name="__EVENTTARGET" id="__EVENTTARGET" value="" />
<input type="hidden" name="__EVENTARGUMENT" id="__EVENTARGUMENT" value="" />
<input name="p$lt$ContentWidgets$pageplaceholder$p$lt$zoneContent$CHO_Widget_LoginFormWithFullscreenBackground_XLarge$loginCtrl$BaseLogin$UserName" type="text" />
<input name="p$lt$ContentWidgets$pageplaceholder$p$lt$zoneContent$CHO_Widget_LoginFormWithFullscreenBackground_XLarge$loginCtrl$BaseLogin$Password" type="password" />
<input type="submit" name="p$lt$ContentWidgets$pageplaceholder$p$lt$zoneContent$CHO_Widget_LoginFormWithFullscreenBackground_XLarge$loginCtrl$BaseLogin$LoginButton" value="Log in" />
</form></body></html>
```

- [ ] **Step 2: Write the failing test**

Append to `tests/test_rvyc.py`:

```python
from club_moorage_mcp.rvyc import build_login_form


def test_build_login_form_includes_hidden_and_credentials():
    html = (FIX / "login_form.html").read_text()
    form = build_login_form(html, "myuser", "mypass")
    # Hidden ASP.NET state echoed back verbatim
    assert form["__VIEWSTATE"] == "VS_TOKEN_ABC"
    assert form["__VIEWSTATEGENERATOR"] == "GEN123"
    assert form["__EVENTVALIDATION"] == "EV_TOKEN_XYZ"
    # Username/password placed under whatever field name ends in UserName/Password
    user_key = next(k for k in form if k.endswith("$UserName"))
    pass_key = next(k for k in form if k.endswith("$Password"))
    assert form[user_key] == "myuser"
    assert form[pass_key] == "mypass"
    # Submit button present (ASP.NET needs the button name to fire the click handler)
    assert any(k.endswith("$LoginButton") for k in form)


def test_build_login_form_raises_without_username_field():
    with pytest.raises(ValueError):
        build_login_form("<html><form></form></html>", "u", "p")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_rvyc.py -k login_form -v`
Expected: FAIL — `ImportError: cannot import name 'build_login_form'`.

- [ ] **Step 4: Implement `build_login_form`**

Parsing with stdlib `html.parser` (no new dependency). Add to `src/club_moorage_mcp/rvyc.py`:

```python
from html.parser import HTMLParser


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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_rvyc.py -k login_form -v`
Expected: PASS (both tests).

- [ ] **Step 6: Commit**

```bash
git add src/club_moorage_mcp/rvyc.py tests/fixtures/rvyc/login_form.html tests/test_rvyc.py
git commit -m "feat: assemble RVYC WebForms login POST body from page HTML"
```

---

## Task 6: `RvycClient` — login, cookie cache, `day_availability`, degradation

The client ties it together over httpx. Tests drive it with `httpx.MockTransport`, asserting both the happy path and every degradation path. The client must catch all network/parse errors and return an `unavailable(...)` Availability — never raise.

**Files:**
- Modify: `src/club_moorage_mcp/rvyc.py`
- Test: `tests/test_rvyc.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_rvyc.py`:

```python
import httpx
from club_moorage_mcp.rvyc import RvycClient

BASE = "https://rvyc.bc.ca"


def _login_html():
    return (FIX / "login_form.html").read_text()


def _client_with(handler, **kw):
    transport = httpx.MockTransport(handler)
    http = httpx.Client(base_url=BASE, transport=transport)
    return RvycClient(http=http, username="u", password="p", **kw)


def test_day_availability_logs_in_then_fetches():
    calls = {"login": 0, "schedule": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/login.aspx":
            if request.method == "GET":
                return httpx.Response(200, text=_login_html())
            calls["login"] += 1
            # WebForms posts back; set the auth cookie on success
            return httpx.Response(200, headers={"set-cookie": ".ASPXFORMSAUTH=TOKEN; path=/"})
        if "GetSchedule" in request.url.path:
            calls["schedule"] += 1
            return httpx.Response(200, json=json.loads((FIX / "schedule_mixed.json").read_text()))
        return httpx.Response(404)

    client = _client_with(handler)
    av = client.day_availability(783, "2026-06-20", outstation="Long Harbour")
    assert av.available_slips == 2
    assert calls["login"] == 1
    assert calls["schedule"] == 1


def test_day_availability_reuses_session_no_relogin():
    logins = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/login.aspx":
            if request.method == "GET":
                return httpx.Response(200, text=_login_html())
            logins["n"] += 1
            return httpx.Response(200, headers={"set-cookie": ".ASPXFORMSAUTH=TOKEN; path=/"})
        return httpx.Response(200, json=json.loads((FIX / "schedule_mixed.json").read_text()))

    client = _client_with(handler)
    client.day_availability(783, "2026-06-20", outstation="Long Harbour")
    client.day_availability(781, "2026-06-21", outstation="Friday Harbor")
    assert logins["n"] == 1  # second call reused the cookie


def test_day_availability_relogins_once_on_401():
    state = {"authed": False, "logins": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/login.aspx":
            if request.method == "GET":
                return httpx.Response(200, text=_login_html())
            state["authed"] = True
            state["logins"] += 1
            return httpx.Response(200, headers={"set-cookie": ".ASPXFORMSAUTH=TOKEN; path=/"})
        if not state["authed"]:
            return httpx.Response(401, json={"message": "denied"})
        return httpx.Response(200, json=json.loads((FIX / "schedule_mixed.json").read_text()))

    # Pretend we start with a stale cookie so the first schedule call 401s.
    client = _client_with(handler)
    client._logged_in = True  # simulate cached-but-stale session
    av = client.day_availability(783, "2026-06-20", outstation="Long Harbour")
    assert av.available_slips == 2
    assert state["logins"] == 1


def test_day_availability_login_failure_degrades():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/login.aspx":
            if request.method == "GET":
                return httpx.Response(200, text=_login_html())
            return httpx.Response(200, text="Login failed")  # no auth cookie set
        return httpx.Response(401, json={"message": "denied"})

    client = _client_with(handler)
    av = client.day_availability(783, "2026-06-20", outstation="Long Harbour")
    assert av.total_slips is None
    assert av.reason == "could not sign in to RVYC"


def test_day_availability_bad_json_degrades():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/login.aspx":
            if request.method == "GET":
                return httpx.Response(200, text=_login_html())
            return httpx.Response(200, headers={"set-cookie": ".ASPXFORMSAUTH=TOKEN; path=/"})
        return httpx.Response(200, text="<html>not json</html>")

    client = _client_with(handler)
    av = client.day_availability(783, "2026-06-20", outstation="Long Harbour")
    assert av.total_slips is None
    assert av.reason == "availability lookup failed"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_rvyc.py -k day_availability -v`
Expected: FAIL — `RvycClient` has no `http`/`username` constructor or no `day_availability`.

- [ ] **Step 3: Implement `RvycClient`**

Add to `src/club_moorage_mcp/rvyc.py`. First ensure these are at the **top** of the file with the other imports: `import logging`, `import httpx`, and a module logger `logger = logging.getLogger(__name__)`. Then append:

```python
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
        # Ensure a session, fetching schedule with one transparent re-login on 401.
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_rvyc.py -v`
Expected: PASS (all client + parser + helper tests).

- [ ] **Step 5: Commit**

```bash
git add src/club_moorage_mcp/rvyc.py tests/test_rvyc.py
git commit -m "feat: RvycClient login + cookie reuse + degrading day_availability"
```

---

## Task 7: Provider factory with credential gate + per-process cache

A single factory builds the production availability provider: returns `None` when no credentials (so tools know the live layer is off), otherwise a callable that wraps one `RvycClient` and memoizes `(court_type_id, date)` for the process with a short TTL.

**Files:**
- Modify: `src/club_moorage_mcp/rvyc.py`
- Test: `tests/test_rvyc.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_rvyc.py`:

```python
from club_moorage_mcp.rvyc import build_provider


def test_build_provider_returns_none_without_credentials(monkeypatch):
    monkeypatch.delenv("RVYC_USERNAME", raising=False)
    monkeypatch.delenv("RVYC_PASSWORD", raising=False)
    assert build_provider() is None


def test_provider_caches_by_court_and_date(monkeypatch):
    monkeypatch.setenv("RVYC_USERNAME", "u")
    monkeypatch.setenv("RVYC_PASSWORD", "p")
    fetches = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/login.aspx":
            if request.method == "GET":
                return httpx.Response(200, text=_login_html())
            return httpx.Response(200, headers={"set-cookie": ".ASPXFORMSAUTH=TOKEN; path=/"})
        fetches["n"] += 1
        return httpx.Response(200, json=json.loads((FIX / "schedule_mixed.json").read_text()))

    http = httpx.Client(base_url=BASE, transport=httpx.MockTransport(handler))
    provider = build_provider(client=RvycClient(http=http, username="u", password="p"))
    a = provider(783, "2026-06-20", "Long Harbour")
    b = provider(783, "2026-06-20", "Long Harbour")
    assert a["available_slips"] == 2
    assert b == a
    assert fetches["n"] == 1  # second lookup served from cache
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_rvyc.py -k provider -v`
Expected: FAIL — `cannot import name 'build_provider'`.

- [ ] **Step 3: Implement `build_provider`**

Add to `src/club_moorage_mcp/rvyc.py` (`import time` at top):

```python
_CACHE_TTL_SECONDS = 300


def build_provider(client: "RvycClient | None" = None):
    """Production availability provider, or None when no credentials are configured.

    Returns a callable (court_type_id, date, outstation) -> dict (Availability.as_dict()),
    memoized per (court_type_id, date) for _CACHE_TTL_SECONDS.
    """
    if client is None:
        creds = resolve_credentials()
        if creds is None:
            return None
        http = httpx.Client(
            base_url="https://rvyc.bc.ca",
            timeout=20.0,
            headers={"User-Agent": "club-moorage-mcp", "Accept": "application/json, text/plain, */*"},
            follow_redirects=True,
        )
        client = RvycClient(http=http, username=creds[0], password=creds[1])

    cache: dict[tuple[int, str], tuple[float, dict]] = {}

    def provider(court_type_id: int, date: str, outstation: str) -> dict:
        key = (court_type_id, date)
        hit = cache.get(key)
        now = time.monotonic()
        if hit and now - hit[0] < _CACHE_TTL_SECONDS:
            return hit[1]
        result = client.day_availability(court_type_id, date, outstation=outstation).as_dict()
        cache[key] = (now, result)
        return result

    return provider
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_rvyc.py -v`
Expected: PASS (all rvyc tests).

- [ ] **Step 5: Commit**

```bash
git add src/club_moorage_mcp/rvyc.py tests/test_rvyc.py
git commit -m "feat: credential-gated RVYC availability provider with per-process cache"
```

---

## Task 8: `check_availability` tool

The tool maps an outstation name to availability, using the record's `court_type_id` and the injected provider. It returns the right `null`+reason shape for not-bookable outstations and when the provider is off.

**Files:**
- Modify: `src/club_moorage_mcp/tools.py`
- Test: `tests/test_tools.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_tools.py` (uses the *real* bundled data via `Store.load()` for RVYC records; a stub provider stands in for the network):

```python
from club_moorage_mcp.store import Store as _RealStore
from club_moorage_mcp.tools import check_availability


def _rvyc_store():
    return _RealStore.load()  # bundled RVYC + reciprocal data


def _stub_provider(court_type_id, date, outstation):
    return {
        "outstation": outstation, "date": date, "total_slips": 11,
        "available_slips": 9, "fully_booked": False,
        "checked_at": "2026-06-12T00:00:00+00:00", "reason": None,
    }


def test_check_availability_live_outstation():
    out = check_availability(_rvyc_store(), name="Long Harbour", date="2026-06-20", provider=_stub_provider)
    assert out["found"] is True
    assert out["availability"]["available_slips"] == 9
    assert out["availability"]["fully_booked"] is False


def test_check_availability_telegraph_is_not_online_bookable():
    out = check_availability(_rvyc_store(), name="Telegraph Harbour", date="2026-06-20", provider=_stub_provider)
    assert out["found"] is True
    assert out["availability"]["total_slips"] is None
    assert "telegraphharbour.com" in out["availability"]["reason"]


def test_check_availability_no_provider_reports_not_configured():
    out = check_availability(_rvyc_store(), name="Long Harbour", date="2026-06-20", provider=None)
    assert out["availability"]["reason"] == "live availability not configured"
    assert out["availability"]["total_slips"] is None


def test_check_availability_unknown_name():
    out = check_availability(_rvyc_store(), name="Nowhere", date="2026-06-20", provider=_stub_provider)
    assert out["found"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_tools.py -k check_availability -v`
Expected: FAIL — `cannot import name 'check_availability'`.

- [ ] **Step 3: Implement the tool**

In `src/club_moorage_mcp/tools.py`, add this import near the top:

```python
from club_moorage_mcp.rvyc import unavailable
```

Then add a shared helper and the tool. The helper centralises the "which availability shape applies" decision so the ranking tools reuse it:

```python
def _availability_for(m: Moorage, date: str | None, provider) -> dict | None:
    """Resolve an availability block for one moorage, or None if no date was asked.

    - No date requested            -> None (tools omit the field)
    - Not online-bookable          -> reason pointing at the right channel
    - Live layer off (no provider) -> 'live availability not configured'
    - Otherwise                    -> live numbers via the provider
    """
    if date is None:
        return None
    if m.court_type_id is None:
        if m.booking_url:
            reason = f"first-come-first-served; book via {m.booking_url}"
        else:
            reason = "no online reservation system for this moorage"
        return unavailable(m.name, date, reason).as_dict()
    if provider is None:
        return unavailable(m.name, date, "live availability not configured").as_dict()
    return provider(m.court_type_id, date, m.name)


def check_availability(store: Store, name: str, date: str, provider=None) -> dict:
    m = store.get(name)
    if m is None:
        return {"found": False, "name": name}
    record = {k: v for k, v in asdict(m).items()}
    return {"found": True, "moorage": record, "availability": _availability_for(m, date, provider)}
```

Note: Telegraph Harbour's record carries `booking_url:` only if present; confirm `rvyc-telegraph-harbour.md` has `booking_url: https://www.telegraphharbour.com` (it does per the spec). If a not-bookable record lacks `booking_url`, the generic reason is used.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_tools.py -k check_availability -v`
Expected: PASS (all four).

- [ ] **Step 5: Commit**

```bash
git add src/club_moorage_mcp/tools.py tests/test_tools.py
git commit -m "feat: check_availability tool with not-bookable + no-creds reasons"
```

---

## Task 9: Optional `date` annotation on `find_moorage_near` and `rank_moorage`

Both tools gain an optional `date` and `provider`. When `date` is set, each result with a `court_type_id` (and the not-bookable ones too) gets an `availability` block via the shared helper. Availability is annotation, never a filter.

**Files:**
- Modify: `src/club_moorage_mcp/tools.py`
- Test: `tests/test_tools.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_tools.py`:

```python
from club_moorage_mcp.tools import find_moorage_near as _find, rank_moorage as _rank


def test_find_moorage_near_annotates_availability_when_date_given():
    store = _rvyc_store()
    # Long Harbour is at 48.86, -123.46; search around it.
    out = _find(store, lat=48.86, lon=-123.46, radius_nm=80, date="2026-06-20", provider=_stub_provider)
    lh = next(o for o in out["moorage"] if o["name"] == "Long Harbour")
    assert lh["availability"]["available_slips"] == 9


def test_find_moorage_near_no_date_omits_availability():
    store = _rvyc_store()
    out = _find(store, lat=48.86, lon=-123.46, radius_nm=80)
    lh = next(o for o in out["moorage"] if o["name"] == "Long Harbour")
    assert "availability" not in lh


def test_rank_moorage_full_outstation_still_listed_and_flagged():
    store = _rvyc_store()

    def full_provider(court_type_id, date, outstation):
        return {"outstation": outstation, "date": date, "total_slips": 11,
                "available_slips": 0, "fully_booked": True,
                "checked_at": "2026-06-12T00:00:00+00:00", "reason": None}

    out = _rank(store, names=["Long Harbour"], forecast=[], date="2026-06-20", provider=full_provider)
    # Long Harbour is dock+buoy+anchoring but carries no holding -> not_ranked; still annotated.
    entries = out["ranked"] + out["not_ranked"]
    lh = next(e for e in entries if e["name"] == "Long Harbour")
    assert lh["availability"]["fully_booked"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_tools.py -k "annotates or no_date or full_outstation" -v`
Expected: FAIL — `find_moorage_near() got an unexpected keyword argument 'date'`.

- [ ] **Step 3: Thread `date`/`provider` through both tools**

In `src/club_moorage_mcp/tools.py`, change `find_moorage_near`'s signature and result building. Replace the existing `find_moorage_near` definition with:

```python
def find_moorage_near(
    store: Store, lat: float, lon: float, radius_nm: float = 20.0,
    clubs: list[str] | None = None, relationship: str | None = None,
    date: str | None = None, provider=None,
) -> dict:
    candidates = [m for m in store.records if _selectable(m, clubs, relationship)]
    hits = within_radius(candidates, lat, lon, radius_nm)
    out = []
    for m, dist in hits:
        row = {
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
        av = _availability_for(m, date, provider)
        if av is not None:
            row["availability"] = av
        out.append(row)
    return {"moorage": out}
```

Then update `rank_moorage` to accept `date`/`provider` and annotate both `ranked` and `not_ranked`. Replace its `return` and the loop tail. Change the signature line to:

```python
def rank_moorage(store: Store, names: list[str], forecast: list[dict], date: str | None = None, provider=None) -> dict:
```

and replace the final `ranked = ...; return {...}` block with:

```python
    ranked = _rank_anchorages(rankable, forecast) if rankable else []

    if date is not None:
        by_name = {n: store.get(n) for n in names}

        def _annotate(entry: dict) -> dict:
            m = by_name.get(entry["name"])
            if m is not None:
                av = _availability_for(m, date, provider)
                if av is not None:
                    entry = {**entry, "availability": av}
            return entry

        ranked = [_annotate(e) for e in ranked]
        not_ranked = [_annotate(e) for e in not_ranked]

    return {"ranked": ranked, "not_ranked": not_ranked, "unknown": unknown}
```

(`_rank_anchorages` returns dicts with a `"name"` key, so name-keyed annotation works for both lists.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_tools.py -v`
Expected: PASS (all tools tests, old and new).

- [ ] **Step 5: Commit**

```bash
git add src/club_moorage_mcp/tools.py tests/test_tools.py
git commit -m "feat: optional date availability annotation on find/rank tools"
```

---

## Task 10: Wire the server — register tool, schemas, provider

Register `check_availability`, add `date` to the two schemas, build the provider once at startup, and thread it through `dispatch`.

**Files:**
- Modify: `src/club_moorage_mcp/server.py`
- Test: `tests/test_server.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_server.py` (match the existing test style in that file — it uses `dispatch`/`tool_list`):

```python
from club_moorage_mcp.server import tool_list, dispatch
from club_moorage_mcp.store import Store


def test_check_availability_registered():
    names = {t.name for t in tool_list()}
    assert "check_availability" in names


def test_find_and_rank_schemas_accept_date():
    schemas = {t.name: t.inputSchema for t in tool_list()}
    assert "date" in schemas["find_moorage_near"]["properties"]
    assert "date" in schemas["rank_moorage"]["properties"]


def test_dispatch_check_availability_without_creds():
    store = Store.load()
    out = dispatch(store, "check_availability", {"name": "Long Harbour", "date": "2026-06-20"})
    # No RVYC creds in the test env -> not configured, but the call must succeed.
    assert out["found"] is True
    assert out["availability"]["reason"] == "live availability not configured"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_server.py -k "registered or accept_date or without_creds" -v`
Expected: FAIL — `check_availability` not in tool list / dispatch raises `Unknown tool`.

- [ ] **Step 3: Register the tool and date params**

In `src/club_moorage_mcp/server.py`:

(a) Add a reusable date schema constant near `_CLUBS`/`_RELATIONSHIP`:

```python
_DATE = {"type": "string",
         "description": "Optional ISO date (YYYY-MM-DD). When set, RVYC reservable outstations are annotated with live slip availability for that day."}
```

(b) In `tool_list()`, add the new tool to the returned list (after `get_moorage`):

```python
        types.Tool(
            name="check_availability",
            description=(
                "Live slip availability for an RVYC reservable outstation on a given date "
                "(Long Harbour, Friday Harbor). Returns total/available slip counts and a "
                "fully_booked flag, or a reason when the outstation is not online-bookable "
                "(e.g. Telegraph Harbour) or no RVYC credentials are configured."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Outstation name, e.g. \"Long Harbour\"."},
                    "date": _DATE,
                },
                "required": ["name", "date"],
            },
        ),
```

(c) Add `"date": _DATE` to the `properties` of both `find_moorage_near` and `rank_moorage` schemas (leave `required` unchanged — date is optional there).

- [ ] **Step 4: Build the provider once and thread it through dispatch**

In `src/club_moorage_mcp/server.py`:

(a) Add the import: `from club_moorage_mcp.rvyc import build_provider`.

(b) Change `dispatch` to accept a provider and pass it where relevant:

```python
def dispatch(store: Store, name: str, args: dict, provider=None) -> dict:
    """Route a tool call to its implementation. Shared by the server and tests."""
    if name == "list_moorage":
        return tools.list_moorage(
            store, clubs=args.get("clubs"), relationship=args.get("relationship"),
        )
    if name == "find_moorage_near":
        return tools.find_moorage_near(
            store, lat=args["lat"], lon=args["lon"],
            radius_nm=args.get("radius_nm", 20.0), clubs=args.get("clubs"),
            relationship=args.get("relationship"),
            date=args.get("date"), provider=provider,
        )
    if name == "get_moorage":
        return tools.get_moorage(store, name=args["name"])
    if name == "rank_moorage":
        return tools.rank_moorage(
            store, names=args["names"], forecast=args.get("forecast", []),
            date=args.get("date"), provider=provider,
        )
    if name == "check_availability":
        return tools.check_availability(
            store, name=args["name"], date=args["date"], provider=provider,
        )
    raise ValueError(f"Unknown tool: {name}")
```

(c) In `build_server`, build the provider once and pass it into dispatch:

```python
def build_server(store: Store) -> Server:
    server = Server("club-moorage-mcp")
    provider = build_provider()

    @server.list_tools()
    async def _list_tools() -> list[types.Tool]:
        return tool_list()

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
        result = dispatch(store, name, arguments or {}, provider=provider)
        return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

    return server
```

(The `dispatch` `provider` defaults to `None`, so existing `test_server.py` calls that pass three args still work and behave as "live layer off".)

- [ ] **Step 5: Run the whole suite**

Run: `uv run pytest -v`
Expected: PASS (all tests across the repo).

- [ ] **Step 6: Commit**

```bash
git add src/club_moorage_mcp/server.py tests/test_server.py
git commit -m "feat: register check_availability + date params; wire RVYC provider"
```

---

## Task 11: Opt-in live smoke test

A single real-network test, skipped unless credentials + `RVYC_LIVE_TEST=1` are set, to verify the whole login→fetch path against the live site on demand. Never runs in CI.

**Files:**
- Create: `tests/test_rvyc_live.py`

- [ ] **Step 1: Write the opt-in test**

Create `tests/test_rvyc_live.py`:

```python
"""Opt-in live smoke test against the real RVYC site.

Runs only when RVYC_USERNAME, RVYC_PASSWORD, and RVYC_LIVE_TEST=1 are all set.
Verifies the self-login + schedule-fetch path end to end. Never runs in CI.
"""

import os
from datetime import date, timedelta

import pytest

from club_moorage_mcp.rvyc import build_provider

pytestmark = pytest.mark.skipif(
    os.environ.get("RVYC_LIVE_TEST") != "1"
    or not os.environ.get("RVYC_USERNAME")
    or not os.environ.get("RVYC_PASSWORD"),
    reason="set RVYC_USERNAME, RVYC_PASSWORD and RVYC_LIVE_TEST=1 to run",
)


def test_long_harbour_live_lookup():
    provider = build_provider()
    assert provider is not None
    target = (date.today() + timedelta(days=8)).isoformat()
    av = provider(783, target, "Long Harbour")
    # Either real numbers came back, or a known degradation reason — never a crash.
    if av["reason"] is None:
        assert av["total_slips"] is not None and av["total_slips"] > 0
        assert 0 <= av["available_slips"] <= av["total_slips"]
    else:
        assert av["reason"] in {"could not sign in to RVYC", "availability lookup failed"}
    # No member names ever surface.
    import json as _json
    assert "REDACTED" not in _json.dumps(av)
```

- [ ] **Step 2: Verify it skips by default**

Run: `uv run pytest tests/test_rvyc_live.py -v`
Expected: SKIPPED (1 skipped).

- [ ] **Step 3: (Optional, manual) run it live**

Only if you have credentials handy:
Run: `RVYC_LIVE_TEST=1 RVYC_USERNAME=... RVYC_PASSWORD=... uv run pytest tests/test_rvyc_live.py -v`
Expected: PASS against the live site.

- [ ] **Step 4: Commit**

```bash
git add tests/test_rvyc_live.py
git commit -m "test: opt-in live RVYC availability smoke test"
```

---

## Task 12: README + version bump

Document the new capability and the credential env vars; bump the package version.

**Files:**
- Modify: `README.md`
- Modify: `pyproject.toml` (version)

- [ ] **Step 1: Document in README**

In `README.md`, add a short section under the tools list (keep the "why" ≤8 lines per repo convention; link the engineering blog only if such an article exists — otherwise omit the link):

```markdown
## Live outstation availability (optional)

`check_availability(name, date)` reports live slip availability for RVYC's two
reservable outstations (Long Harbour, Friday Harbor); `find_moorage_near` and
`rank_moorage` take an optional `date` to annotate results the same way. Telegraph
Harbour is first-come-first-served (booked via the marina) and reciprocal clubs have
no online scheduler, so those return a reason instead of counts.

This layer is **off by default**. Set `RVYC_USERNAME` and `RVYC_PASSWORD` (member
credentials) to enable it; without them the tools return static data plus a
"not configured" note. No credentials or member data are stored in this package.
```

- [ ] **Step 2: Bump the version**

In `pyproject.toml`, change `version = "0.5.0"` to `version = "0.6.0"` (new feature, backward compatible).

- [ ] **Step 3: Run the full suite once more**

Run: `uv run pytest -q`
Expected: PASS, with the live test skipped.

- [ ] **Step 4: Commit**

```bash
git add README.md pyproject.toml
git commit -m "docs: document optional RVYC live availability; bump to v0.6.0"
```

---

## Final verification

- [ ] Run the whole suite: `uv run pytest -q` — all pass, 1 skipped (live test).
- [ ] Confirm the server starts: `uv run python -c "from club_moorage_mcp.server import build_server; from club_moorage_mcp.store import Store; build_server(Store.load()); print('ok')"` — prints `ok` even with no RVYC creds set.
- [ ] Confirm no member-name leakage path: `grep -rn "players" src/club_moorage_mcp/` returns only the parser line that reads `status`, never one that stores names.
