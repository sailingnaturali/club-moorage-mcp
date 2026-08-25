#!/usr/bin/env python3
"""Render the bundled moorage records -> ../moorage.geojson (GitHub renders it as a map).

The top-level file is generated, never hand-edited: run `python ingest/build_geojson.py`
after changing data, or `--check` (CI/tests) to fail when it has drifted.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from club_moorage_mcp.store import Store

OUT = Path(__file__).parent.parent / "moorage.geojson"

# GitHub's map reads marker-color/-size/-symbol and pops up the other properties.
COLORS = {"outstation": "#1f78b4", "reciprocal": "#33a02c"}


def build() -> dict:
    features = []
    for m in sorted(Store.load().records, key=lambda m: m.name):
        if m.lat is None or m.lon is None or m.available is False:
            continue
        rel = m.relationship or "outstation"
        props = {
            "name": m.name,
            "club": m.club,
            "relationship": rel,
            "locale": m.locale or m.island,
            "moorage": ", ".join(m.moorage) or None,
            "max_loa_ft": m.max_loa_ft,
            "free_nights": m.free_nights,
            "source_url": m.source_url,
            "confidence": m.confidence,   # 'low' == listed by RVYC, terms not researched
            "marker-color": COLORS.get(rel, "#888888"),
            "marker-size": "medium",
        }
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [m.lon, m.lat]},
            "properties": {k: v for k, v in props.items() if v is not None},
        })
    return {"type": "FeatureCollection", "features": features}


def main() -> None:
    text = json.dumps(build(), indent=2, ensure_ascii=False) + "\n"
    if "--check" in sys.argv:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            raise SystemExit(f"{OUT.name} is stale — run: python ingest/build_geojson.py")
        print(f"{OUT.name} is up to date.")
        return
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {len(build()['features'])} features to {OUT}")


if __name__ == "__main__":
    main()
