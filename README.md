# outstations-mcp

MCP server serving yacht-club **moorage** records — size limits, rafting rules, booking
processes, amenities, reciprocal terms, and overnight-comfort ranking. Each record carries
a `relationship`:

- **`outstation`** — a facility the club owns for its own members. Ships bundled with the
  three Royal Victoria Yacht Club (RVYC) outstations (Long Harbour, Friday Harbor,
  Telegraph Harbour).
- **`reciprocal`** — a partner club that hosts visiting RVYC members as guests, with its own
  visitor terms (free nights, fees, max stay, insurance minimum). Ships bundled with the
  BC + Washington cruising-grounds tranche (18 clubs across South Vancouver Island, the Gulf
  Islands, and the San Juans / Anacortes / Blaine).

## Tools

- `list_outstations(clubs?, relationship?)` — all moorage: location, coords, size limits.
- `find_outstations_near(lat, lon, radius_nm=20, clubs?, relationship?)` — nearby moorage, nearest first.
- `get_outstation(name)` — full record + prose; for an outstation, also the club's general rules.
- `rank_outstations(names, forecast)` — overnight-comfort rank for records that
  support anchoring/mooring; dock-only records are returned under `not_ranked`.
  Reuses pilotbook-mcp's scoring against a weather-mcp forecast.

The `clubs` filter is an optional list of club codes (e.g. `["RVYC"]`); omit for all clubs.
The `relationship` filter is `"outstation"` or `"reciprocal"`; omit for both. The
agent/context layer decides which clubs are relevant from who is aboard. Discontinued
reciprocals (`available: false`) are omitted from `list`/`find` but still resolve by name.

## Data

Records are markdown (YAML frontmatter + prose) under `src/outstations_mcp/data/`
(`clubs/`, `outstations/`, `reciprocals/`). Point at a different directory with
`OUTSTATIONS_DATA_PATH`. `pilotbook_anchorage` cross-links a record to the nearest
pilot-book anchorage; the agent calls pilotbook-mcp's `get_anchorage` for seabed/depth.

Reciprocal records are generated from `ingest/reciprocals.yaml` — edit the YAML, then
`uv run python ingest/build_records.py`. The three RVYC outstations are hand-authored.
Per-club reciprocal terms were researched from secondary sources; **verify fees, LOA, and
availability with the club before arrival.**

## Install

    uv sync --dev

## Run the server

    uv run outstations-mcp
