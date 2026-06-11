from pathlib import Path

from club_moorage_mcp.server import dispatch, tool_list
from club_moorage_mcp.store import Store

FIXTURE = Path(__file__).parent / "fixtures" / "data"


def _store():
    return Store.load(FIXTURE)


def test_tool_list_advertises_four_tools():
    names = {t.name for t in tool_list()}
    assert names == {
        "list_outstations", "find_outstations_near", "get_outstation", "rank_outstations",
    }


def test_dispatch_routes_find():
    out = dispatch(_store(), "find_outstations_near", {"lat": 48.86, "lon": -123.46, "radius_nm": 60})
    assert out["outstations"][0]["name"] == "Near Cove"


def test_dispatch_routes_get():
    out = dispatch(_store(), "get_outstation", {"name": "Near Cove"})
    assert out["found"] is True


def test_dispatch_unknown_tool_raises():
    import pytest
    with pytest.raises(ValueError):
        dispatch(_store(), "nope", {})
