"""Reciprocal-club records (relationship: reciprocal) loaded from bundled data."""

from club_moorage_mcp.store import Store
from club_moorage_mcp.tools import (
    find_moorage_near,
    get_moorage,
    list_moorage,
)


def test_find_near_nanaimo_returns_reciprocal_club():
    s = Store.load()
    out = find_moorage_near(s, lat=49.1771, lon=-123.9426, radius_nm=5)
    nyc = next(o for o in out["moorage"] if o["name"] == "Nanaimo Yacht Club")
    assert nyc["relationship"] == "reciprocal"
    assert nyc["free_nights"] == 2
    assert nyc["fits_vaan"] is True


def test_relationship_filter_separates_owned_from_reciprocal():
    s = Store.load()
    owned = list_moorage(s, relationship="outstation")["moorage"]
    recip = list_moorage(s, relationship="reciprocal")["moorage"]
    assert {o["name"] for o in owned} == {"Friday Harbor", "Long Harbour", "Telegraph Harbour"}
    assert len(recip) == 44        # 45 loaded, minus discontinued Deep Bay (available: false)
    assert all(o["relationship"] == "reciprocal" for o in recip)


def test_royal_vancouver_is_not_coded_as_royal_victoria():
    # "RVYC" is Royal VICTORIA (the host club). Royal VANCOUVER must use a different code,
    # or a clubs=["RVYC"] filter would wrongly sweep it in.
    s = Store.load()
    rvan = s.get("Royal Vancouver Yacht Club")
    assert rvan is not None
    assert rvan.club == "RVANYC"
    assert rvan.club != "RVYC"


def test_discontinued_reciprocal_excluded_from_list_and_find_but_gettable():
    s = Store.load()
    # Deep Bay's reciprocal ended Jan 2026 (available: false) — not a place you can moor now.
    listed = {o["name"] for o in list_moorage(s)["moorage"]}
    assert "Deep Bay Yacht Club" not in listed
    near = find_moorage_near(s, lat=49.4645, lon=-124.7259, radius_nm=10)
    assert "Deep Bay Yacht Club" not in {o["name"] for o in near["moorage"]}
    # but a direct lookup still explains why it's gone
    got = get_moorage(s, name="Deep Bay Yacht Club")
    assert got["found"] is True
    assert got["moorage"]["available"] is False


def test_get_reciprocal_has_no_club_rules_record():
    # Reciprocal terms live on the record itself; there's no Club record for partner clubs.
    s = Store.load()
    got = get_moorage(s, name="Orcas Island Yacht Club")
    assert got["found"] is True
    o = got["moorage"]
    assert o["relationship"] == "reciprocal"
    assert o["power"] is False and o["water"] is False     # anchor-out comfort, no services
    assert got["club_rules"] is None
