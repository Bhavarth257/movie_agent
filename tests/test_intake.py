from datetime import date

from movie_agent.bms import Movie
from movie_agent.intake import build_prompt, validate
from movie_agent.jobs import JobSpec

TODAY = date(2026, 11, 1)  # a Sunday
CATALOG = [Movie("vellore", "jailer-2", "ET00518674"), Movie("vellore", "cult", "ET00524017")]
VENUES = [("PVYS", "PVR: Velocity, Silk Mill, Gandhi Nagar"), ("IOSE", "INOX: Selvam Square, Vellore")]


def spec(**kw) -> JobSpec:
    base = dict(
        movie_title="Jailer 2", et_code="ET00518674", movie_slug="jailer-2", city="vellore",
        venue_codes=["PVYS"], date="20261106", time_from="16:00", time_to="20:00", screens=[],
        tickets=2, seat_pref="middle", max_price=500, clarify=None,
    )
    return JobSpec(**{**base, **kw})


def check(s: JobSpec, link=None) -> JobSpec:
    return validate(s, today=TODAY, catalog=CATALOG, venues=VENUES, link=link)


def test_valid_job_passes_unchanged():
    s = spec()
    assert check(s) == s


def test_invented_movie_code_is_dropped_and_link_requested():
    out = check(spec(et_code="ET99999999"))
    assert (out.et_code, out.movie_slug) == (None, None)
    assert "BookMyShow link" in out.clarify


def test_pasted_link_counts_as_known():
    link = Movie("vellore", "new-film", "ET00600000")
    out = check(spec(et_code="ET00600000", movie_slug="new-film"), link=link)
    assert out.et_code == "ET00600000" and out.clarify is None


def test_unknown_theatre_codes_removed():
    assert check(spec(venue_codes=["IOSE", "XXXX", "PVYS"])).venue_codes == ["IOSE", "PVYS"]


def test_past_date_bad_time_and_ticket_count():
    out = check(spec(date="20261031", time_from="7pm", tickets=0))
    assert out.time_from is None
    assert "past" in out.clarify and "How many tickets" in out.clarify


def test_model_question_kept_first():
    out = check(spec(clarify="Which theatre?", tickets=0))
    assert out.clarify.startswith("Which theatre?")


def test_prompt_carries_context():
    p = build_prompt(
        "2 for jailer 2 https://in.bookmyshow.com/movies/vellore/jailer-2/ET00518674",
        today=TODAY, city="vellore", catalog=CATALOG, venues=VENUES,
    )
    assert "Today: Sunday 2026-11-01" in p
    assert "PVYS: PVR" in p and "et_code=ET00524017" in p
    assert "Link given: slug=jailer-2" in p


def test_parse_request_sends_schema_and_validates_reply():
    """Offline: fake HTTP transport, checks the request we send and the parsing of the reply."""
    import asyncio
    import json

    import anthropic
    import httpx2

    from movie_agent.intake import parse_request

    reply = spec(et_code="ET99999999").model_dump()
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["body"] = json.loads(request.content)
        seen["beta"] = request.headers.get("anthropic-beta")
        return httpx2.Response(200, json={
            "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
            "content": [{"type": "text", "text": json.dumps(reply)}],
            "stop_reason": "end_turn", "stop_sequence": None,
            "usage": {"input_tokens": 1, "output_tokens": 1},
        })

    client = anthropic.AsyncAnthropic(api_key="test", http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)))
    out = asyncio.run(parse_request(client, "claude-opus-5-5", "2 for jailer 2 friday", today=TODAY,
                                    city="vellore", catalog=CATALOG, venues=VENUES))
    body = seen["body"]
    assert body["fallbacks"] == "default" and "server-side-fallback-2026-07-01" in seen["beta"]
    assert body["output_config"]["effort"] == "low"
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert out.et_code is None and "BookMyShow link" in out.clarify  # validate() ran on the reply
