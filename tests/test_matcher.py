import gzip
from pathlib import Path

from movie_agent import bms
from movie_agent.jobs import JobSpec, Store
from movie_agent.matcher import choices_for, learned_choice, match, pick

FIXTURE = Path(__file__).parent / "fixtures" / "showtimes_vellore_20261102.html.gz"
SHOWS = bms.parse_shows(gzip.open(FIXTURE, "rt").read(), "20261102")


def spec(**kw) -> JobSpec:
    base = dict(
        movie_title="Jailer 2", et_code="ET00518674", movie_slug="jailer-2", city="vellore",
        venue_codes=["PVYS"], date="20261102", time_from="18:00", time_to="20:00", screens=[],
        tickets=2, seat_pref="middle", max_price=None, clarify=None,
    )
    return JobSpec(**{**base, **kw})


def test_exact_evening_show_at_preferred_theatre():
    m = match(spec(), SHOWS)
    assert [s.time for s in m.exact] == ["1900", "1830", "1800"]  # closest to the window's middle (19:00) first
    assert all(s.venue_code == "PVYS" for s in m.exact)


def test_screen_filter():
    m = match(spec(screens=["atmos"]), SHOWS)
    assert [s.time for s in m.exact] == ["1900"]


def test_no_exact_show_offers_alternatives():
    # Apsara only has 18:30 LASER in this window; ask for ATMOS there.
    m = match(spec(venue_codes=["APVE"], screens=["ATMOS"]), SHOWS)
    assert m.exact == []
    assert {s.venue_code for s in m.other_venue} == {"PVYS", "IOSE"}
    assert m.other_time and all(s.venue_code == "APVE" for s in m.other_time)
    assert choices_for(m) == ["other_venue", "other_time", "wait", "stop"]
    assert pick("other_venue", m).screen.lower() == "atmos"
    assert pick("wait", m) is None


def test_venue_order_is_preference_order():
    m = match(spec(venue_codes=["IOSE", "PVYS"], time_from="18:00", time_to="18:30"), SHOWS)
    assert m.exact[0].venue_code == "IOSE"


def test_no_shows_for_date():
    m = match(spec(date="20261125"), [])
    assert not m.any_shows
    assert choices_for(m) == ["wait", "stop"]


def test_learned_choice_needs_agreeing_answers():
    assert learned_choice([], 2) is None
    assert learned_choice(["other_venue"], 2) is None
    assert learned_choice(["other_venue", "wait"], 2) is None
    assert learned_choice(["other_venue", "other_venue", "wait"], 2) == "other_venue"
    assert learned_choice(["wait"], 0) is None  # learning switched off


def test_store_roundtrip(tmp_path):
    store = Store(tmp_path / "t.db")
    job_id = store.add_job(spec())
    assert [j.id for j in store.active()] == [job_id]
    store.set_meta(job_id, asked_sig="abc")
    store.set_status(job_id, "asking")
    job = store.get(job_id)
    assert (job.status, job.meta, job.spec.venue_codes) == ("asking", {"asked_sig": "abc"}, ["PVYS"])

    store.record_answer("no_exact_show", "wait")
    store.record_answer("no_exact_show", "other_venue")
    assert store.recent_answers("no_exact_show", 5) == ["other_venue", "wait"]

    store.save_venues("vellore", SHOWS)
    assert ("IOSE", "INOX: Selvam Square, Vellore") in store.venues("vellore")

    store.cache_put("k", [1, 2])
    assert store.cache_get("k", 60) == [1, 2]
    assert store.cache_get("k", -1) is None

    assert store.stop_all() == 1
    assert store.active() == []
