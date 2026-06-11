from club_moorage_mcp.models import Outstation, Club

OUTSTATION_MD = """---
name: Near Cove
club: TC
lat: 48.86
lon: -123.46
region: Test Region
island: Test Island
moorage: [dock, mooring_buoys, anchoring]
max_loa_ft: 55
raft_max: 2
mooring_buoys: 2
shore_power: 15/30A free
potable_water: false
amenities: [kitchen, showers]
booking: club-online
pilotbook_anchorage: Welbury Bay (Long Harbour)
exposed_sectors: []
holding: good
swing_room: adequate
last_updated: '2025'
confidence: high
---
Near Cove sits at the head of a protected harbour.
"""

CLUB_MD = """---
club: TC
name: Test Club
source_url: https://example.test/outstations
max_nights: 3
checkout: '1200'
quiet_hours: 2200-0800
burgee_required: true
reciprocal: false
---
Stay limited to three nights. Quiet hours 2200-0800.
"""


def test_outstation_roundtrip_is_stable():
    o = Outstation.from_markdown(OUTSTATION_MD)
    assert o.name == "Near Cove"
    assert o.club == "TC"
    assert o.moorage == ["dock", "mooring_buoys", "anchoring"]
    assert o.max_loa_ft == 55
    assert o.holding == "good"
    assert o.exposed_sectors == []
    assert "head of a protected harbour" in o.prose
    # round-trip and re-parse equals the first parse
    assert Outstation.from_markdown(o.to_markdown()) == o


def test_outstation_drops_none_and_empty_from_frontmatter():
    o = Outstation(name="Bare", club="TC")
    md = o.to_markdown()
    assert "name: Bare" in md
    assert "lat:" not in md          # None dropped
    assert "amenities:" not in md     # [] dropped
    assert "prose" not in md          # prose never in frontmatter


def test_club_roundtrip():
    c = Club.from_markdown(CLUB_MD)
    assert c.club == "TC"
    assert c.name == "Test Club"
    assert c.max_nights == 3
    assert c.reciprocal is False
    assert "three nights" in c.prose
    assert Club.from_markdown(c.to_markdown()) == c
