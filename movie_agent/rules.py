"""Free intake: turn a chat message into a JobSpec with plain rules, no LLM.

Each rule finds one field and blanks out the words it used, so later rules
don't mistake "Jailer 2" or "6pm" for a ticket count or a date.
"""

import re
from datetime import date, timedelta

from .bms import Movie, parse_movie_url
from .intake import validate
from .jobs import JobSpec

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
TIME_WORDS = {
    "morning": ("06:00", "12:00"),
    "afternoon": ("12:00", "16:00"),
    "matinee": ("12:00", "16:00"),
    "evening": ("16:00", "20:00"),
    "night": ("20:00", "23:59"),
    "tonight": ("20:00", "23:59"),
}
SCREENS = ["imax", "4dx", "atmos", "laser", "dolby", "3d"]
# Words in theatre names that don't identify a theatre.
GENERIC = {"cinemas", "cinema", "theatre", "theatres", "dolby", "laser", "vellore", "mill", "nagar", "gandhi", "silk", "square"}

_AMPM = r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)"


def parse(text: str, *, today: date, city: str, catalog: list[Movie], venues: list[tuple[str, str]]) -> JobSpec:
    link = parse_movie_url(text)
    s = " " + _normalise(re.sub(r"https?://\S+", " ", text)) + " "

    movie, s = _movie(s, catalog, link)
    time_from, time_to, s = _time(s)
    day, s = _date(s, today)
    max_price, s = _price(s)
    tickets, s = _tickets(s)
    questions = []
    if tickets is None:
        questions.append("How many tickets?")
    if day is None:
        questions.append("Which date?")

    spec = JobSpec(
        movie_title=movie.title if movie else _guess_title(text),
        et_code=movie.et_code if movie else None,
        movie_slug=movie.slug if movie else None,
        city=city,
        venue_codes=_venues(s, venues),
        date=(day or today).strftime("%Y%m%d"),
        time_from=time_from,
        time_to=time_to,
        screens=[w.upper() for w in SCREENS if re.search(rf"\b{w}\b", s)],
        tickets=tickets or 1,
        seat_pref=_seat_pref(s),
        max_price=max_price,
        clarify=" ".join(questions) or None,
    )
    return validate(spec, today=today, catalog=catalog, venues=venues, link=link)


def _normalise(text: str) -> str:
    text = text.lower().replace("₹", " rs ")
    return re.sub(r"[^a-z0-9:/ ]+", " ", text)


def _cut(s: str, m: re.Match) -> str:
    return s[: m.start()] + " " + s[m.end() :]


def _movie(s: str, catalog: list[Movie], link: Movie | None) -> tuple[Movie | None, str]:
    """Longest catalog title found in the text ("jailer 2" or "jailer2")."""
    best = None
    for movie in catalog:
        words = movie.slug.split("-")
        for form in (r"\s+".join(map(re.escape, words)), re.escape("".join(words))):
            m = re.search(rf"\b{form}\b", s)
            if m and (best is None or len(m.group()) > len(best[1].group())):
                best = (movie, m)
    if best:
        return best[0], _cut(s, best[1])
    return link, s


def _hm(hour: str, minute: str | None, ampm: str | None) -> str:
    h = int(hour) % 12 + (12 if ampm == "pm" else 0) if ampm else int(hour)
    return f"{h:02d}:{int(minute or 0):02d}"


def _time(s: str) -> tuple[str | None, str | None, str]:
    m = re.search(rf"\bbetween\s+(\d{{1,2}})(?::(\d{{2}}))?\s*(am|pm)?\s+(?:and|to|-)\s+{_AMPM}", s)
    if m:
        ampm = m.group(3) or m.group(6)
        return _hm(m.group(1), m.group(2), ampm), _hm(m.group(4), m.group(5), m.group(6)), _cut(s, m)
    m = re.search(rf"\b(after|from|before|by|around|at)?\s*{_AMPM}(\s+show)?", s)
    if m:
        t = _hm(m.group(2), m.group(3), m.group(4))
        word = m.group(1)
        if word in ("after", "from"):
            return t, None, _cut(s, m)
        if word in ("before", "by"):
            return None, t, _cut(s, m)
        h, mi = int(t[:2]), int(t[3:])
        lo, hi = max(h * 60 + mi - 30, 0), min(h * 60 + mi + 30, 23 * 60 + 59)
        return f"{lo // 60:02d}:{lo % 60:02d}", f"{hi // 60:02d}:{hi % 60:02d}", _cut(s, m)
    for word, (lo, hi) in TIME_WORDS.items():
        m = re.search(rf"\b{word}\b", s)
        if m:
            return lo, hi, _cut(s, m) if word != "tonight" else s  # "tonight" also sets the date
    return None, None, s


