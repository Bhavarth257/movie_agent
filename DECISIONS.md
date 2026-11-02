# Decisions

Major choices, newest last. Each entry says what we chose, why, and what we gave up.
To change one, add a new entry that replaces it instead of editing history.

## D1. Payment is always approved by a human (2026-11-01)
- **Chose:** the agent holds seats and stops at the payment page; you approve with your UPI PIN.
- **Why:** RBI's 2025 authentication rules require a factor unique to each payment. A bot cannot legally skip it.
- **Cost:** you must respond within BookMyShow's 7–8 minute seat hold.

## D2. No CAPTCHA solving, proxy rotation or fingerprint spoofing (2026-11-01)
- **Chose:** on a block or challenge, the agent alerts you and backs off (15 min, doubling up to 2 h). You book by hand.
- **Why:** getting around bot protection is evasion, and it risks a ban on your account.
- **Cost:** a block on release day means a manual booking.

## D3. Poll with a real Chrome window, not plain HTTP (2026-11-01)
- **Chose:** Playwright drives the installed Google Chrome with a saved profile, for polling as well as booking.
- **Why:** tested on 2026-11-01. A plain HTTP request from the home Jio connection got a Cloudflare 403, while real Chrome loaded the page in 0.6 s. Imitating Chrome's network fingerprint to make plain HTTP pass would break D2.
- **Cost:** heavier than HTTP, needs a desktop session, one page load per check.
- **Replaces:** the plan's `httpx` + APScheduler poller.

## D4. Read the page's embedded JSON, not its visible markup (2026-11-01)
- **Chose:** parse `window.__INITIAL_STATE__`, filter shows on their own `showDateCode`.
- **Why:** it carries venue code, show time, format, session ID and availability in one place, and survives visual redesigns better than CSS selectors.
- **Cost:** if BookMyShow renames these keys, the parser breaks. The fixture tests catch this.

## D5. The LLM handles intake only; plain code runs the race (2026-11-01)
- **Chose:** Claude (`claude-opus-5-5`, structured output, server-side refusal fallback on) turns your message into a job. Polling, matching and seat choice are plain code.
- **Why:** an LLM call takes seconds; the race is decided in seconds.

## D6. Fallback: ask first, then learn (2026-11-01)
- **Chose:** when your exact show is missing, the agent asks: other theatre, other time, keep watching, or stop. Once your last `LEARN_AFTER` (default 2) answers agree, it applies that answer itself and tells you what it did.
- **Why:** your choice, so the agent adapts to you instead of using a fixed rule.

## D7. Defaults: Vellore, Telegram, owner only (2026-11-01)
- **Chose:** city `vellore`; Telegram bot that answers only your chat ID; theatres learned from the pages it reads.
- **Why:** your answers to the setup questions.

## D8. Polite polling (2026-11-01)
- **Chose:** one check per job every 60 s with random jitter, one booking at a time, one personal account. The movie list is cached for 6 hours.
- **Why:** about five page loads in a few minutes got us blocked while building the parser.

## D9. Secrets never reach git (2026-11-01)
- **Chose:** tokens in `.env`, browser profile and database in `data/`, both gitignored. The repo is public.

## D10. You commit and push; Claude gives the commands (2026-11-01)
- **Chose:** Claude writes code and docs and gives you the git commands after each step. Commit messages carry no AI co-author line.

## D11. Check Claude's output in code (2026-11-01)
- **Chose:** after Claude fills in a job, plain code checks the facts it can verify: the movie code must come from the catalog or your link, theatre codes from the known list, the date can't be past, times must be HH:MM, and 1–10 tickets. Anything wrong turns into a question back to you instead of a silent guess.
- **Why:** a wrong movie or theatre code would watch the wrong page all the way to release day without anyone noticing.
- **Cost:** sometimes one extra question before arming.

## D12. Intake runs on Claude Haiku (2026-11-01)
- **Chose:** `claude-haiku-5-5` as the default intake model, at low effort. Change it with `CLAUDE_MODEL` in `.env`.
- **Why:** the Anthropic API is paid per use. Opus costs about ₹1.5–2 per message; Haiku costs about ₹0.05. Pulling a job out of a short chat message is a simple task, and the 10-case live check will show whether Haiku is good enough.
- **Cost:** Haiku has no server-side refusal fallback, so the intake sends `fallbacks` only to the larger models. If Haiku gets cases wrong, switch back to `claude-opus-5-5`.
- **Replaces:** the model part of D5.

## D13. Free rules parser is the default intake (2026-11-02)
- **Chose:** `movie_agent/rules.py` turns your message into a job with plain rules, at no cost. Claude intake stays in the code, switched off (`INTAKE=claude` in `.env` turns it on).
- **Why:** no paid API use for now. The plan already listed a no-LLM option. All 10 test requests, written for Claude, also pass with the rules parser.
- **Cost:** the rules only understand phrasing they were written for. Unusual wording can be misread, so the bot always shows the job and waits for your OK before arming (the same as with Claude). The same code checks (D11) run on both parsers.
- **Replaces:** D12 as the default. D12 still applies when `INTAKE=claude`.
