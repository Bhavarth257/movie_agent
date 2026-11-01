"""Booking jobs and everything the agent remembers, in one SQLite file."""

import json
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .bms import Show

# Statuses: armed (watching) -> asking (waiting on your fallback answer) -> matched | stopped | expired
ACTIVE = ("armed", "asking")


class JobSpec(BaseModel):
    """What you asked for. Also the structured output Claude fills in from your message."""

    movie_title: str = Field(description="Movie name as the user said it, cleaned up")
    et_code: str | None = Field(description="BookMyShow event code like ET00518674, only if it is in the catalog or link given")
    movie_slug: str | None = Field(description="BookMyShow URL slug like jailer-2, from the same catalog entry as et_code")
    city: str = Field(description="BookMyShow city slug, lowercase, e.g. vellore")
    venue_codes: list[str] = Field(description="Theatre codes in order of preference; empty means any theatre")
    date: str = Field(description="Show date as YYYYMMDD")
    time_from: str | None = Field(description="Earliest show start, HH:MM 24h; null for no limit")
    time_to: str | None = Field(description="Latest show start, HH:MM 24h; null for no limit")
    screens: list[str] = Field(description="Wanted screen formats like IMAX, ATMOS, LASER, 4DX; empty means any")
    tickets: int = Field(description="Number of tickets")
    seat_pref: Literal["front", "middle", "back", "any"] = Field(description="Preferred rows")
    max_price: int | None = Field(description="Price cap per ticket in rupees; null for no cap")
    clarify: str | None = Field(description="One short question if something essential is missing or ambiguous; otherwise null")

    def summary(self) -> str:
        when = f"{self.date[6:8]}-{self.date[4:6]}-{self.date[:4]}"
        if self.time_from or self.time_to:
            when += f", {self.time_from or 'any'}–{self.time_to or 'any'}"
        lines = [
            f"🎬 {self.movie_title}" + (f" ({self.et_code})" if self.et_code else ""),
            f"📍 {self.city.title()}: {', '.join(self.venue_codes) or 'any theatre'}",
            f"🗓 {when}",
            f"🎟 {self.tickets} × {self.seat_pref} rows" + (f", max ₹{self.max_price} each" if self.max_price else ""),
        ]
        if self.screens:
            lines.append(f"🖥 {', '.join(self.screens)}")
        return "\n".join(lines)


@dataclass
class Job:
    id: int
    status: str
    spec: JobSpec
    meta: dict = field(default_factory=dict)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY, status TEXT NOT NULL, spec TEXT NOT NULL,
    meta TEXT NOT NULL DEFAULT '{}', created_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS answers (
    id INTEGER PRIMARY KEY, situation TEXT NOT NULL, choice TEXT NOT NULL, at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS venues (
    city TEXT NOT NULL, code TEXT NOT NULL, name TEXT NOT NULL, PRIMARY KEY (city, code));
CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT NOT NULL, at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY, job_id INTEGER, kind TEXT NOT NULL, detail TEXT NOT NULL, at REAL NOT NULL);
"""


class Store:
    def __init__(self, path: Path | str):
        self.db = sqlite3.connect(path)
        self.db.executescript(_SCHEMA)

    # jobs
    def add_job(self, spec: JobSpec) -> int:
        now = time.time()
        cur = self.db.execute(
            "INSERT INTO jobs (status, spec, created_at, updated_at) VALUES ('armed', ?, ?, ?)",
            (spec.model_dump_json(), now, now),
        )
        self.db.commit()
        self.log(cur.lastrowid, "armed", spec.movie_title)
        return cur.lastrowid

    def get(self, job_id: int) -> Job | None:
        row = self.db.execute("SELECT id, status, spec, meta FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return _job(row) if row else None

    def active(self) -> list[Job]:
        rows = self.db.execute(
            f"SELECT id, status, spec, meta FROM jobs WHERE status IN {ACTIVE} ORDER BY id"
        ).fetchall()
        return [_job(r) for r in rows]

    def set_status(self, job_id: int, status: str, detail: str = "") -> None:
        self.db.execute("UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?", (status, time.time(), job_id))
        self.db.commit()
        self.log(job_id, status, detail)

    def set_meta(self, job_id: int, **values) -> None:
        job = self.get(job_id)
        meta = {**job.meta, **values}
        self.db.execute("UPDATE jobs SET meta = ?, updated_at = ? WHERE id = ?", (json.dumps(meta), time.time(), job_id))
        self.db.commit()

    def stop_all(self) -> int:
        ids = [j.id for j in self.active()]
        for job_id in ids:
            self.set_status(job_id, "stopped", "/stop")
        return len(ids)

    # fallback answers, newest first
    def record_answer(self, situation: str, choice: str) -> None:
        self.db.execute("INSERT INTO answers (situation, choice, at) VALUES (?, ?, ?)", (situation, choice, time.time()))
        self.db.commit()

    def recent_answers(self, situation: str, n: int) -> list[str]:
        rows = self.db.execute(
            "SELECT choice FROM answers WHERE situation = ? ORDER BY id DESC LIMIT ?", (situation, n)
        ).fetchall()
        return [r[0] for r in rows]

    # theatres seen on pages
    def save_venues(self, city: str, shows: list[Show]) -> None:
        self.db.executemany(
            "INSERT OR REPLACE INTO venues (city, code, name) VALUES (?, ?, ?)",
            {(city, s.venue_code, s.venue_name) for s in shows},
        )
        self.db.commit()

    def venues(self, city: str) -> list[tuple[str, str]]:
        return self.db.execute("SELECT code, name FROM venues WHERE city = ? ORDER BY name", (city,)).fetchall()

    # small JSON cache (movie catalog)
    def cache_get(self, key: str, max_age: float):
        row = self.db.execute("SELECT value, at FROM cache WHERE key = ?", (key,)).fetchone()
        return json.loads(row[0]) if row and time.time() - row[1] < max_age else None

    def cache_put(self, key: str, value) -> None:
        self.db.execute("INSERT OR REPLACE INTO cache (key, value, at) VALUES (?, ?, ?)", (key, json.dumps(value), time.time()))
        self.db.commit()

    def log(self, job_id: int | None, kind: str, detail: str = "") -> None:
        self.db.execute("INSERT INTO events (job_id, kind, detail, at) VALUES (?, ?, ?, ?)", (job_id, kind, detail, time.time()))
        self.db.commit()


def _job(row) -> Job:
    return Job(id=row[0], status=row[1], spec=JobSpec.model_validate_json(row[2]), meta=json.loads(row[3]))
