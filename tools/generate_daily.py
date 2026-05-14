from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

import yaml

try:
    from common import DAILY_DIR, DATA_DIR, SCORED_DIR, ensure_data_dirs, isoformat_z, load_json, today_str, utc_now, write_json
    from logger import get_logger
except ModuleNotFoundError:
    from tools.common import DAILY_DIR, DATA_DIR, SCORED_DIR, ensure_data_dirs, isoformat_z, load_json, today_str, utc_now, write_json
    from tools.logger import get_logger


CATEGORY_LABELS = {
    "ai-models": "模型发布/更新",
    "ai-products": "产品发布/更新",
    "industry": "行业动态",
    "paper": "论文研究",
    "tip": "技巧与观点",
    "cn-media": "中文媒体精选",
}
INDEX_PATH = DATA_DIR / "index.json"
log = get_logger("daily")


def sort_score(item: dict) -> float:
    return float(item.get("rank_score", item.get("score", 0)) or 0)


def sort_archive_items(items: list[dict]) -> list[dict]:
    return sorted(items, key=lambda item: (-sort_score(item), item.get("published_at", "")))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate AIpulse daily JSON")
    parser.add_argument("--date", help="Target date, format YYYY-MM-DD")
    parser.add_argument("--input", help="Explicit scored input path")
    parser.add_argument("--sources", default=str(Path(__file__).with_name("sources.yaml")))
    return parser.parse_args()


def load_daily_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    return payload.get("daily", {})


def build_sections(items: list[dict], category_limits: dict[str, int]) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        grouped[item["category"]].append(item)

    sections: list[dict] = []
    for category, label in CATEGORY_LABELS.items():
        category_items = grouped.get(category, [])
        if not category_items:
            continue
        ordered_items = sorted(category_items, key=lambda item: (-sort_score(item), item.get("published_at", "")))
        limit = category_limits.get(category)
        if limit:
            ordered_items = ordered_items[:limit]
        sections.append({"category": category, "label": label, "items": [to_public_item(item) for item in ordered_items]})
    return sections


def to_public_item(item: dict) -> dict:
    title_en = item.get("title", "").strip()
    title_zh = item.get("title_zh", "").strip() or title_en
    summary_zh = item.get("summary_zh", "").strip() or item.get("summary", "").strip()
    source = item.get("source", "")
    published_at = item.get("published_at")

    public_item = {
        "id": item.get("id"),
        "title": title_zh,
        "title_en": title_en if title_en and title_en != title_zh else None,
        "url": item.get("url"),
        "source": source,
        "source_type": item.get("source_type"),
        "sourceName": source,
        "sourceUrl": item.get("url"),
        "category": item.get("category"),
        "score": item.get("score"),
        "rank_score": item.get("rank_score", item.get("score")),
        "rankingScore": item.get("rank_score", item.get("score")),
        "summary": summary_zh,
        "summary_zh": summary_zh,
        "publishedAt": published_at,
        "published_at": published_at,
        "votes_count": item.get("votes_count"),
        "featured": item.get("featured"),
        "topics": item.get("topics") or [],
        "score_details": item.get("score_details") or None,
    }
    return public_item


def build_archive_entry(payload: dict) -> dict:
    sections = payload.get("sections") or []
    items = payload.get("items") or []
    if not items and sections:
        items = [item for section in sections for item in section.get("items", [])]

    highlights = sort_archive_items(list(items))[:3]
    generated_at = str(payload.get("generatedAt") or payload.get("generated_at") or "")

    return {
        "date": payload.get("date"),
        "generated_at": generated_at,
        "generatedAt": generated_at,
        "total": int(payload.get("total") or len(items)),
        "sectionCount": len(sections),
        "highlights": highlights,
    }


