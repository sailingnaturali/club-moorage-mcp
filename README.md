# outstations-mcp

MCP server serving yacht-club **outstation** records — member-moorage facilities with
size limits, rafting rules, booking processes, amenities, and overnight-comfort
ranking. Ships bundled with the three Royal Victoria Yacht Club (RVYC) outstations
(Long Harbour, Friday Harbor, Telegraph Harbour).

## Tools

- `list_outstations(clubs?)` — all stations: location, coords, size limits.
- `find_outstations_near(lat, lon, radius_nm=20, clubs?)` — nearby stations, nearest first.
- `get_outstation(name)` — full record + prose + the club's general rules.
- `rank_outstations(names, forecast)` — overnight-comfort rank for stations that
  support anchoring/mooring; dock-only stations are returned under `not_ranked`.
  Reuses pilotbook-mcp's scoring against a weather-mcp forecast.

The `clubs` filter is an optional list of club codes (e.g. `["RVYC"]`); omit for all
clubs. The agent/context layer decides which clubs are relevant from who is aboard.

## Data

Records are markdown (YAML frontmatter + prose) under `src/outstations_mcp/data/`
(`clubs/` and `outstations/`). Point at a different directory with
`OUTSTATIONS_DATA_PATH`. `pilotbook_anchorage` cross-links a station to the nearest
pilot-book anchorage; the agent calls pilotbook-mcp's `get_anchorage` for seabed/depth.

## Install

    uv sync --dev

## Run the server

    uv run outstations-mcp
