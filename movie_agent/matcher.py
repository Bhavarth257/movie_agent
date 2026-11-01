"""Which shows fit a job, and what to do when none fit exactly."""

from dataclasses import dataclass

from .bms import Show
from .jobs import JobSpec

SITUATION = "no_exact_show"
CHOICES = {
    "other_venue": "Same time, another theatre",
    "other_time": "Another show, same theatre",
    "wait": "Keep watching",
    "stop": "Stop, I'll book myself",
}


@dataclass
class Match:
    exact: list[Show]
    other_venue: list[Show]  # right time and format, theatre you didn't list
    other_time: list[Show]  # theatre you listed, outside your time window or format

    @property
    def any_shows(self) -> bool:
        return bool(self.exact or self.other_venue or self.other_time)


def match(spec: JobSpec, shows: list[Show]) -> Match:
    m = Match([], [], [])
    for s in shows:
        venue_ok = not spec.venue_codes or s.venue_code in spec.venue_codes
        slot_ok = _time_ok(spec, s) and _screen_ok(spec, s)
        if venue_ok and slot_ok:
            m.exact.append(s)
        elif slot_ok:
            m.other_venue.append(s)
        elif venue_ok:
            m.other_time.append(s)
    key = lambda s: (_venue_rank(spec, s), _time_distance(spec, s))
    for bucket in (m.exact, m.other_venue, m.other_time):
        bucket.sort(key=key)
    return m


def choices_for(m: Match) -> list[str]:
    """Fallback options that make sense right now."""
    opts = [c for c in ("other_venue", "other_time") if getattr(m, c)]
    return opts + ["wait", "stop"]


def learned_choice(recent: list[str], learn_after: int) -> str | None:
    """Your answer, once your last `learn_after` answers all agree."""
    if learn_after < 1 or len(recent) < learn_after:
        return None
    last = recent[:learn_after]
    return last[0] if len(set(last)) == 1 else None


def pick(choice: str, m: Match) -> Show | None:
    bucket = getattr(m, choice, None) if choice in ("other_venue", "other_time") else None
    return bucket[0] if bucket else None


def _minutes(hhmm: str) -> int:
    hhmm = hhmm.replace(":", "")
    return int(hhmm[:2]) * 60 + int(hhmm[2:4])


def _time_ok(spec: JobSpec, s: Show) -> bool:
    t = _minutes(s.time)
    return (not spec.time_from or t >= _minutes(spec.time_from)) and (not spec.time_to or t <= _minutes(spec.time_to))


def _screen_ok(spec: JobSpec, s: Show) -> bool:
    return not spec.screens or any(w.lower() in s.screen.lower() for w in spec.screens)


def _venue_rank(spec: JobSpec, s: Show) -> int:
    return spec.venue_codes.index(s.venue_code) if s.venue_code in spec.venue_codes else len(spec.venue_codes)


def _time_distance(spec: JobSpec, s: Show) -> int:
    """Minutes from the middle of your window (or from its open end)."""
    lo = _minutes(spec.time_from) if spec.time_from else None
    hi = _minutes(spec.time_to) if spec.time_to else None
    if lo is None and hi is None:
        return 0
    target = (lo + hi) // 2 if lo is not None and hi is not None else (lo if lo is not None else hi)
    return abs(_minutes(s.time) - target)
