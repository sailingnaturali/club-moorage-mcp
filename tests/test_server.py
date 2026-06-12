from pathlib import Path

from club_moorage_mcp.server import dispatch, tool_list
from club_moorage_mcp.store import Store

FIXTURE = Path(__file__).parent / "fixtures" / "data"


def _store():
    return Store.load(FIXTURE)


def test_tool_list_advertises_five_tools():
    names = {t.name for t in tool_list()}
    assert names == {
        "list_moorage", "find_moorage_near", "get_moorage", "rank_moorage", "check_availability",
    }


def test_dispatch_routes_find():
    out = dispatch(_store(), "find_moorage_near", {"lat": 48.86, "lon": -123.46, "radius_nm": 60})
    assert out["moorage"][0]["name"] == "Near Cove"


def test_dispatch_routes_get():
    out = dispatch(_store(), "get_moorage", {"name": "Near Cove"})
    assert out["found"] is True


def test_dispatch_unknown_tool_raises():
    import pytest
    with pytest.raises(ValueError):
        dispatch(_store(), "nope", {})


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
    assert out["found"] is True
    assert out["availability"]["reason"] == "live availability not configured"
