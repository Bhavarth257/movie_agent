"""Phase 3 check: differently worded requests must produce the right job.

Calls the real Claude API (Haiku: well under ₹1 for all cases). Run with:
    RUN_LIVE=1 PYTHONPATH= .venv/bin/python -m pytest -q tests/test_intake_live.py
"""

import asyncio
import os

import anthropic
import pytest

from intake_cases import CASES, CATALOG, TODAY, VENUES, check
from movie_agent import config  # noqa: F401  (loads .env)
from movie_agent.intake import parse_request

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not os.environ.get("RUN_LIVE"), reason="set RUN_LIVE=1 to call the Claude API"),
]


@pytest.mark.parametrize("message,expected", CASES, ids=[c[0][:40] for c in CASES])
def test_request_becomes_right_job(message, expected):
    client = anthropic.AsyncAnthropic()
    model = os.environ.get("CLAUDE_MODEL", "claude-haiku-5-5")
    spec = asyncio.run(
        parse_request(client, model, message, today=TODAY, city="vellore", catalog=CATALOG, venues=VENUES)
    )
    check(spec, expected)
