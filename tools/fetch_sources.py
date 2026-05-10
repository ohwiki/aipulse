from __future__ import annotations

import argparse
import html
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import struct_time

import feedparser
import requests
import yaml
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from common import RAW_DIR, ensure_data_dirs, isoformat_z, item_id, local_date_str_from_utc, normalize_whitespace, parse_datetime, today_str, utc_now, write_json
    from logger import get_logger
except ModuleNotFoundError:
    from tools.common import RAW_DIR, ensure_data_dirs, isoformat_z, item_id, local_date_str_from_utc, normalize_whitespace, parse_datetime, today_str, utc_now, write_json
    from tools.logger import get_logger


ARXIV_API_URL = "https://export.arxiv.org/api/query"
PRODUCTHUNT_GRAPHQL_URL = "https://api.producthunt.com/v2/api/graphql"
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


def source_matches_keywords(source: dict, *parts: str) -> bool:
    keywords = source.get("keywords_any") or []
    if not keywords:
        return True
    haystack = " ".join(part for part in parts if part).lower()
    return any(str(keyword).lower() in haystack for keyword in keywords)


def within_source_window(value: datetime, now: datetime, source: dict) -> bool:
    window_hours = int(source.get("window_hours", 24))
    return value >= now - timedelta(hours=window_hours)


def resolve_target_window(date_value: str | None) -> tuple[datetime, datetime]:
    if not date_value:
        end_at = utc_now()
        return end_at - timedelta(hours=24), end_at

    target_day = datetime.fromisoformat(date_value).date()
    start_at = datetime(target_day.year, target_day.month, target_day.day, tzinfo=timezone.utc)
    end_at = start_at + timedelta(days=1)
    return start_at, end_at


def within_target_window(value: datetime, start_at: datetime, end_at: datetime) -> bool:
    return start_at <= value < end_at


def feed_time_to_datetime(parsed_time: struct_time | None) -> datetime | None:
    if parsed_time is None:
        return None
    return datetime(*parsed_time[:6], tzinfo=timezone.utc)


def clean_summary(value: str | None) -> str:
    text = normalize_whitespace(value)
    return html.unescape(text)


def build_retry_session() -> requests.Session:
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


def fetch_rss(source: dict, now: datetime, start_at: datetime, end_at: datetime) -> list[dict]:
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
        if not published or not within_target_window(published, start_at, end_at):
            continue
        url = getattr(entry, "link", "").strip()
        if not url:
            continue
        title = normalize_whitespace(getattr(entry, "title", ""))
        summary = clean_summary(getattr(entry, "summary", "") or getattr(entry, "description", ""))
        if not source_matches_keywords(source, title, summary, url):
            continue
        items.append(
            {
                "id": item_id(url),
                "title": title,
                "url": url,
                "source": source["name"],
                "category": source["category"],
                "summary": summary,
                "published_at": isoformat_z(published),
            }
        )
    return items


def fetch_arxiv(source: dict, now: datetime, start_at: datetime, end_at: datetime) -> list[dict]:
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
        if not within_target_window(published, start_at, end_at):
            continue
        url = entry.findtext("atom:id", default="", namespaces=ATOM_NS).strip()
        if not url:
            continue
        summary = entry.findtext("atom:summary", default="", namespaces=ATOM_NS)
        title = entry.findtext("atom:title", default="", namespaces=ATOM_NS)
        clean_title = normalize_whitespace(title)
        clean_summary_text = clean_summary(summary)
        if not source_matches_keywords(source, clean_title, clean_summary_text, url):
            continue
        items.append(
            {
                "id": item_id(url),
                "title": clean_title,
                "url": url,
                "source": source["name"],
                "category": source["category"],
                "summary": clean_summary_text,
                "published_at": isoformat_z(published),
            }
        )
    return items


def fetch_hf_papers(source: dict, now: datetime, start_at: datetime, end_at: datetime) -> list[dict]:
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
        if not within_target_window(published, start_at, end_at):
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
        clean_title = normalize_whitespace(str(title))
        clean_summary_text = clean_summary(str(summary))
        if not source_matches_keywords(source, clean_title, clean_summary_text, str(url)):
            continue
        items.append(
            {
                "id": item_id(url),
                "title": clean_title,
                "url": url.strip(),
                "source": source["name"],
                "category": source["category"],
                "summary": clean_summary_text,
                "published_at": isoformat_z(published),
            }
        )
    return items


