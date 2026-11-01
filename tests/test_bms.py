import gzip
from pathlib import Path

from movie_agent import bms

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> str:
    with gzip.open(FIXTURES / f"{name}.html.gz", "rt") as f:
        return f.read()


def test_parse_shows_reads_every_venue_and_show():
    shows = bms.parse_shows(load("showtimes_vellore_20261102"), "20261102")
    by_venue = {}
    for s in shows:
        by_venue.setdefault(s.venue_code, []).append(s)
    assert {v: len(s) for v, s in by_venue.items()} == {"PVYS": 12, "IOSE": 8, "ACTV": 4, "APVE": 4}
    evening = next(s for s in by_venue["PVYS"] if s.time == "1830")
    assert evening.label == "06:30 PM"
    assert evening.session_id == "24707"
    assert evening.venue_name == "PVR: Velocity, Silk Mill, Gandhi Nagar"
    assert {s.screen for s in by_venue["APVE"]} == {"LASER"}


def test_parse_shows_ignores_fallback_date():
    # The site renders the nearest open date when ours isn't open; that must not count.
    assert bms.parse_shows(load("showtimes_vellore_20261102"), "20261125") == []


def test_blocked_page_is_detected():
    html = load("cloudflare_blocked")
    assert bms.is_blocked(403, html)
    assert bms.parse_shows(html, "20261102") == []
    assert not bms.is_blocked(200, load("showtimes_vellore_20261102"))


def test_parse_movies_dedupes_and_filters_city():
    html = """
      <a href="https://in.bookmyshow.com/movies/vellore/jailer-2/ET00518674">x</a>
      <a href="/movies/vellore/jailer-2/ET00518674">dup</a>
      <a href="/movies/vellore/cult/ET00524017">y</a>
      <a href="/movies/chennai/other/ET00000001">other city</a>
    """
    movies = bms.parse_movies(html, "vellore")
    assert [(m.slug, m.et_code) for m in movies] == [("jailer-2", "ET00518674"), ("cult", "ET00524017")]
    assert movies[0].title == "Jailer 2"


def test_parse_movie_url_from_pasted_link():
    m = bms.parse_movie_url("book this https://in.bookmyshow.com/movies/vellore/jailer-2/buytickets/ET00518674/20261102 pls")
    assert m == bms.Movie("vellore", "jailer-2", "ET00518674")
    assert bms.buytickets_url(m.city, m.slug, m.et_code, "20261106").endswith("/jailer-2/buytickets/ET00518674/20261106")