def load_archive_entries() -> list[dict]:
    index_payload = load_json(INDEX_PATH, default={}) or {}
    raw_entries = (index_payload.get("entries") or []) if isinstance(index_payload, dict) else []
    indexed_entries = [
        entry
        for entry in raw_entries
        if isinstance(entry, dict) and entry.get("date")
    ]
    if not indexed_entries:
        entries: list[dict] = []
        for path in sorted(DAILY_DIR.glob("*.json"), key=lambda item: item.name, reverse=True):
            payload = load_json(path, default={})
            if not isinstance(payload, dict) or not payload.get("date"):
                continue
            entries.append(build_archive_entry(payload))
        return entries

    entries_by_date = {entry["date"]: entry for entry in indexed_entries}
    indexed_dates = set(entries_by_date)
    file_dates = {path.stem for path in DAILY_DIR.glob("*.json")}
    missing_dates = sorted(file_dates - indexed_dates, reverse=True)
    for date in missing_dates:
        payload = load_json(DAILY_DIR / f"{date}.json", default={})
        if isinstance(payload, dict) and payload.get("date"):
            entries_by_date[date] = build_archive_entry(payload)

    return sorted(entries_by_date.values(), key=lambda entry: entry["date"], reverse=True)


def write_archive_index(payload: dict, generated_at: str) -> None:
    entries = load_archive_entries()
    entries_by_date = {entry["date"]: entry for entry in entries if entry.get("date")}
    current_entry = build_archive_entry(payload)
    if current_entry.get("date"):
        entries_by_date[str(current_entry["date"])] = current_entry

    ordered_entries = sorted(entries_by_date.values(), key=lambda entry: entry["date"], reverse=True)
    index_payload = {
        "generated_at": generated_at,
        "generatedAt": generated_at,
        "count": len(ordered_entries),
        "total": len(ordered_entries),
        "entries": ordered_entries,
    }
    write_json(INDEX_PATH, index_payload)


def collect_latest(days: int = 7) -> list[dict]:
    index_payload = load_json(INDEX_PATH, default={}) or {}
    indexed_dates = [
        str(entry.get("date", "")).strip()
        for entry in index_payload.get("entries", [])
        if isinstance(entry, dict) and str(entry.get("date", "")).strip()
    ]
    file_dates = [path.stem for path in sorted(DAILY_DIR.glob("*.json"), key=lambda item: item.name, reverse=True)[:days]]
    dates = sorted(set(indexed_dates) | set(file_dates), reverse=True)[:days]

    aggregated: list[dict] = []
    for date in dates:
        payload = load_json(DAILY_DIR / f"{date}.json", default={})
        if payload.get("items"):
            aggregated.extend(payload.get("items", []))
            continue
        for section in payload.get("sections", []):
            aggregated.extend(section.get("items", []))
    aggregated = sort_archive_items(aggregated)
    return aggregated


def main() -> None:
    args = parse_args()
    ensure_data_dirs()
    daily_config = load_daily_config(args.sources)
    category_limits = daily_config.get(
        "category_limits",
        {"ai-models": 4, "ai-products": 4, "industry": 4, "paper": 8, "tip": 4},
    )
    target_date = args.date or today_str()
    input_path = Path(args.input) if args.input else SCORED_DIR / f"{target_date}.json"
    scored_items = load_json(input_path, default=[])
    if not scored_items:
        raise RuntimeError(f"No scored items found at {input_path}")

    generated_at = isoformat_z(utc_now())
    ordered_items = sorted(scored_items, key=lambda item: (-sort_score(item), item.get("published_at", "")))
    sections = build_sections(ordered_items, category_limits)
    public_items = [item for section in sections for item in section["items"]]
    daily_payload = {
        "date": target_date,
        "generated_at": generated_at,
        "generatedAt": generated_at,
        "total": len(public_items),
        "count": len(public_items),
        "sections": sections,
        "items": public_items,
    }

    output_path = DAILY_DIR / f"{target_date}.json"
    write_json(output_path, daily_payload)
    write_archive_index(daily_payload, generated_at)

    latest_payload = {
        "generated_at": generated_at,
        "generatedAt": generated_at,
        "days": 7,
        "total": 0,
        "count": 0,
        "items": collect_latest(7),
    }
    latest_payload["total"] = len(latest_payload["items"])
    latest_payload["count"] = latest_payload["total"]
    latest_path = DATA_DIR / "latest.json"
    write_json(latest_path, latest_payload)

    for section in sections:
        log.info("section generated", extra={"category": section["category"], "count": len(section["items"])})
    log.info(
        "daily complete",
        extra={
            "output": str(output_path.relative_to(output_path.parent.parent.parent)),
            "latest_output": str(latest_path.relative_to(latest_path.parent.parent)),
            "total": len(public_items),
        },
    )


if __name__ == "__main__":
    main()
