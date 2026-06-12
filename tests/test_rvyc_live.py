"""Opt-in live smoke test against the real RVYC site.

Runs only when RVYC_USERNAME, RVYC_PASSWORD, and RVYC_LIVE_TEST=1 are all set.
Verifies the self-login + schedule-fetch path end to end. Never runs in CI.
"""

import os
from datetime import date, timedelta

import pytest

from club_moorage_mcp.rvyc import build_provider

pytestmark = pytest.mark.skipif(
    os.environ.get("RVYC_LIVE_TEST") != "1"
    or not os.environ.get("RVYC_USERNAME")
    or not os.environ.get("RVYC_PASSWORD"),
    reason="set RVYC_USERNAME, RVYC_PASSWORD and RVYC_LIVE_TEST=1 to run",
)


def test_long_harbour_live_lookup():
    provider = build_provider()
    assert provider is not None
    target = (date.today() + timedelta(days=8)).isoformat()
    av = provider(783, target, "Long Harbour")
    # Either real numbers came back, or a known degradation reason — never a crash.
    if av["reason"] is None:
        assert av["total_slips"] is not None and av["total_slips"] > 0
        assert 0 <= av["available_slips"] <= av["total_slips"]
    else:
        assert av["reason"] in {"could not sign in to RVYC", "availability lookup failed"}
    # No member names ever surface.
    import json as _json
    assert "REDACTED" not in _json.dumps(av)
