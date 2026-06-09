from pathlib import Path

from outstations_mcp.store import Store
from outstations_mcp.tools import list_outstations, find_outstations_near

FIXTURE = Path(__file__).parent / "fixtures" / "data"


def _store():
    return Store.load(FIXTURE)


def test_list_outstations_returns_all():
    out = list_outstations(_store())
    names = sorted(o["name"] for o in out["outstations"])
    assert names == ["Dock Only", "Near Cove"]
    near = next(o for o in out["outstations"] if o["name"] == "Near Cove")
    assert near["max_loa_ft"] == 55
    assert near["mooring_buoys"] == 2


def test_list_outstations_clubs_filter():
    out = list_outstations(_store(), clubs=["ZZ"])
    assert out["outstations"] == []
    out = list_outstations(_store(), clubs=["TC"])
    assert len(out["outstations"]) == 2


def test_find_outstations_near_sorted_with_distance():
    out = find_outstations_near(_store(), lat=48.86, lon=-123.46, radius_nm=60)
    assert out["outstations"][0]["name"] == "Near Cove"
    assert "distance_nm" in out["outstations"][0]
    assert out["outstations"][0]["distance_nm"] <= out["outstations"][-1]["distance_nm"]
