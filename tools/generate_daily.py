from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

try:
    from common import DAILY_DIR, DATA_DIR, SCORED_DIR, ensure_data_dirs, isoformat_z, load_json, parse_datetime, today_str, utc_now, write_json
    from logger import get_logger
except ModuleNotFoundError:
    from tools.common import DAILY_DIR, DATA_DIR, SCORED_DIR, ensure_data_dirs, isoformat_z, load_json, parse_datetime, today_str, utc_now, write_json
    from tools.logger import get_logger


CATEGORY_LABELS = {
    "ai-models": "模型发布/更新",
    "ai-products": "产品发布/更新",
    "industry": "行业动态",
    "paper": "论文研究",
    "tip": "技巧与观点",
}
log = get_logger("daily")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate AIpulse daily JSON")
    parser.add_argument("--date", help="Target date, format YYYY-MM-DD")
    parser.add_argument("--input", help="Explicit scored input path")
    return parser.parse_args()


def build_sections(items: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        grouped[item["category"]].append(item)

    sections: list[dict] = []
    for category, label in CATEGORY_LABELS.items():
        category_items = grouped.get(category, [])
        if not category_items:
            continue
        ordered_items = sorted(category_items, key=lambda item: (-item.get("score", 0), item.get("published_at", "")))
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
        "sourceName": source,
        "sourceUrl": item.get("url"),
        "category": item.get("category"),
        "score": item.get("score"),
        "summary": summary_zh,
        "summary_zh": summary_zh,
        "publishedAt": published_at,
        "published_at": published_at,
    }
    return public_item


def collect_latest(days: int = 7) -> list[dict]:
    cutoff = utc_now() - timedelta(days=days)
    aggregated: list[dict] = []
    for path in sorted(DAILY_DIR.glob("*.json"), reverse=True):
        if path.name == "latest.json":
            continue
        payload = load_json(path, default={})
        date_value = parse_datetime(payload.get("generatedAt") or payload.get("generated_at"))
        if date_value and date_value < cutoff:
            continue
        if payload.get("items"):
            aggregated.extend(payload.get("items", []))
            continue
        for section in payload.get("sections", []):
            aggregated.extend(section.get("items", []))
    aggregated.sort(key=lambda item: (item.get("published_at", ""), item.get("score", 0)), reverse=True)
    return aggregated


def main() -> None:
    args = parse_args()
    ensure_data_dirs()
    target_date = args.date or today_str()
    input_path = Path(args.input) if args.input else SCORED_DIR / f"{target_date}.json"
    scored_items = load_json(input_path, default=[])
    if not scored_items:
        raise RuntimeError(f"No scored items found at {input_path}")

    generated_at = isoformat_z(utc_now())
    ordered_items = sorted(scored_items, key=lambda item: (-item.get("score", 0), item.get("published_at", "")))
    sections = build_sections(ordered_items)
    public_items = [to_public_item(item) for item in ordered_items]
    daily_payload = {
        "date": target_date,
        "generated_at": generated_at,
        "generatedAt": generated_at,
        "total": len(ordered_items),
        "count": len(ordered_items),
        "sections": sections,
        "items": public_items,
    }

    output_path = DAILY_DIR / f"{target_date}.json"
    write_json(output_path, daily_payload)

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
            "total": len(ordered_items),
        },
    )


if __name__ == "__main__":
    main()
