from __future__ import annotations

import argparse
import html
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from time import struct_time

import feedparser
import requests
import yaml

try:
    from common import RAW_DIR, ensure_data_dirs, isoformat_z, item_id, normalize_whitespace, today_str, utc_now, within_last_24_hours, write_json
    from logger import get_logger
except ModuleNotFoundError:
    from tools.common import RAW_DIR, ensure_data_dirs, isoformat_z, item_id, normalize_whitespace, today_str, utc_now, within_last_24_hours, write_json
    from tools.logger import get_logger


ARXIV_API_URL = "https://export.arxiv.org/api/query"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
log = get_logger("fetch")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch AIpulse source items")
    parser.add_argument("--date", help="Override output date, format YYYY-MM-DD")
    parser.add_argument("--sources", default=str(Path(__file__).with_name("sources.yaml")))
    return parser.parse_args()


def load_sources(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def is_enabled(source: dict) -> bool:
    return source.get("enabled", True) is not False


def feed_time_to_datetime(parsed_time: struct_time | None) -> datetime | None:
    if parsed_time is None:
        return None
    return datetime(*parsed_time[:6], tzinfo=timezone.utc)


def clean_summary(value: str | None) -> str:
    text = normalize_whitespace(value)
    return html.unescape(text)


def fetch_rss(source: dict, now: datetime) -> list[dict]:
    response = requests.get(source["url"], timeout=30, headers={"User-Agent": "aipulse/1.0"})
    response.raise_for_status()
    feed = feedparser.parse(response.text)
    if getattr(feed, "bozo", False) and not feed.entries:
        exception = getattr(feed, "bozo_exception", None)
        if exception:
            raise RuntimeError(str(exception))

    items: list[dict] = []
    for entry in feed.entries:
        published = (
            feed_time_to_datetime(getattr(entry, "published_parsed", None))
            or feed_time_to_datetime(getattr(entry, "updated_parsed", None))
        )
        if not published or not within_last_24_hours(published, now):
            continue
        url = getattr(entry, "link", "").strip()
        if not url:
            continue
        items.append(
            {
                "id": item_id(url),
                "title": normalize_whitespace(getattr(entry, "title", "")),
                "url": url,
                "source": source["name"],
                "category": source["category"],
                "summary": clean_summary(getattr(entry, "summary", "") or getattr(entry, "description", "")),
                "published_at": isoformat_z(published),
            }
        )
    return items


def fetch_arxiv(source: dict, now: datetime) -> list[dict]:
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
        published_text = entry.findtext("atom:published", default="", namespaces=ATOM_NS)
        if not published_text:
            continue
        published = datetime.fromisoformat(published_text.replace("Z", "+00:00")).astimezone(timezone.utc)
        if not within_last_24_hours(published, now):
            continue
        url = entry.findtext("atom:id", default="", namespaces=ATOM_NS).strip()
        if not url:
            continue
        summary = entry.findtext("atom:summary", default="", namespaces=ATOM_NS)
        title = entry.findtext("atom:title", default="", namespaces=ATOM_NS)
        items.append(
            {
                "id": item_id(url),
                "title": normalize_whitespace(title),
                "url": url,
                "source": source["name"],
                "category": source["category"],
                "summary": clean_summary(summary),
                "published_at": isoformat_z(published),
            }
        )
    return items


def fetch_hf_papers(source: dict, now: datetime) -> list[dict]:
    response = requests.get(source["url"], timeout=30)
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict):
        records = payload.get("papers") or payload.get("items") or []
    else:
        records = payload

    items: list[dict] = []
    for record in records:
        published = None
        for key in ("published_at", "publishedAt", "createdAt", "date"):
            raw_value = record.get(key)
            if isinstance(raw_value, str):
                try:
                    published = datetime.fromisoformat(raw_value.replace("Z", "+00:00")).astimezone(timezone.utc)
                except ValueError:
                    published = None
                if published:
                    break
        if not published:
            published = now
        if not within_last_24_hours(published, now):
            continue

        url = (
            record.get("url")
            or record.get("paper", {}).get("url")
            or record.get("paper", {}).get("id")
            or record.get("id")
            or ""
        )
        if not isinstance(url, str) or not url.strip():
            continue
        title = record.get("title") or record.get("paper", {}).get("title") or ""
        summary = record.get("summary") or record.get("paper", {}).get("summary") or record.get("abstract") or ""
        items.append(
            {
                "id": item_id(url),
                "title": normalize_whitespace(str(title)),
                "url": url.strip(),
                "source": source["name"],
                "category": source["category"],
                "summary": clean_summary(str(summary)),
                "published_at": isoformat_z(published),
            }
        )
    return items


def fetch_api_source(source: dict, now: datetime) -> list[dict]:
    source_type = source["type"]
    if source_type == "arxiv":
        return fetch_arxiv(source, now)
    if source_type == "hf_papers":
        return fetch_hf_papers(source, now)
    raise ValueError(f"Unsupported API source type: {source_type}")


def dedupe_items(items: list[dict]) -> list[dict]:
    deduped: list[dict] = []
    seen_urls: set[str] = set()
    for item in items:
        url = item["url"]
        if url in seen_urls:
            continue
        seen_urls.add(url)
        deduped.append(item)
    return deduped


def main() -> None:
    args = parse_args()
    ensure_data_dirs()
    now = utc_now()
    output_date = args.date or today_str(now)
    sources = load_sources(args.sources)
    all_items: list[dict] = []

    for source in sources.get("rss", []):
        if not is_enabled(source):
            log.info(
                "source skipped",
                extra={"source_name": source["name"], "source_type": "rss", "reason": source.get("note", "disabled")},
            )
            continue
        try:
            items = fetch_rss(source, now)
            all_items.extend(items)
            log.info("source fetched", extra={"source_name": source["name"], "source_type": "rss", "count": len(items)})
        except Exception as exc:  # noqa: BLE001
            log.error("source fetch failed", extra={"source_name": source["name"], "source_type": "rss", "error": str(exc)})

    for source in sources.get("api", []):
        if not is_enabled(source):
            log.info(
                "source skipped",
                extra={"source_name": source["name"], "source_type": source.get("type"), "reason": source.get("note", "disabled")},
            )
            continue
        try:
            items = fetch_api_source(source, now)
            all_items.extend(items)
            log.info("source fetched", extra={"source_name": source["name"], "source_type": source["type"], "count": len(items)})
        except Exception as exc:  # noqa: BLE001
            log.error("source fetch failed", extra={"source_name": source["name"], "source_type": source.get("type"), "error": str(exc)})

    deduped_items = dedupe_items(all_items)
    output_path = RAW_DIR / f"{output_date}.json"
    write_json(output_path, deduped_items)
    log.info(
        "fetch complete",
        extra={
            "output": str(output_path.relative_to(output_path.parent.parent.parent)),
            "total_raw": len(all_items),
            "total_unique": len(deduped_items),
        },
    )


if __name__ == "__main__":
    main()
