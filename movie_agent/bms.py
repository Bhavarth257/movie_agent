"""BookMyShow URLs and page parsing. Pure functions, no network."""

import json
import re
from dataclasses import dataclass

BASE = "https://in.bookmyshow.com"

_STATE_MARKER = "window.__INITIAL_STATE__"
_MOVIE_LINK = re.compile(r"/movies/([a-z-]+)/([a-z0-9-]+)/(?:buytickets/)?(ET\d{8})")


@dataclass(frozen=True)
class Show:
    venue_code: str
    venue_name: str
    session_id: str
    date: str  # YYYYMMDD
    time: str  # HHMM, 24h
    label: str  # "06:30 PM" as shown on the site
    screen: str  # "ATMOS", "LASER", "" ...
    avail_status: str  # raw site code; meaning not verified yet (recon)


@dataclass(frozen=True)
class Movie:
    city: str
    slug: str
    et_code: str

    @property
    def title(self) -> str:
        return self.slug.replace("-", " ").title()


def buytickets_url(city: str, slug: str, et_code: str, date: str) -> str:
    return f"{BASE}/movies/{city}/{slug}/buytickets/{et_code}/{date}"


def explore_urls(city: str) -> list[str]:
    return [f"{BASE}/explore/movies-{city}", f"{BASE}/explore/upcoming-movies-{city}"]


def is_blocked(status: int, html: str) -> bool:
    """Cloudflare block or challenge page. We stop and alert; we never try to get around it."""
    return status in (403, 429, 503) or "Attention Required! | Cloudflare" in html


def initial_state(html: str) -> dict | None:
    i = html.find(_STATE_MARKER)
    if i < 0:
        return None
    rest = html[html.index("=", i) + 1 :].lstrip()
    try:
        state, _ = json.JSONDecoder().raw_decode(rest)
    except json.JSONDecodeError:
        return None
    return state


def parse_shows(html: str, date: str) -> list[Show]:
    """All shows on a buy-tickets page for `date`.

    BookMyShow silently shows the nearest open date when the requested one isn't
    open yet, so shows are filtered on their own date code, never on the URL.
    """
    state = initial_state(html)
    if state is None:
        return []
    shows: list[Show] = []
    for venue in _venue_blocks(state):
        info = venue["additionalData"]
        for section in venue.get("showtimesSections") or []:
            for st in section.get("showtimes") or []:
                d = st.get("additionalData") or {}
                if d.get("showDateCode") != date:
                    continue
                shows.append(
                    Show(
                        venue_code=info["venueCode"],
                        venue_name=info.get("venueName", info["venueCode"]),
                        session_id=str(d.get("sessionId", "")),
                        date=date,
                        time=d.get("showTimeCode", ""),
                        label=d.get("showTime", st.get("title", "")),
                        screen=(st.get("screenAttr") or d.get("attributes") or "").strip(),
                        avail_status=str(d.get("availStatus", "")),
                    )
                )
    return shows


def _venue_blocks(node):
    if isinstance(node, dict):
        info = node.get("additionalData")
        if isinstance(info, dict) and "venueCode" in info and "showtimesSections" in node:
            yield node
            return
        for v in node.values():
            yield from _venue_blocks(v)
    elif isinstance(node, list):
        for v in node:
            yield from _venue_blocks(v)


def parse_movies(html: str, city: str) -> list[Movie]:
    """Movie links on an explore page, deduplicated, in page order."""
    seen: dict[str, Movie] = {}
    for c, slug, et in _MOVIE_LINK.findall(html):
        if c == city and et not in seen:
            seen[et] = Movie(c, slug, et)
    return list(seen.values())


def parse_movie_url(text: str) -> Movie | None:
    """A BookMyShow movie or buy-tickets link pasted into a message."""
    m = _MOVIE_LINK.search(text)
    return Movie(*m.groups()) if m else None
