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


from outstations_mcp.tools import get_outstation


def test_get_outstation_includes_record_prose_and_club_rules():
    out = get_outstation(_store(), name="near cove")     # case-insensitive
    assert out["found"] is True
    o = out["outstation"]
    assert o["name"] == "Near Cove"
    assert o["pilotbook_anchorage"] == "Welbury Bay (Long Harbour)"
    assert "protected harbour" in o["prose"]
    rules = out["club_rules"]
    assert rules["name"] == "Test Club"
    assert rules["max_nights"] == 3
    assert rules["reciprocal"] is False
    assert "three nights" in rules["rules"]


def test_get_outstation_missing_returns_found_false():
    out = get_outstation(_store(), name="Nowhere")
    assert out["found"] is False
    assert out["name"] == "Nowhere"


def test_get_outstation_unknown_club_omits_rules():
    # an outstation whose club has no club record still resolves, rules None
    store = _store()
    store.outstations[0].club = "ZZ"
    out = get_outstation(store, name=store.outstations[0].name)
    assert out["found"] is True
    assert out["club_rules"] is None


from outstations_mcp.tools import rank_outstations


def test_rank_outstations_ranks_only_comfort_bearing():
    # SW wind; Near Cove is fully protected (exposed_sectors []), so it scores calm.
    forecast = [{"time": "t", "wind_from_deg": 225, "wind_kn": 20.0,
                 "swell_from_deg": None, "swell_m": None}]
    out = rank_outstations(_store(), names=["Near Cove", "Dock Only"], forecast=forecast)
    ranked_names = [r["name"] for r in out["ranked"]]
    assert ranked_names == ["Near Cove"]
    assert out["ranked"][0]["score"] == 0.0
    not_ranked = {r["name"]: r["reason"] for r in out["not_ranked"]}
    assert "Dock Only" in not_ranked
    assert "dock" in not_ranked["Dock Only"].lower()


def test_rank_outstations_reports_unknown():
    out = rank_outstations(_store(), names=["Ghost Station"], forecast=[])
    assert out["unknown"] == ["Ghost Station"]
    assert out["ranked"] == []
