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
