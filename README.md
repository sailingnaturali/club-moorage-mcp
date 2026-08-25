# club-moorage-mcp

MCP server serving yacht-club **moorage** records — size limits, rafting rules, booking
processes, amenities, reciprocal terms, and overnight-comfort ranking. Each record carries
a `relationship`:

- **`outstation`** — a facility the club owns for its own members. Ships bundled with the
  three Royal Victoria Yacht Club (RVYC) outstations (Long Harbour, Friday Harbor,
  Telegraph Harbour).
- **`reciprocal`** — a partner club that hosts visiting RVYC members as guests, with its own
  visitor terms (free nights, fees, max stay, insurance minimum). Ships bundled with the
  **whole RVYC reciprocal list — 137 clubs, worldwide**, in two depths:
  - **Researched** (`confidence` med/high, 45 clubs) — the BC + Washington coastal set the
    boat actually cruises: South Vancouver Island, the Gulf Islands, the Vancouver-side
    crossing stops, the San Juans / Anacortes / Bellingham, the Strait of Juan de Fuca /
    North Puget Sound. Per-club terms, fees, size limits and Vaan fit.
  - **Listed only** (`confidence: low`, 92 clubs) — everything else on the list: California,
    Hawaii, Mexico, Bermuda, the Caribbean, eastern Canada, the UK, Australia/NZ and the
    rest. Position, address, phone and website only, so a passage plan can ask "whose club
    is in this port?" — guest-moorage terms are **not** researched and every record says so.

## Tools

- `list_moorage(clubs?, relationship?)` — all moorage: location, coords, size limits.
- `find_moorage_near(lat, lon, radius_nm=20, clubs?, relationship?, date?)` — nearby moorage, nearest first; annotates live availability when configured.
- `get_moorage(name)` — full record + prose; for an outstation, also the club's general rules.
- `rank_moorage(names, forecast, date?)` — overnight-comfort rank for records that
  support anchoring/mooring; dock-only records are returned under `not_ranked`.
  Reuses pilotbook-mcp's scoring against a weather-mcp forecast.
- `check_availability(name, date)` — live slip availability for RVYC reservable outstations; requires `RVYC_USERNAME`/`RVYC_PASSWORD`.

The `clubs` filter is an optional list of club codes (e.g. `["RVYC"]`); omit for all clubs.
The `relationship` filter is `"outstation"` or `"reciprocal"`; omit for both. The
agent/context layer decides which clubs are relevant from who is aboard. Discontinued
reciprocals (`available: false`) are omitted from `list`/`find` but still resolve by name.

## Live outstation availability (optional)

`check_availability(name, date)` reports live slip availability for RVYC's two
reservable outstations (Long Harbour, Friday Harbor); `find_moorage_near` and
`rank_moorage` take an optional `date` to annotate results the same way. Telegraph
Harbour is first-come-first-served (booked via the marina) and reciprocal clubs have
no online scheduler, so those return a reason instead of counts.

This layer is **off by default**. Set `RVYC_USERNAME` and `RVYC_PASSWORD` (member
credentials) to enable it; without them the tools return static data plus a
"not configured" note. No credentials or member data are stored in this package.

## Data

Records are markdown (YAML frontmatter + prose) under `src/club_moorage_mcp/data/`
(`clubs/`, `outstations/`, `reciprocals/`). Point at a different directory with
`CLUB_MOORAGE_DATA_PATH`. `pilotbook_anchorage` cross-links a record to the nearest
pilot-book anchorage; the agent calls pilotbook-mcp's `get_anchorage` for seabed/depth.

[**moorage.geojson**](moorage.geojson) is a generated map of every bundled record —
GitHub renders it inline (blue = outstation, green = reciprocal). Regenerate after a data
change with `uv run python ingest/build_geojson.py`; `--check` fails on drift, and
`tests/test_geojson.py` does the same in CI.

Reciprocal records are generated from `ingest/reciprocals.yaml` — edit the YAML, then
`uv run python ingest/build_records.py`. The three RVYC outstations are hand-authored.
The club list is the RVYC 2024 Annual; positions and contacts are RVYC's own reciprocal
map. Per-club terms were researched from secondary sources where they exist at all;
**verify fees, LOA, and availability with the club before arrival.**

## Install

    uv sync --dev

## Run the server

    uv run club-moorage-mcp
