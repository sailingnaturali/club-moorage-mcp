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
