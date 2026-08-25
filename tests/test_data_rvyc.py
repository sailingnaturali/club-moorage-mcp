from club_moorage_mcp.store import Store


def test_bundled_data_has_three_rvyc_outstations():
    s = Store.load()                      # default = bundled package data
    owned = sorted(o.name for o in s.records if (o.relationship or "outstation") == "outstation")
    assert owned == ["Friday Harbor", "Long Harbour", "Telegraph Harbour"]
    assert "RVYC" in s.clubs
    assert s.clubs["RVYC"].reciprocal is False
    assert s.clubs["RVYC"].max_nights == 3


def test_bundled_data_includes_reciprocal_clubs():
    s = Store.load()
    reciprocals = [o for o in s.records if o.relationship == "reciprocal"]
    assert len(reciprocals) == 138                         # the full RVYC 2024 Annual list
    nanaimo = s.get("Nanaimo Yacht Club")
    assert nanaimo.relationship == "reciprocal"
    assert nanaimo.club == "NYC"                            # the partner club's own code, not RVYC
    assert nanaimo.free_nights == 2
    assert nanaimo.fits_vaan is True


def test_reciprocals_cover_the_route_home_not_just_the_pnw():
    # The list is worldwide — the delivery route home passes several of these.
    s = Store.load()
    by_region = {o.region for o in s.records if o.relationship == "reciprocal"}
    assert {"California", "Hawaii", "Mexico", "Bermuda", "Caribbean"} <= by_region
    assert s.get("San Diego Yacht Club").country == "US"
    assert s.get("Club de Yates de Acapulco").country == "MX"


def test_every_reciprocal_is_mappable_and_uniquely_coded():
    # No coords = invisible to find_moorage_near and to moorage.geojson; a duplicate club
    # code would make a clubs=[...] filter sweep in someone else's club.
    s = Store.load()
    assert [o.name for o in s.records if o.lat is None or o.lon is None] == []
    codes = [o.club for o in s.records if o.relationship == "reciprocal"]
    assert len(codes) == len(set(codes))


def test_no_two_clubs_share_a_pin():
    # Two clubs on one pin means a record inherited someone else's position — how Channel
    # Islands YC (Oxnard) landed on Royal Channel Islands YC's Guernsey pin. The one real
    # pair: Roche Harbor YC's reciprocal moorage IS Bremerton Marina, Bremerton YC's dock.
    s = Store.load()
    seen: dict[tuple, str] = {}
    shared = []
    for m in s.records:
        if m.lat is None:
            continue
        key = (round(m.lat, 4), round(m.lon, 4))
        if key in seen:
            shared.append(tuple(sorted((seen[key], m.name))))
        seen[key] = m.name
    assert shared == [("Bremerton Yacht Club", "Roche Harbor Yacht Club")]


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
