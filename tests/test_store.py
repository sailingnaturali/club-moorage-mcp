from pathlib import Path

from outstations_mcp.store import Store

FIXTURE = Path(__file__).parent / "fixtures" / "data"


def _store():
    return Store.load(FIXTURE)


def test_loads_outstations_and_clubs():
    s = _store()
    names = sorted(o.name for o in s.outstations)
    assert names == ["Dock Only", "Near Cove"]
    assert s.clubs["TC"].name == "Test Club"


def test_get_outstation_is_case_insensitive():
    s = _store()
    assert s.get("near cove").name == "Near Cove"
    assert s.get("Nope") is None


def test_get_club():
    s = _store()
    assert s.get_club("TC").max_nights == 3
    assert s.get_club("ZZ") is None
