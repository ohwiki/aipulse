"""Jina Reader fetcher. Scrapes article lists from web pages without RSS.

Used for sites that don't provide RSS feeds (e.g., jiqizhixin.com, tophub.today).
Jina Reader renders JS pages and returns clean text/markdown.
"""
from __future__ import annotations

import re
from datetime import datetime

import requests

try:
    from common import isoformat_z, item_id, normalize_whitespace
except ModuleNotFoundError:
    from tools.common import isoformat_z, item_id, normalize_whitespace

from . import source_matches_keywords

# Lines starting with these prefixes are metadata/noise, not article titles
SKIP_PREFIXES = ("!", "URL Source", "Title:", "Markdown Content", "Image",
                 "http", "今天", "昨天", "[!", "[![", "*", "#", "##", "###")


def fetch(source: dict, now: datetime, start_at: datetime, end_at: datetime) -> list[dict]:
    """Fetch article titles from a web page via Jina Reader.

    Parses the returned markdown/text to extract titles and optional URLs.
    Supports tophub.today format: "1.[title](url)count"
    """
    url = source["url"]
    jina_url = f"https://r.jina.ai/{url}"
    resp = requests.get(jina_url, timeout=30, headers={"User-Agent": "aipulse/1.0"})
    resp.raise_for_status()

    items: list[dict] = []
    for line in resp.text.split("\n"):
        line = line.strip()

        # Skip empty, short, and metadata lines
        if not line or len(line) < 15:
            continue
        if any(line.startswith(p) for p in SKIP_PREFIXES):
            continue
        # Skip tag-like lines (short single phrases)
        if len(line) < 20 and " " not in line and "，" not in line:
            continue

        # Try to extract title + URL from tophub format: "1.[title](url)count"
        tophub_match = re.match(r'(?:\d+[:.]?\s*)?\[([^\]]+)\]\((https?://[^\)]+)\)', line)
        if tophub_match:
            title = tophub_match.group(1)
            article_url = tophub_match.group(2)
        else:
            title = line
            article_url = url

        # Apply keyword filter
        title = normalize_whitespace(title)
        if not source_matches_keywords(source, title):
            continue

        items.append({
            "id": item_id(article_url + title),
            "title": title,
            "url": article_url,
            "source": source["name"],
            "category": source.get("category", "cn-media"),
            "summary": "",
            "published_at": isoformat_z(now),
        })

    max_results = source.get("max_results", 10)
    return items[:max_results]