def get_producthunt_token() -> str:
    developer_token = os.getenv("PRODUCTHUNT_DEVELOPER_TOKEN", "").strip()
    if developer_token:
        return developer_token

    client_id = os.getenv("PRODUCTHUNT_CLIENT_ID", "").strip()
    client_secret = os.getenv("PRODUCTHUNT_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise RuntimeError(
            "Product Hunt credentials missing. Set PRODUCTHUNT_DEVELOPER_TOKEN "
            "or PRODUCTHUNT_CLIENT_ID and PRODUCTHUNT_CLIENT_SECRET."
        )

    response = requests.post(
        "https://api.producthunt.com/v2/oauth/token",
        json={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials",
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    token = str(payload.get("access_token", "")).strip()
    if not token:
        raise RuntimeError("Product Hunt OAuth response did not include access_token")
    return token


def producthunt_matches_keywords(post: dict, source: dict) -> bool:
    return source_matches_keywords(
        source,
        str(post.get("name", "")),
        str(post.get("tagline", "")),
        str(post.get("description", "")),
        str(post.get("topics_text", "")),
    )


def fetch_producthunt(source: dict, now: datetime, start_at: datetime, end_at: datetime) -> list[dict]:
    token = get_producthunt_token()
    session = build_retry_session()
    max_results = int(source.get("max_results", 20))
    page_size = min(max_results, int(source.get("page_size", 20)))
    posted_after = start_at.astimezone(timezone.utc)
    posted_before = end_at.astimezone(timezone.utc)

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "aipulse/1.0",
    }
    query = """
    query FetchPosts($first: Int!, $after: String, $postedAfter: DateTime!, $postedBefore: DateTime!) {
      posts(first: $first, after: $after, order: VOTES, postedAfter: $postedAfter, postedBefore: $postedBefore) {
        nodes {
          id
          name
          tagline
          description
          votesCount
          createdAt
          featuredAt
          website
          url
          topics {
            edges {
              node {
                id
                name
                slug
              }
            }
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
    """

    items: list[dict] = []
    cursor: str | None = None
    has_next_page = True
    while has_next_page and len(items) < max_results:
        response = session.post(
            PRODUCTHUNT_GRAPHQL_URL,
            headers=headers,
            json={
                "query": query,
                "variables": {
                    "first": page_size,
                    "after": cursor,
                    "postedAfter": isoformat_z(posted_after),
                    "postedBefore": isoformat_z(posted_before),
                },
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("errors"):
            raise RuntimeError(f"Product Hunt GraphQL error: {payload['errors']}")

        posts_payload = payload.get("data", {}).get("posts") or {}
        for post in posts_payload.get("nodes", []):
            published_at = parse_datetime(post.get("createdAt"))
            if not published_at or not within_target_window(published_at, start_at, end_at):
                continue

            topic_nodes = [
                edge.get("node", {})
                for edge in ((post.get("topics") or {}).get("edges") or [])
                if isinstance(edge, dict)
            ]
            post["topics_text"] = " ".join(
                normalize_whitespace(str(node.get("name", ""))) for node in topic_nodes if node.get("name")
            )
            if not producthunt_matches_keywords(post, source):
                continue

            url = str(post.get("url", "")).strip()
            if not url:
                continue

            summary_parts = [post.get("tagline", ""), post.get("description", "")]
            summary = normalize_whitespace(" ".join(part for part in summary_parts if part))
            items.append(
                {
                    "id": item_id(url),
                    "title": normalize_whitespace(str(post.get("name", ""))),
                    "url": url,
                    "source": source["name"],
                    "category": source["category"],
                    "summary": summary,
                    "published_at": isoformat_z(published_at),
                    "votes_count": post.get("votesCount"),
                    "featured": bool(post.get("featuredAt")),
                    "website": post.get("website"),
                    "topics": [
                        {
                            "id": node.get("id"),
                            "name": node.get("name"),
                            "slug": node.get("slug"),
                        }
                        for node in topic_nodes
                    ],
                }
            )
            if len(items) >= max_results:
                break

        page_info = posts_payload.get("pageInfo") or {}
        has_next_page = bool(page_info.get("hasNextPage")) and len(items) < max_results
        cursor = page_info.get("endCursor")

    items.sort(key=lambda item: (-int(item.get("votes_count") or 0), item.get("published_at", "")))
    return items[:max_results]


def fetch_api_source(source: dict, now: datetime, start_at: datetime, end_at: datetime) -> list[dict]:
    source_type = source["type"]
    if source_type == "arxiv":
        return fetch_arxiv(source, now, start_at, end_at)
    if source_type == "hf_papers":
        return fetch_hf_papers(source, now, start_at, end_at)
    if source_type == "producthunt":
        return fetch_producthunt(source, now, start_at, end_at)
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
    output_date = args.date or local_date_str_from_utc(now)
    start_at, end_at = resolve_target_window(args.date)
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
            items = fetch_rss(source, now, start_at, end_at)
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
            items = fetch_api_source(source, now, start_at, end_at)
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
