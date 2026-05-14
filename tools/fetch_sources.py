"""AIpulse source fetcher — orchestrates all fetcher modules.

Reads sources.yaml, dispatches to the appropriate fetcher module,
deduplicates results, and writes raw JSON output.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

try:
    from common import RAW_DIR, ensure_data_dirs, local_date_str_from_utc, utc_now, write_json
    from logger import get_logger
    from fetchers import rss, arxiv, hf_papers, producthunt, jina
except ModuleNotFoundError:
    from tools.common import RAW_DIR, ensure_data_dirs, local_date_str_from_utc, utc_now, write_json
    from tools.logger import get_logger
    from tools.fetchers import rss, arxiv, hf_papers, producthunt, jina

log = get_logger("fetch")

# Maps source type strings to fetcher modules
API_FETCHERS = {
    "arxiv": arxiv.fetch,
    "hf_papers": hf_papers.fetch,
    "producthunt": producthunt.fetch,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch AIpulse source items")
    parser.add_argument("--date", help="Override output date, format YYYY-MM-DD")
    parser.add_argument("--sources", default=str(Path(__file__).with_name("sources.yaml")))
    return parser.parse_args()


def load_sources(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def is_enabled(source: dict) -> bool:
    return source.get("enabled", True) is not False


def resolve_target_window(date_value: str | None) -> tuple[datetime, datetime]:
    """Determine the time window for fetching items."""
    if not date_value:
        end_at = utc_now()
        return end_at - timedelta(hours=24), end_at
    target_day = datetime.fromisoformat(date_value).date()
    start_at = datetime(target_day.year, target_day.month, target_day.day, tzinfo=timezone.utc)
    return start_at, start_at + timedelta(days=1)


def dedupe_items(items: list[dict]) -> list[dict]:
    """Remove duplicates by url+title combination."""
    seen: set[str] = set()
    deduped: list[dict] = []
    for item in items:
        key = item["url"] + "|" + item.get("title", "")
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped


def fetch_source_group(sources: list[dict], source_type: str, now: datetime,
                       start_at: datetime, end_at: datetime) -> list[dict]:
    """Fetch all enabled sources in a group, handling errors per-source."""
    all_items: list[dict] = []
    for source in sources:
        if not is_enabled(source):
            log.info("source skipped", extra={
                "source_name": source["name"], "source_type": source_type,
                "reason": source.get("note", "disabled"),
            })
            continue
        try:
            items = _dispatch_fetch(source, source_type, now, start_at, end_at)
            all_items.extend(items)
            log.info("source fetched", extra={
                "source_name": source["name"], "source_type": source_type, "count": len(items),
            })
        except Exception as exc:  # noqa: BLE001
            # Try fallback URL if configured
            fallback = source.get("fallback_url")
            if fallback:
                try:
                    fallback_source = {**source, "url": fallback}
                    items = rss.fetch(fallback_source, now, start_at, end_at)
                    all_items.extend(items)
                    log.info("source fetched (fallback)", extra={
                        "source_name": source["name"], "source_type": source_type, "count": len(items),
                    })
                except Exception as exc2:  # noqa: BLE001
                    log.error("source fetch failed (both)", extra={
                        "source_name": source["name"], "error": str(exc2),
                    })
            else:
                log.error("source fetch failed", extra={
                    "source_name": source["name"], "source_type": source_type, "error": str(exc),
                })
    return all_items


def _dispatch_fetch(source: dict, source_type: str, now: datetime,
                    start_at: datetime, end_at: datetime) -> list[dict]:
    """Route a source to the correct fetcher based on its type."""
    # cn_media sources can specify a type override (e.g., jina_list)
    actual_type = source.get("type", "rss" if source_type in ("rss", "cn_media") else source_type)

    if actual_type == "jina_list":
        return jina.fetch(source, now, start_at, end_at)
    if actual_type in API_FETCHERS:
        return API_FETCHERS[actual_type](source, now, start_at, end_at)
    # Default: treat as RSS
    return rss.fetch(source, now, start_at, end_at)


def main() -> None:
    args = parse_args()
    ensure_data_dirs()
    now = utc_now()
    output_date = args.date or local_date_str_from_utc(now)
    start_at, end_at = resolve_target_window(args.date)
    sources = load_sources(args.sources)

    # Fetch all source groups
    all_items: list[dict] = []
    all_items.extend(fetch_source_group(sources.get("rss", []), "rss", now, start_at, end_at))
    all_items.extend(fetch_source_group(sources.get("api", []), "api", now, start_at, end_at))
    all_items.extend(fetch_source_group(sources.get("cn_media", []), "cn_media", now, start_at, end_at))

    # Deduplicate and write output
    deduped = dedupe_items(all_items)
    output_path = RAW_DIR / f"{output_date}.json"
    write_json(output_path, deduped)
    log.info("fetch complete", extra={
        "output": str(output_path.relative_to(output_path.parent.parent.parent)),
        "total_raw": len(all_items),
        "total_unique": len(deduped),
    })


if __name__ == "__main__":
    main()
