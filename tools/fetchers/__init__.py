"""Fetcher modules for different source types.

Each fetcher implements: fetch(source, now, start_at, end_at) -> list[dict]
"""
from __future__ import annotations

import html
import re
from datetime import datetime, timedelta, timezone
from time import struct_time

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import requests

try:
    from common import isoformat_z, item_id, normalize_whitespace
except ModuleNotFoundError:
    from tools.common import isoformat_z, item_id, normalize_whitespace


def feed_time_to_datetime(parsed_time: struct_time | None) -> datetime | None:
    """Convert feedparser's time_struct to timezone-aware datetime."""
    if parsed_time is None:
        return None
    return datetime(*parsed_time[:6], tzinfo=timezone.utc)


def within_target_window(value: datetime, start_at: datetime, end_at: datetime) -> bool:
    """Check if a datetime falls within the target fetch window."""
    return start_at <= value < end_at


def source_matches_keywords(source: dict, *parts: str) -> bool:
    """Check if any keyword from source config appears in the given text parts.
    Returns True if no keywords are configured (pass-through).
    """
    keywords = source.get("keywords_any") or []
    if not keywords:
        return True
    haystack = " ".join(part for part in parts if part).lower()
    return any(str(keyword).lower() in haystack for keyword in keywords)


def clean_summary(value: str | None) -> str:
    """Strip HTML tags, unescape entities, normalize whitespace, cap length."""
    text = normalize_whitespace(value)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return text.strip()[:500]


def build_retry_session() -> requests.Session:
    """Create a requests session with automatic retry on transient errors."""
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def build_item(*, title: str, url: str, source_name: str, category: str,
               summary: str = "", published_at: str = "", **extra) -> dict:
    """Construct a standardized raw item dict. Single source of truth for item schema."""
    item = {
        "id": item_id(url),
        "title": title,
        "url": url,
        "source": source_name,
        "category": category,
        "summary": summary,
        "published_at": published_at,
    }
    item.update(extra)
    return item
