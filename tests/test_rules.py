import pytest

from intake_cases import CASES, CATALOG, TODAY, VENUES, check
from movie_agent.rules import parse


def run(text):
    return parse(text, today=TODAY, city="vellore", catalog=CATALOG, venues=VENUES)


@pytest.mark.parametrize("message,expected", CASES, ids=[c[0][:40] for c in CASES])
def test_request_becomes_right_job(message, expected):
    check(run(message), expected)


@pytest.mark.parametrize("text,date", [
    ("2 tickets jailer 2 today", "20261101"),
    ("2 tickets jailer 2 sunday", "20261101"),  # today is Sunday
    ("2 tickets jailer 2 next sunday", "20261108"),
    ("2 tickets jailer 2 nov 15", "20261115"),
    ("2 tickets jailer 2 15/11", "20261115"),
    ("2 tickets jailer 2 on the 1st", "20261101"),
    ("2 tickets jailer 2 3rd january", "20270103"),
])
def test_dates(text, date):
    assert run(text).date == date


@pytest.mark.parametrize("text,window", [
    ("2 tickets jailer 2 friday 6:30pm", ("18:00", "19:00")),
    ("2 tickets jailer 2 friday before 3pm", (None, "15:00")),
    ("2 tickets jailer 2 friday 11am show", ("10:30", "11:30")),
    ("2 tickets jailer 2 friday afternoon", ("12:00", "16:00")),
    ("2 tickets jailer 2 friday", (None, None)),
])
def test_times(text, window):
    out = run(text)
    assert (out.time_from, out.time_to) == window


def test_rupee_price_and_word_count():
    out = run("two tickets jailer 2 friday under ₹250")
    assert (out.tickets, out.max_price) == (2, 250)


def test_movie_number_is_not_a_ticket_count():
    out = run("jailer 2 friday")
    assert "How many tickets" in out.clarify
