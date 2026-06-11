#!/usr/bin/env python3
"""Render reciprocals.yaml -> ../src/club_moorage_mcp/data/reciprocals/<slug>.md.

Reciprocal-club records (`relationship: reciprocal`) are too many to hand-author without
drift, so the canonical data lives in reciprocals.yaml and this script emits conforming
markdown (frontmatter + prose) in the same shape as Moorage.from_markdown/to_markdown.
The three RVYC-owned outstations are hand-authored under data/outstations/ instead.

Frontmatter key order is fixed; None / empty / false-by-default fields are dropped so
records round-trip clean. Run:  python ingest/build_records.py
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

HERE = Path(__file__).parent
SRC = HERE / "reciprocals.yaml"
OUT = HERE.parent / "src" / "club_moorage_mcp" / "data" / "reciprocals"

# `relationship` distinguishes a reciprocal club from an RVYC-owned outstation; the rest
# mirrors the club_moorage_mcp.models.Moorage schema.
ORDER = [
    "name", "club", "relationship", "lat", "lon", "coords_approx",
    "region", "locale", "country", "source_url",
    "available", "moorage", "max_loa_ft", "loa_note", "raft_max",
    "power", "water", "vhf", "phone",
    "booking", "reservation_required",
    "free_nights", "nightly_fee", "facility_fee", "max_stay", "insurance_min",
    "fits_vaan", "confidence", "flags", "last_updated",
]

LAST_UPDATED = "2026-06-10"


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return re.sub(r"-+", "-", s)


def drop_empty(rec: dict) -> dict:
    out = {}
    for k in ORDER:
        if k not in rec:
            continue
        v = rec[k]
        if v in (None, "", [], {}):
            continue
        if k in ("coords_approx", "reservation_required") and v is False:
            continue
        out[k] = v
    return out


def render(rec: dict) -> str:
    rec = dict(rec)
    body = (rec.pop("summary", "") or "").strip()
    rec.setdefault("relationship", "reciprocal")
    rec.setdefault("available", True)
    rec.setdefault("last_updated", LAST_UPDATED)
    fm = drop_empty(rec)
    yml = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True, width=100).strip()
    return f"---\n{yml}\n---\n{body}\n"


def main() -> None:
    data = yaml.safe_load(SRC.read_text(encoding="utf-8")) or {}
    records = data.get("records", [])
    OUT.mkdir(parents=True, exist_ok=True)
    known = set(ORDER) | {"summary", "relationship", "available", "last_updated"}
    written = []
    for rec in records:
        unknown = set(rec) - known
        if unknown:
            raise SystemExit(f"{rec.get('name')!r}: unknown field(s) {sorted(unknown)}")
        slug = slugify(rec["name"])
        (OUT / f"{slug}.md").write_text(render(rec), encoding="utf-8")
        written.append(slug)
    print(f"wrote {len(written)} records to {OUT}/")


if __name__ == "__main__":
    main()
