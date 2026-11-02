"""Turn a chat message into a JobSpec with Claude, then check it in plain code."""

import re
from datetime import date, datetime

import anthropic

from .bms import Movie, parse_movie_url
from .jobs import JobSpec

SYSTEM = """You turn a movie-ticket request sent over chat into a booking job for BookMyShow.

Rules:
- Resolve relative dates against the given today. A weekday name means the next such day, or today if today is that day and the user says "today".
- Time words: morning = 06:00-12:00, afternoon = 12:00-16:00, evening = 16:00-20:00, night = 20:00-23:59, "first day first show" = earliest show (time_to null).
- Pick et_code and movie_slug only from the catalog or link provided. If the movie is not there, set both to null and ask for the BookMyShow link in clarify.
- venue_codes must come from the known theatres list, in the order the user prefers. Match loosely ("PVR" -> the PVR theatre). If the user names no theatre, leave it empty (any theatre).
- Screens: copy formats the user asks for (IMAX, 4DX, ATMOS, LASER, DOLBY). Empty if none.
- seat_pref: "middle" unless the user says front/back/any. "middle rows", "center" -> middle.
- If the ticket count or the date is missing, ask in clarify. Ask at most one short question. Otherwise clarify is null.
- Never invent a price cap; null if not given."""


class IntakeError(Exception):
    pass


async def parse_request(
    client: anthropic.AsyncAnthropic,
    model: str,
    text: str,
    *,
    today: date,
    city: str,
    catalog: list[Movie],
    venues: list[tuple[str, str]],
) -> JobSpec:
    # Haiku has no server-side refusal fallback; the larger models re-run a declined request on another model.
    fallback = {} if model.startswith("claude-haiku") else {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
    response = await client.beta.messages.parse(
        model=model,
        max_tokens=4000,
        system=SYSTEM,
        messages=[{"role": "user", "content": build_prompt(text, today=today, city=city, catalog=catalog, venues=venues)}],
        output_format=JobSpec,
        output_config={"effort": "low"},
        **fallback,
    )
    if response.stop_reason == "refusal":
        raise IntakeError("Claude declined this request.")
    if response.parsed_output is None:
        raise IntakeError(f"No job came back (stop reason: {response.stop_reason}).")
    return validate(response.parsed_output, today=today, catalog=catalog, venues=venues, link=parse_movie_url(text))


def build_prompt(text: str, *, today: date, city: str, catalog: list[Movie], venues: list[tuple[str, str]]) -> str:
    link = parse_movie_url(text)
    movies = "\n".join(f"- {m.title} | slug={m.slug} | et_code={m.et_code}" for m in catalog) or "(empty)"
    theatres = "\n".join(f"- {code}: {name}" for code, name in venues) or "(none known yet)"
    parts = [
        f"Today: {today:%A %Y-%m-%d}",
        f"Default city: {city}",
        f"Known theatres in {city}:\n{theatres}",
        f"Movie catalog for {city}:\n{movies}",
    ]
    if link:
        parts.append(f"Link given: slug={link.slug} et_code={link.et_code} city={link.city}")
    parts.append(f"Request:\n{text}")
    return "\n\n".join(parts)


def validate(
    spec: JobSpec, *, today: date, catalog: list[Movie], venues: list[tuple[str, str]], link: Movie | None = None
) -> JobSpec:
    """Don't trust the model on facts we can check: codes, dates, counts."""
    known = {(m.et_code, m.slug) for m in catalog} | ({(link.et_code, link.slug)} if link else set())
    questions = [spec.clarify] if spec.clarify else []
    fix: dict = {}

    if (spec.et_code, spec.movie_slug) not in known:
        fix.update(et_code=None, movie_slug=None)
        questions.append(f"I couldn't find '{spec.movie_title}' on BookMyShow. Send me its BookMyShow link?")

    venue_codes = {c for c, _ in venues}
    if venue_codes:
        fix["venue_codes"] = [c for c in spec.venue_codes if c in venue_codes]

    try:
        day = datetime.strptime(spec.date, "%Y%m%d").date()
        if day < today:
            questions.append(f"{day:%d %b} is in the past. Which date?")
    except ValueError:
        questions.append("Which date?")

    for name in ("time_from", "time_to"):
        value = getattr(spec, name)
        if value and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", value):
            fix[name] = None

    if not 1 <= spec.tickets <= 10:
        questions.append("How many tickets?")

    fix["clarify"] = " ".join(dict.fromkeys(questions)) or None
    return spec.model_copy(update=fix)
