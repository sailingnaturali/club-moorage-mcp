from pathlib import Path

from club_moorage_mcp.store import Store
from club_moorage_mcp.tools import list_moorage, find_moorage_near

FIXTURE = Path(__file__).parent / "fixtures" / "data"


def _store():
    return Store.load(FIXTURE)


def test_list_moorage_returns_all():
    out = list_moorage(_store())
    names = sorted(o["name"] for o in out["moorage"])
    assert names == ["Dock Only", "Near Cove"]
    near = next(o for o in out["moorage"] if o["name"] == "Near Cove")
    assert near["max_loa_ft"] == 55
    assert near["mooring_buoys"] == 2


def test_list_moorage_clubs_filter():
    out = list_moorage(_store(), clubs=["ZZ"])
    assert out["moorage"] == []
    out = list_moorage(_store(), clubs=["TC"])
    assert len(out["moorage"]) == 2


def test_find_moorage_near_sorted_with_distance():
    out = find_moorage_near(_store(), lat=48.86, lon=-123.46, radius_nm=60)
    assert out["moorage"][0]["name"] == "Near Cove"
    assert "distance_nm" in out["moorage"][0]
    assert out["moorage"][0]["distance_nm"] <= out["moorage"][-1]["distance_nm"]


from club_moorage_mcp.tools import get_moorage


def test_get_moorage_includes_record_prose_and_club_rules():
    out = get_moorage(_store(), name="near cove")     # case-insensitive
    assert out["found"] is True
    o = out["moorage"]
    assert o["name"] == "Near Cove"
    assert o["pilotbook_anchorage"] == "Welbury Bay (Long Harbour)"
    assert "protected harbour" in o["prose"]
    rules = out["club_rules"]
    assert rules["name"] == "Test Club"
    assert rules["max_nights"] == 3
    assert rules["reciprocal"] is False
    assert "three nights" in rules["rules"]


def test_get_moorage_missing_returns_found_false():
    out = get_moorage(_store(), name="Nowhere")
    assert out["found"] is False
    assert out["name"] == "Nowhere"


def test_get_moorage_unknown_club_omits_rules():
    # an outstation whose club has no club record still resolves, rules None
    store = _store()
    store.records[0].club = "ZZ"
    out = get_moorage(store, name=store.records[0].name)
    assert out["found"] is True
    assert out["club_rules"] is None


from club_moorage_mcp.tools import rank_moorage


def test_rank_moorage_ranks_only_comfort_bearing():
    # SW wind; Near Cove is fully protected (exposed_sectors []), so it scores calm.
    forecast = [{"time": "t", "wind_from_deg": 225, "wind_kn": 20.0,
                 "swell_from_deg": None, "swell_m": None}]
    out = rank_moorage(_store(), names=["Near Cove", "Dock Only"], forecast=forecast)
    ranked_names = [r["name"] for r in out["ranked"]]
    assert ranked_names == ["Near Cove"]
    assert out["ranked"][0]["score"] == 0.0
    not_ranked = {r["name"]: r["reason"] for r in out["not_ranked"]}
    assert "Dock Only" in not_ranked
    assert "dock" in not_ranked["Dock Only"].lower()


def test_rank_moorage_reports_unknown():
    out = rank_moorage(_store(), names=["Ghost Station"], forecast=[])
    assert out["unknown"] == ["Ghost Station"]
    assert out["ranked"] == []


def test_rank_moorage_reason_reflects_anchoring_capability():
    # Real bundled data: Friday Harbor can anchor (moorage includes "anchoring") but
    # has no comfort fields, so its not_ranked reason must NOT call it dock moorage.
    real = Store.load()
    out = rank_moorage(real, names=["Friday Harbor", "Telegraph Harbour"], forecast=[])
    reasons = {r["name"]: r["reason"] for r in out["not_ranked"]}
    assert "dock" not in reasons["Friday Harbor"].lower()      # it can anchor
    assert "dock" in reasons["Telegraph Harbour"].lower()      # truly dock-only


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
