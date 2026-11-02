# Progress

What's built, what's next, and what's blocking. Updated at the end of each step.
Major choices and their reasons live in [DECISIONS.md](DECISIONS.md).

## Phases

| # | Phase | Status |
| --- | --- | --- |
| 1 | Recon: book one ticket by hand with `playwright codegen`, write down every page and selector | Not started (needs you) |
| 2 | Watcher + Telegram alert | In progress: parser, matcher and job store done; watcher loop next |
| 3 | Intake agent (Telegram message to booking job) | In progress: free rules parser (default) and Claude parser done; Telegram side next |
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

### Step 4: Job store, show matcher, learned fallback (2026-11-01)
- `movie_agent/jobs.py`: `JobSpec` holds what you asked for (movie, theatres in order of preference, date, time window, formats, tickets, rows, price cap). It doubles as the structured output Claude will fill in Step 5.
- SQLite `Store` in `data/agent.db`: jobs and their status, your fallback answers, theatres seen on pages, a small cache, and an event log.
- `movie_agent/matcher.py` sorts a page's shows into three groups:
  - **exact:** your theatre, time window and format;
  - **other theatre:** right time and format at a theatre you didn't list;
  - **other time:** your theatre, outside your window or format.
- Within each group, preferred theatres come first, then shows closest to the middle of your time window.
- Fallback (D6): the agent offers only the options that exist right now. Once your last `LEARN_AFTER` answers agree, it applies that answer itself.
- 18 tests pass.

### Step 5: Claude intake (2026-11-01)
- `movie_agent/intake.py` sends your message to Claude (`claude-haiku-5-5` by default, see D12; low effort, structured output). The prompt includes:
  - today's date;
  - the default city;
  - the known theatres;
  - the movie catalog;
  - any BookMyShow link you pasted.
- The reply is a `JobSpec`. Plain code then checks what it can (D11):
  - the movie code must come from the catalog or your link;
  - unknown theatre codes are dropped;
  - past dates, malformed times and odd ticket counts become a question back to you.
- If something essential is missing, `clarify` holds one short question for the bot to ask.
- `tests/test_intake.py`: offline tests, including the exact request sent to the API, checked with a fake HTTP transport.
- `tests/test_intake_live.py`: the plan's Phase 3 check, 10 differently worded requests against the real API.
  **First attempt (2026-11-01):** the key works, but the account has no credit ("credit balance is too low"), so no case reached the model. Rerun after topping up:
  `RUN_LIVE=1 PYTHONPATH= .venv/bin/python -m pytest -q tests/test_intake_live.py`

### Step 6: Free rules parser (2026-11-02)
- `movie_agent/rules.py`: no LLM, no cost (D13). It reads, in this order:
  - the movie (from the catalog, or a pasted link);
  - the time ("evening", "after 6pm", "between 2 and 5 pm", "9pm show");
  - the date ("friday", "tomorrow", "6 nov", "the 10th", "15/11");
  - a price cap ("max 300", "under ₹250");
  - the ticket count ("2 tickets", "x2", "need 2", "for 4 people");
  - theatres, in the order you name them ("apsara first, else pvr");
  - formats (IMAX, ATMOS, ...) and rows (front, back, middle).
- Each rule blanks out the words it used, so "Jailer 2" is never read as 2 tickets and "6pm" never as the 6th.
- The 10 test requests now live in `tests/intake_cases.py` and run against both parsers. All 10 pass with the rules parser, plus 14 more checks for dates, times and prices.
- `INTAKE=rules` (default) or `INTAKE=claude` in `.env`.

## Next

1. **Step 7:** Chrome watcher loop + Telegram bot: message to job with Arm/Cancel buttons, `/jobs`, `/stop`, fallback buttons, block back-off.
2. Then Phase 1 recon (you), which unlocks the booker.

## Known facts and open issues

- **Vellore theatres on BookMyShow:** PVR Velocity `PVYS`, INOX Selvam Square `IOSE`, Aascars `ACTV`, Apsara `APVE`.
- **Cloudflare blocks plain HTTP requests** even from a Jio home connection. Real Chrome works, but about five page loads in a few minutes got blocked too. Polling must stay slow.
- **Availability code meaning is unknown** (`availStatus`, seen as `3` on open shows). Find the sold-out and fast-filling values during recon.
- **Running tests:** ROS 2 puts its pytest plugins on `PYTHONPATH`, so run
  `PYTHONPATH= .venv/bin/python -m pytest -q`.
