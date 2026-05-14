"""arXiv API fetcher. Queries arXiv's Atom API for recent papers."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import requests

try:
    from common import isoformat_z, normalize_whitespace
except ModuleNotFoundError:
    from tools.common import isoformat_z, normalize_whitespace

from . import build_item, clean_summary, source_matches_keywords, within_target_window

ARXIV_API_URL = "https://export.arxiv.org/api/query"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


def fetch(source: dict, now: datetime, start_at: datetime, end_at: datetime) -> list[dict]:
    """Fetch papers from arXiv API, filtered by category, time window, and keywords."""
    params = {
        "search_query": source["query"],
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": source.get("max_results", 30),
    }
    response = requests.get(ARXIV_API_URL, params=params, timeout=30)
    response.raise_for_status()
    root = ET.fromstring(response.text)

    items: list[dict] = []
    for entry in root.findall("atom:entry", ATOM_NS):
        # Parse publication date
        published_text = entry.findtext("atom:published", default="", namespaces=ATOM_NS)
        if not published_text:
            continue
        published = datetime.fromisoformat(published_text.replace("Z", "+00:00")).astimezone(timezone.utc)
        if not within_target_window(published, start_at, end_at):
            continue

        url = entry.findtext("atom:id", default="", namespaces=ATOM_NS).strip()
        if not url:
            continue

        title = normalize_whitespace(entry.findtext("atom:title", default="", namespaces=ATOM_NS))
        summary = clean_summary(entry.findtext("atom:summary", default="", namespaces=ATOM_NS))

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
