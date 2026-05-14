"""RSS feed fetcher. Handles standard RSS/Atom feeds via feedparser."""
from __future__ import annotations

from datetime import datetime

import feedparser
import requests

try:
    from common import isoformat_z, normalize_whitespace
except ModuleNotFoundError:
    from tools.common import isoformat_z, normalize_whitespace

from . import (build_item, clean_summary, feed_time_to_datetime,
               source_matches_keywords, within_target_window)


def fetch(source: dict, now: datetime, start_at: datetime, end_at: datetime) -> list[dict]:
    """Fetch items from an RSS/Atom feed.

    Filters by time window and optional keyword matching.
    Raises on network/parse errors so caller can handle fallback.
    """
    response = requests.get(source["url"], timeout=30, headers={"User-Agent": "aipulse/1.0"})
    response.raise_for_status()

    feed = feedparser.parse(response.text)
    if getattr(feed, "bozo", False) and not feed.entries:
        exception = getattr(feed, "bozo_exception", None)
        if exception:
            raise RuntimeError(str(exception))

    items: list[dict] = []
    for entry in feed.entries:
        # Parse publication date
        published = (
            feed_time_to_datetime(getattr(entry, "published_parsed", None))
            or feed_time_to_datetime(getattr(entry, "updated_parsed", None))
        )
        if not published or not within_target_window(published, start_at, end_at):
            continue

        url = getattr(entry, "link", "").strip()
        if not url:
            continue

        title = normalize_whitespace(getattr(entry, "title", ""))
        summary = clean_summary(getattr(entry, "summary", "") or getattr(entry, "description", ""))

        # Keyword filter (skip if source has keywords_any and none match)
        if not source_matches_keywords(source, title, summary, url):
            continue

        items.append(build_item(
            title=title,
            url=url,
            source_name=source["name"],
            category=source["category"],
            summary=summary,
            published_at=isoformat_z(published),
        ))

    return items
