"""club-moorage-mcp server. Exposes yacht-club moorage tools over stdio.

Data directory comes from CLUB_MOORAGE_DATA_PATH (default: bundled package data).
"""

from __future__ import annotations

import asyncio
import json
import logging

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from club_moorage_mcp import tools
from club_moorage_mcp.rvyc import build_provider
from club_moorage_mcp.store import Store

logger = logging.getLogger(__name__)

_FORECAST_STEP = {
    "type": "object",
    "properties": {
        "time": {"type": "string"},
        "wind_from_deg": {"type": "number"},
        "wind_kn": {"type": "number"},
        "swell_from_deg": {"type": ["number", "null"]},
        "swell_m": {"type": ["number", "null"]},
    },
    "required": ["wind_from_deg", "wind_kn"],
}

_CLUBS = {"type": "array", "items": {"type": "string"},
          "description": "Optional club-code filter, e.g. [\"RVYC\"]. Omit for all clubs."}

_RELATIONSHIP = {
    "type": "string",
    "enum": ["outstation", "reciprocal"],
    "description": (
        "Optional filter. 'outstation' = an RVYC-owned facility (members only); "
        "'reciprocal' = a partner club that hosts visiting RVYC members. Omit for both."
    ),
}

_DATE = {"type": "string",
         "description": "Optional ISO date (YYYY-MM-DD). When set, RVYC reservable outstations are annotated with live slip availability for that day."}


def tool_list() -> list[types.Tool]:
    return [
        types.Tool(
            name="list_moorage",
            description=(
                "All club moorage records with location and size limits — RVYC-owned "
                "outstations and partner-club reciprocals. Discontinued reciprocals are omitted."
            ),
            inputSchema={
                "type": "object",
                "properties": {"clubs": _CLUBS, "relationship": _RELATIONSHIP},
            },
        ),
        types.Tool(
            name="find_moorage_near",
            description=(
                "Club moorage within a radius of a position, nearest first — RVYC outstations "
                "and reciprocal partner clubs. Discontinued reciprocals are omitted."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "lat": {"type": "number"},
                    "lon": {"type": "number"},
                    "radius_nm": {"type": "number", "description": "Search radius in nautical miles (default 20)."},
                    "clubs": _CLUBS,
                    "relationship": _RELATIONSHIP,
                    "date": _DATE,
                },
                "required": ["lat", "lon"],
            },
        ),
        types.Tool(
            name="get_moorage",
            description="Full record and prose for one named moorage, plus (for outstations) its club's general rules.",
            inputSchema={
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        ),
        types.Tool(
            name="check_availability",
            description=(
                "Live slip availability for an RVYC reservable outstation on a given date "
                "(Long Harbour, Friday Harbor). Returns total/available slip counts and a "
                "fully_booked flag, or a reason when the outstation is not online-bookable "
                "(e.g. Telegraph Harbour) or no RVYC credentials are configured."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Outstation name, e.g. \"Long Harbour\"."},
                    "date": _DATE,
                },
                "required": ["name", "date"],
            },
        ),
        types.Tool(
            name="rank_moorage",
            description=(
                "Rank overnight-capable moorage by comfort against a forecast (same scoring "
                "as pilotbook rank_anchorages). Dock-only records are returned under not_ranked. "
                "Fetch the forecast from weather-mcp (steps with wind_from_deg, wind_kn, "
                "swell_from_deg, swell_m)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "names": {"type": "array", "items": {"type": "string"}},
                    "forecast": {"type": "array", "items": _FORECAST_STEP},
                    "date": _DATE,
                },
                "required": ["names", "forecast"],
            },
        ),
    ]


def dispatch(store: Store, name: str, args: dict, provider=None) -> dict:
    """Route a tool call to its implementation. Shared by the server and tests."""
    if name == "list_moorage":
        return tools.list_moorage(
            store, clubs=args.get("clubs"), relationship=args.get("relationship"),
        )
    if name == "find_moorage_near":
        return tools.find_moorage_near(
            store, lat=args["lat"], lon=args["lon"],
            radius_nm=args.get("radius_nm", 20.0), clubs=args.get("clubs"),
            relationship=args.get("relationship"),
            date=args.get("date"), provider=provider,
        )
    if name == "get_moorage":
        return tools.get_moorage(store, name=args["name"])
    if name == "rank_moorage":
        return tools.rank_moorage(
            store, names=args["names"], forecast=args.get("forecast", []),
            date=args.get("date"), provider=provider,
        )
    if name == "check_availability":
        return tools.check_availability(
            store, name=args["name"], date=args["date"], provider=provider,
        )
    raise ValueError(f"Unknown tool: {name}")


def build_server(store: Store) -> Server:
    server = Server("club-moorage-mcp")
    provider = build_provider()

    @server.list_tools()
    async def _list_tools() -> list[types.Tool]:
        return tool_list()

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
        result = dispatch(store, name, arguments or {}, provider=provider)
        return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

    return server


async def _run() -> None:
    store = Store.load()
    logger.info("loaded %d moorage records from %s", len(store.records), store.root)
    server = build_server(store)
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_run())


if __name__ == "__main__":
    main()
