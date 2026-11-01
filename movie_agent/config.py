"""Settings read from the environment (and .env in the repo root)."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    telegram_token: str
    owner_chat_id: int | None
    city: str
    poll_seconds: int
    learn_after: int
    model: str
    data_dir: Path

    @property
    def db_path(self) -> Path:
        return self.data_dir / "agent.db"

    @property
    def chrome_profile(self) -> Path:
        return self.data_dir / "chrome-profile"


def load() -> Settings:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is missing. Copy .env.example to .env and fill it in.")
    owner = os.environ.get("TELEGRAM_OWNER_ID", "").strip()
    data_dir = Path(os.environ.get("DATA_DIR", ROOT / "data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return Settings(
        telegram_token=token,
        owner_chat_id=int(owner) if owner else None,
        city=os.environ.get("BMS_CITY", "vellore").strip().lower(),
        poll_seconds=int(os.environ.get("POLL_SECONDS", "60")),
        learn_after=int(os.environ.get("LEARN_AFTER", "2")),
        model=os.environ.get("CLAUDE_MODEL", "claude-opus-5-5"),
        data_dir=data_dir,
    )
