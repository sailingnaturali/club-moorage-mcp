from club_moorage_mcp.geo import within_radius
from club_moorage_mcp.models import Moorage


def _stations():
    return [
        Moorage(name="Near Cove", club="TC", lat=48.86, lon=-123.46),
        Moorage(name="Dock Only", club="TC", lat=48.53, lon=-123.01),
        Moorage(name="No Coords", club="TC"),
    ]


def test_within_radius_sorted_nearest_first():
    hits = within_radius(_stations(), 48.86, -123.46, radius_nm=10)
    assert [o.name for o, _ in hits] == ["Near Cove"]
    assert hits[0][1] < 0.1          # essentially zero distance


def test_within_radius_wider_includes_more_sorted():
    hits = within_radius(_stations(), 48.86, -123.46, radius_nm=60)
    assert [o.name for o, _ in hits] == ["Near Cove", "Dock Only"]
    assert hits[0][1] < hits[1][1]


def test_within_radius_skips_missing_coords():
    hits = within_radius(_stations(), 48.86, -123.46, radius_nm=10000)
    assert "No Coords" not in [o.name for o, _ in hits]
