"""
Shared configuration helpers for the Financial Tracker bot.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_TIMEZONE = "Asia/Jakarta"

load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    bot_token: str | None
    excel_path: Path
    allowed_user_ids: tuple[int, ...]
    timezone: str

    @classmethod
    def from_env(cls) -> "Settings":
        token = os.getenv("TELEGRAM_BOT_TOKEN") or None
        excel_path = Path(os.getenv("EXCEL_PATH", "./Financial_Tracker.xlsx")).expanduser()
        if not excel_path.is_absolute():
            excel_path = (PROJECT_ROOT / excel_path).resolve()

        raw_ids = os.getenv("ALLOWED_USER_IDS", "")
        allowed_ids = tuple(
            int(uid.strip()) for uid in raw_ids.split(",") if uid.strip().isdigit()
        )

        timezone = os.getenv("TIMEZONE", DEFAULT_TIMEZONE).strip() or DEFAULT_TIMEZONE

        return cls(
            bot_token=token,
            excel_path=excel_path,
            allowed_user_ids=allowed_ids,
            timezone=timezone,
        )


settings = Settings.from_env()


def is_user_allowed(user_id: int) -> bool:
    """Return True when the bot is open or the user is explicitly allowed."""
    if not settings.allowed_user_ids:
        return True
    return user_id in settings.allowed_user_ids


def local_now() -> datetime:
    """Return a timezone-aware local datetime without failing on bad TZ config."""
    try:
        return datetime.now(ZoneInfo(settings.timezone))
    except ZoneInfoNotFoundError:
        return datetime.now()
