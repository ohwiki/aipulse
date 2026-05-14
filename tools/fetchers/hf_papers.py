"""HuggingFace Daily Papers fetcher. Queries HF API for trending papers."""
from __future__ import annotations

from datetime import datetime, timezone

import requests

try:
    from common import isoformat_z, normalize_whitespace, parse_datetime
except ModuleNotFoundError:
    from tools.common import isoformat_z, normalize_whitespace, parse_datetime

from . import build_item, clean_summary, source_matches_keywords, within_target_window


def fetch(source: dict, now: datetime, start_at: datetime, end_at: datetime) -> list[dict]:
    """Fetch trending papers from HuggingFace Daily Papers API."""
    response = requests.get(source["url"], timeout=30)
    response.raise_for_status()
    payload = response.json()

    # HF API may return {papers: [...]} or a flat list
    if isinstance(payload, dict):
        records = payload.get("papers") or payload.get("items") or []
    else:
        records = payload

    items: list[dict] = []
    for record in records:
        # Try multiple date field names
        published = None
        for key in ("published_at", "publishedAt", "createdAt", "date"):
            raw_value = record.get(key)
            if isinstance(raw_value, str):
                try:
                    published = datetime.fromisoformat(raw_value.replace("Z", "+00:00")).astimezone(timezone.utc)
                except ValueError:
                    continue
                if published:
                    break
        if not published:
            published = now

        if not within_target_window(published, start_at, end_at):
            continue

        # Extract URL from nested or flat structure
        url = (
            record.get("url")
            or record.get("paper", {}).get("url")
            or record.get("paper", {}).get("id")
            or record.get("id")
            or ""
        )
        if not isinstance(url, str) or not url.strip():
            continue

        title = normalize_whitespace(str(record.get("title") or record.get("paper", {}).get("title") or ""))
        summary = clean_summary(str(
            record.get("summary") or record.get("paper", {}).get("summary") or record.get("abstract") or ""
        ))

        if not source_matches_keywords(source, title, summary, str(url)):
            continue

        items.append(build_item(
            title=title,
            url=url.strip(),
            source_name=source["name"],
            category=source["category"],
            summary=summary,
            published_at=isoformat_z(published),
        ))

    return items
