from club_moorage_mcp.store import Store


def test_bundled_data_has_three_rvyc_outstations():
    s = Store.load()                      # default = bundled package data
    owned = sorted(o.name for o in s.outstations if (o.relationship or "outstation") == "outstation")
    assert owned == ["Friday Harbor", "Long Harbour", "Telegraph Harbour"]
    assert "RVYC" in s.clubs
    assert s.clubs["RVYC"].reciprocal is False
    assert s.clubs["RVYC"].max_nights == 3


def test_bundled_data_includes_reciprocal_clubs():
    s = Store.load()
    reciprocals = [o for o in s.outstations if o.relationship == "reciprocal"]
    assert len(reciprocals) == 45                          # BC+WA: charter core + crossing/Strait tranche
    nanaimo = s.get("Nanaimo Yacht Club")
    assert nanaimo.relationship == "reciprocal"
    assert nanaimo.club == "NYC"                            # the partner club's own code, not RVYC
    assert nanaimo.free_nights == 2
    assert nanaimo.fits_vaan is True


def test_long_harbour_is_overnight_capable():
    s = Store.load()
    lh = s.get("Long Harbour")
    assert lh.holding is not None                 # rankable
    assert lh.mooring_buoys == 2
    assert lh.max_loa_ft == 55
    assert lh.pilotbook_anchorage == "Welbury Bay (Long Harbour)"


def test_dock_only_stations_have_no_holding():
    s = Store.load()
    assert s.get("Friday Harbor").holding is None
    assert s.get("Telegraph Harbour").holding is None
    assert s.get("Telegraph Harbour").vhf_channel == "66"
