from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


UTC = timezone.utc
LOCAL_TZ = ZoneInfo("Asia/Shanghai")
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
SCORED_DIR = DATA_DIR / "scored"
DAILY_DIR = DATA_DIR / "daily"


def load_dotenv() -> None:
    for candidate in (ROOT_DIR / ".env", ROOT_DIR / ".env.local"):
        if not candidate.exists():
            continue
        for raw_line in candidate.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if not key or key in os.environ:
                continue
            value = value.strip().strip("\"'")
            os.environ[key] = value


load_dotenv()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def ensure_data_dirs() -> None:
    for directory in (DATA_DIR, RAW_DIR, SCORED_DIR, DAILY_DIR):
        ensure_dir(directory)


def utc_now() -> datetime:
    return datetime.now(UTC)


def local_now() -> datetime:
    return datetime.now(LOCAL_TZ)


def today_str(now: datetime | None = None) -> str:
    current = now or local_now()
    return current.astimezone(LOCAL_TZ).date().isoformat()


def local_date_str_from_utc(value: datetime) -> str:
    return value.astimezone(LOCAL_TZ).date().isoformat()


def isoformat_z(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def within_last_24_hours(value: datetime, now: datetime | None = None) -> bool:
    current = now or utc_now()
    return value >= current - timedelta(hours=24)


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def item_id(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:8]


def normalize_whitespace(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.split())


def is_mostly_ascii(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return True
    ascii_count = sum(1 for char in stripped if ord(char) < 128)
    return ascii_count / len(stripped) >= 0.8


def estimate_tokens(*parts: str) -> int:
    characters = sum(len(part) for part in parts)
    return max(1, characters // 4)


@dataclass
class AppConfig:
    api_key: str
    base_url: str
    model: str


def load_app_config(require_api_key: bool = False) -> AppConfig:
    api_key = os.getenv("NULLCLAW_API_KEY", "").strip()
    if require_api_key and not api_key:
        raise RuntimeError("NULLCLAW_API_KEY is required")
    return AppConfig(
        api_key=api_key,
        base_url=os.getenv("NULLCLAW_BASE_URL", "https://platform.xiaomimimo.com/v1").rstrip("/"),
        model=os.getenv("NULLCLAW_MODEL", "mimo-v2.5-pro"),
    )
