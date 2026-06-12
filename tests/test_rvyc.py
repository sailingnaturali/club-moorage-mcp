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


from club_moorage_mcp.rvyc import build_login_form


def test_build_login_form_includes_hidden_and_credentials():
    html = (FIX / "login_form.html").read_text()
    form = build_login_form(html, "myuser", "mypass")
    assert form["__VIEWSTATE"] == "VS_TOKEN_ABC"
    assert form["__VIEWSTATEGENERATOR"] == "GEN123"
    assert form["__EVENTVALIDATION"] == "EV_TOKEN_XYZ"
    user_key = next(k for k in form if k.endswith("$UserName"))
    pass_key = next(k for k in form if k.endswith("$Password"))
    assert form[user_key] == "myuser"
    assert form[pass_key] == "mypass"
    assert any(k.endswith("$LoginButton") for k in form)


def test_build_login_form_raises_without_username_field():
    with pytest.raises(ValueError):
        build_login_form("<html><form></form></html>", "u", "p")


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
    assert logins["n"] == 1


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
    assert fetches["n"] == 1
