# RVYC outstation live availability — design

**Status:** approved (brainstorming) — ready for implementation planning
**Date:** 2026-06-12
**Repo:** club-moorage-mcp

## Problem

`club-moorage-mcp` serves static yacht-club moorage records. It can tell you *which*
outstation is the best overnight option, but not whether the slips are actually free
on a given night. RVYC's two reservable outstations expose a member-authenticated
JSON booking API (mapped in `infrastructure/docs/rvyc-outstation-booking-api.md`); we
want the MCP to log itself in and answer "here's the best outstation — but it's fully
booked that night."

## Scope

- **In:** read-only day availability for the two RVYC outstations that have an online
  scheduler (Long Harbour, Friday Harbor); a standalone availability tool; optional
  availability annotation on the ranking/proximity tools; scripted self-service login
  with cookie caching; graceful degradation everywhere.
- **Out:** making or modifying bookings (the booking-write endpoints exist but stay
  untouched — never automate a real booking). Browser automation. Surfacing any member
  PII. Availability for Telegraph Harbour (no online scheduler) or reciprocal clubs.

## The three outstations (important)

RVYC has **three** outstations, but only **two** are in the court-booking API:

| Outstation | API court type | How availability is handled |
|---|---|---|
| Long Harbour | 783 | Live-checkable |
| Friday Harbor | 781 | Live-checkable |
| Telegraph Harbour | — (none) | Not online-bookable; first-come-first-served reserved dock space, booked via telegraphharbour.com |

Telegraph Harbour having no live availability is a **property to model, not a bug** —
its result carries a reason pointing at the right booking channel.

## Architecture

A new self-contained module `club_moorage_mcp/rvyc.py`, three units, plus a small data
and model change. Existing `tools.py` / `store.py` / `geo.py` are unchanged except where
noted; the live layer is imported lazily so the package still works with **zero network
and zero credentials**.

New dependency: `httpx`.

### `RvycClient` (HTTP session owner)

- Public method that matters: `day_availability(court_type_id: int, date: str) -> Availability`.
- Login: GET `/login.aspx` → scrape `__VIEWSTATE`, `__VIEWSTATEGENERATOR`,
  `__EVENTVALIDATION` (and the other ASP.NET hidden fields) → POST the WebForms login
  body (username/password under the `...$BaseLogin$UserName` / `$Password` field names,
  plus `$LoginButton`) → keep the `.ASPXFORMSAUTH` cookie. No CAPTCHA on this form.
- Cookie cache: persist the auth cookie to disk (path configurable; default a per-user
  cache file). On a request that 401s, transparently re-login **once** and retry.
- Knows nothing about MCP types or moorage models. Pure HTTP + parse.
- The hand-captured `~/.naturali/rvyc-session.json` becomes a fallback/override for the
  cookie, **not** the primary path — the point of this work is the MCP logging itself in.

### `Availability` (result dataclass)

```
date: str            # ISO, as the agent supplied it
outstation: str
total_slips: int | None
available_slips: int | None
fully_booked: bool | None
checked_at: str | None        # ISO timestamp of the live check
reason: str | None            # set only when the live numbers are null
```

**No member names, ever.** The API `players[]` field is read solely to decide
booked-vs-free for a slip and is then discarded. Nothing derived from it leaves the
process.

### Credential / config resolver

- Reads `RVYC_USERNAME` / `RVYC_PASSWORD` from env.
- If absent, the entire live layer is **inert**: tools return static data with
  `availability` = `null` + reason `"live availability not configured"`. No error.

### Data + model change

- Add `court_type_id: int | None = None` to the `Moorage` dataclass (`models.py`).
- Set it in the two reservable records: `rvyc-long-harbour.md` (783),
  `rvyc-friday-harbor.md` (781). Telegraph Harbour and reciprocals leave it unset.
- The mapping lives in **data, not hardcoded** in `rvyc.py`.

## Availability semantics

For a date, query `GET /api/v1/courts/GetSchedule/{court_type_id}/{YYYYMMDD}/{length}`.
Each `schedule[]` entry is one slip with `blocks[]` of `available`/`booked` status.

- A slip is **free** for the date if it has ≥1 `available` (selectable) block.
- `total_slips` = number of slips; `available_slips` = count of free slips;
  `fully_booked` = `available_slips == 0`.
- The agent passes an **ISO `date`** (`2026-06-20`); the tool converts to the API's
  `YYYYMMDD` internally. ISO dates 400 at the API — conversion is mandatory.
- Booking length: use a nominal length to fetch the grid; slip-level free/booked is read
  from the blocks. (A future refinement could take a desired length/time and report
  whether a specific window is open; out of scope here.)

## Tools

### New: `check_availability(outstation: str, date: str)`

Looks up the record, reads its `court_type_id`, calls `RvycClient.day_availability`,
returns the static record plus the `availability` block. For an outstation with no
`court_type_id`, returns `availability: null` + the appropriate reason (Telegraph
Harbour → `"first-come-first-served; book via telegraphharbour.com"`).

### Changed: `rank_moorage` and `find_moorage_near` gain optional `date`

When `date` is present, after ranking, each result with a `court_type_id` gets its
`availability` block filled in (at most two API calls — cheap). Availability is
**annotation, not a filter**: a fully-booked outstation still appears in the ranking,
flagged full, so the agent can say "best protected option is Long Harbour, but it's
booked that night; next is…".

A short in-process cache keyed `(court_type_id, date)` (~5 min TTL) prevents a
rank-then-check sequence from hitting the API twice.

## Error handling

Every failure degrades to `availability: null` + a `reason`; a tool **never** raises out
of the live layer, and the static moorage answer is never blocked by a live failure.

| Condition | reason | log |
|---|---|---|
| No credentials configured | `live availability not configured` | — |
| Login fails (bad creds / Cloudflare / non-200) | `could not sign in to RVYC` | WARNING + detail |
| API 401 after login | (transparent re-login + retry once; if still failing, as above) | WARNING |
| Unparseable / changed JSON | `availability lookup failed` | WARNING + detail |
| Outstation not online-bookable | `first-come-first-served; book via telegraphharbour.com` | — |

## Testing

- `RvycClient` parsing tested against **saved JSON fixtures** — the real `GetSchedule` /
  `GetSportsWithCourtType` payloads captured 2026-06-11, scrubbed of member names — via
  a mocked httpx transport. No live network in unit tests.
- Parsing: all-booked day → `fully_booked=True`; mixed day → correct `available_slips`;
  the captured June-20 Long Harbour fixture.
- Degradation: no creds, login 401, malformed JSON — each yields the right `null`+reason
  and still returns static data.
- Login flow: feed a captured `login.aspx` form, assert `__VIEWSTATE` scraping + POST
  body assembly.
- One **opt-in live smoke test**, skipped unless `RVYC_USERNAME`/`RVYC_PASSWORD` set and
  `RVYC_LIVE_TEST=1`, to verify against the real site on demand (never runs in CI).

## Privacy / public-package constraints

`club-moorage-mcp` ships public (MIT). The availability code ships **in the public
package**, credential-gated and inert without creds. No credentials, cookies, or member
data in the repo. The booking API endpoints are not secret. Member names from `players[]`
never leave the process. This honours the existing rule that live availability is a local,
opt-in layer over the public static data.
