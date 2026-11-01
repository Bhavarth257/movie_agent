# Progress

What's built, what's next, and what's blocking. Updated at the end of each step.
Major choices and their reasons live in [DECISIONS.md](DECISIONS.md).

## Phases

| # | Phase | Status |
| --- | --- | --- |
| 1 | Recon: book one ticket by hand with `playwright codegen`, write down every page and selector | Not started (needs you) |
| 2 | Watcher + Telegram alert | In progress: page parser done; watcher loop next |
| 3 | Intake agent (Telegram + Claude turns a message into a job) | Not started |
| 4 | Booker to seat hold | Waiting on recon. Seat scorer done |
| 5 | Payment handoff + ticket | Not started |
| 6 | Hit-movie mode | Not started |
| 7 | Hardening | Not started |

## Steps done

### Step 1: Project scaffold (2026-11-01)
- Python 3.10 virtualenv, `pyproject.toml`, settings from `.env` (`movie_agent/config.py`).
- `.gitignore` keeps `.env`, `data/` (database and Chrome profile) and the venv out of git.

### Step 2: BookMyShow page parser (2026-11-01)
- `movie_agent/bms.py` reads venues and shows from the page's embedded JSON (`window.__INITIAL_STATE__`).
- Each show has its venue code, time, screen format (ATMOS, LASER, ...), session ID and an availability code.
- Filters on each show's own date, because the site silently shows the nearest open date.
- Detects Cloudflare block pages.
- Tests use a real Vellore page saved on 2026-11-01 (`tests/fixtures/`).

### Step 3: Seat scorer (2026-11-01)
- `movie_agent/seats.py`: picks N seats side by side, never across an aisle, inside your row band (front, middle, back), closest to the centre, under your price cap.
- The booker will turn the real seat map into this format after recon.

## Next

1. **Step 4:** job store (SQLite), show matcher (theatre, time window, format), learned fallback.
2. **Step 5:** Claude intake: message to job, confirm before arming.
3. **Step 6:** Chrome watcher loop + Telegram bot (`/jobs`, `/stop`, fallback buttons).

## Known facts and open issues

- **Vellore theatres on BookMyShow:** PVR Velocity `PVYS`, INOX Selvam Square `IOSE`, Aascars `ACTV`, Apsara `APVE`.
- **Cloudflare blocks plain HTTP requests** even from a Jio home connection. Real Chrome works, but about five page loads in a few minutes got blocked too. Polling must stay slow.
- **Availability code meaning is unknown** (`availStatus`, seen as `3` on open shows). Find the sold-out and fast-filling values during recon.
- **Running tests:** ROS 2 puts its pytest plugins on `PYTHONPATH`, so run
  `PYTHONPATH= .venv/bin/python -m pytest -q`.
