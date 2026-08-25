"""The top-level moorage.geojson is generated — fail if it has drifted from the data."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "ingest"))

from build_geojson import OUT, build  # noqa: E402


def test_geojson_matches_bundled_records():
    assert json.loads(OUT.read_text(encoding="utf-8")) == build(), (
        "moorage.geojson is stale — run: python ingest/build_geojson.py"
    )


def test_every_available_record_with_coords_is_on_the_map():
    from club_moorage_mcp.store import Store

    expected = {
        m.name for m in Store.load().records
        if m.lat is not None and m.lon is not None and m.available is not False
    }
    assert {f["properties"]["name"] for f in build()["features"]} == expected
