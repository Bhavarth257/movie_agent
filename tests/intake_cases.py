"""Requests every intake parser must turn into the right job. Shared by the rules and Claude tests."""

from datetime import date

from movie_agent.bms import Movie

TODAY = date(2026, 11, 1)  # Sunday
CATALOG = [
    Movie("vellore", "jailer-2", "ET00518674"),
    Movie("vellore", "cult", "ET00524017"),
    Movie("vellore", "ramayana", "ET00451914"),
]
VENUES = [
    ("ACTV", "AASCARS CINEMAS 4K DOLBY 7.1"),
    ("APVE", "Apsara Cinemas 4K Laser AC 7.1 Dolby: Vellore"),
    ("IOSE", "INOX: Selvam Square, Vellore"),
    ("PVYS", "PVR: Velocity, Silk Mill, Gandhi Nagar"),
]

# (message, expected fields). Only the listed fields are checked.
CASES = [
    ("2 tickets for jailer 2 at PVR friday evening, middle rows, max 300 each",
     dict(et_code="ET00518674", venue_codes=["PVYS"], date="20261106", time_from="16:00", tickets=2, max_price=300, clarify=None)),
    ("Ramayana 3 seats INOX saturday night back rows",
     dict(et_code="ET00451914", venue_codes=["IOSE"], date="20261107", time_from="20:00", tickets=3, seat_pref="back")),
    ("book cult for 4 people tomorrow morning, any theatre",
     dict(et_code="ET00524017", venue_codes=[], date="20261102", time_from="06:00", time_to="12:00", tickets=4)),
    ("jailer2 x2, apsara first, else pvr, 6 nov after 6pm",
     dict(et_code="ET00518674", venue_codes=["APVE", "PVYS"], date="20261106", time_from="18:00", tickets=2)),
    ("1 ticket ramayana atmos at inox on the 10th",
     dict(et_code="ET00451914", venue_codes=["IOSE"], date="20261110", screens=["ATMOS"], tickets=1)),
    ("need 2 for Jailer 2 aascars this wednesday between 2 and 5 pm under 200",
     dict(et_code="ET00518674", venue_codes=["ACTV"], date="20261104", time_from="14:00", time_to="17:00", max_price=200)),
    ("jailer 2 tickets friday evening pvr",  # no ticket count
     dict(et_code="ET00518674", date="20261106", clarify="ANY")),
    ("2 tickets for Avengers Secret Wars friday at pvr",  # not in catalog
     dict(et_code=None, movie_slug=None, clarify="ANY")),
    ("2 tix https://in.bookmyshow.com/movies/vellore/new-film/ET00600000 sat evening",
     dict(et_code="ET00600000", movie_slug="new-film", date="20261107", tickets=2)),
    ("5 seats for cult at the inox in selvam square, front rows, 8th november 9pm show",
     dict(et_code="ET00524017", venue_codes=["IOSE"], date="20261108", tickets=5, seat_pref="front")),
]



def check(spec, expected):
    for field, want in expected.items():
        got = getattr(spec, field)
        if want == "ANY":
            assert got, f"{field} should be set, got {got!r}\n{spec}"
        else:
            assert got == want, f"{field}: want {want!r}, got {got!r}\n{spec}"