def _date(s: str, today: date) -> tuple[date | None, str]:
    m = re.search(r"\b(today|tonight)\b", s)
    if m:
        return today, _cut(s, m)
    m = re.search(r"\btomorrow\b", s)
    if m:
        return today + timedelta(days=1), _cut(s, m)

    month = "|".join(MONTHS)
    m = re.search(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({month})[a-z]*\b", s) or re.search(
        rf"\b({month})[a-z]*\s+(\d{{1,2}})(?:st|nd|rd|th)?\b", s
    )
    if m:
        a, b = m.groups()
        day, mon = (a, b) if a.isdigit() else (b, a)
        return _future(today, int(day), MONTHS.index(mon[:3]) + 1), _cut(s, m)

    m = re.search(r"\b(\d{1,2})/(\d{1,2})\b", s)  # 6/11 = 6 November
    if m:
        return _future(today, int(m.group(1)), int(m.group(2))), _cut(s, m)

    m = re.search(r"\b(?:on\s+)?(?:the\s+)?(\d{1,2})(st|nd|rd|th)\b", s)
    if m:
        day = int(m.group(1))
        month_ = today.month if day >= today.day else today.month % 12 + 1
        return _future(today, day, month_), _cut(s, m)

    names = "|".join(w[:3] + r"[a-z]*" for w in WEEKDAYS)
    m = re.search(rf"\b(this\s+|next\s+)?({names})\b", s)
    if m:
        target = [w[:3] for w in WEEKDAYS].index(m.group(2)[:3])
        ahead = (target - today.weekday()) % 7
        if ahead == 0 and m.group(1) and m.group(1).strip() == "next":
            ahead = 7
        return today + timedelta(days=ahead), _cut(s, m)
    return None, s


def _future(today: date, day: int, month: int) -> date | None:
    for year in (today.year, today.year + 1):
        try:
            d = date(year, month, day)
        except ValueError:
            return None
        if d >= today:
            return d
    return None


def _price(s: str) -> tuple[int | None, str]:
    m = re.search(r"\b(?:max|maximum|under|below|upto|up to|within|less than|budget)\s*(?:rs\s*)?(\d{2,4})\b(\s*each)?", s) or re.search(
        r"\brs\s*(\d{2,4})\b(\s*each)?", s
    )
    return (int(m.group(1)), _cut(s, m)) if m else (None, s)


def _tickets(s: str) -> tuple[int | None, str]:
    for pattern in (
        r"\b(\d{1,2})\s*(?:tickets?|tix|seats?|people|persons?|members?|of us)\b",
        r"\bx\s*(\d{1,2})\b",
        r"\b(?:need|book|get)\s+(\d{1,2})\b",
        r"\b(\d{1,2})\s+for\b",
        r"\bfor\s+(\d{1,2})\b",
    ):
        m = re.search(pattern, s)
        if m:
            return int(m.group(1)), _cut(s, m)
    for word, n in (("one", 1), ("two", 2), ("three", 3), ("four", 4), ("five", 5), ("six", 6)):
        m = re.search(rf"\b{word}\s+(?:tickets?|seats?|people)\b", s)
        if m:
            return n, _cut(s, m)
    return None, s


def _venues(s: str, venues: list[tuple[str, str]]) -> list[str]:
    """Theatres named in the text, in the order they appear (= your preference)."""
    found = []
    for code, name in venues:
        keys = {w for w in re.findall(r"[a-z]{3,}", name.lower()) if w not in GENERIC}
        hits = [m.start() for k in keys for m in re.finditer(rf"\b{k}\b", s)]
        if hits:
            found.append((min(hits), code))
    return [code for _, code in sorted(found)]


def _seat_pref(s: str) -> str:
    for pref, words in (("front", r"front"), ("back", r"back|last|rear"), ("any", r"any (?:seat|row)s?")):
        if re.search(rf"\b(?:{words})\b", s):
            return pref
    return "middle"


def _guess_title(text: str) -> str:
    """Best guess at an unknown movie's name, for the "couldn't find" question."""
    m = re.search(r"\bfor\s+(.+?)(?=\s+(?:at|on|in|this|next|tomorrow|today|tonight|\w+day)\b|[,.]|$)", text, re.I)
    title = m.group(1) if m else text
    return re.sub(r"^\d+\s*(?:tickets?|tix|seats?)?\s*", "", title).strip()[:60] or "that movie"
