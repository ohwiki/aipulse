from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from time import perf_counter

import os

import requests

try:
    from common import SCORED_DIR, estimate_tokens, ensure_data_dirs, is_mostly_ascii, load_app_config, load_json, today_str, write_json
    from content_fetcher import fetch as fetch_content
    from logger import get_logger
except ModuleNotFoundError:
    from tools.common import SCORED_DIR, estimate_tokens, ensure_data_dirs, is_mostly_ascii, load_app_config, load_json, today_str, write_json
    from tools.content_fetcher import fetch as fetch_content
    from tools.logger import get_logger


SCORE_PROMPT = """你是一个 AI 资讯编辑。请对以下条目打分（1-10），标准：
- 对中文 AI 从业者的价值（新模型发布、重要产品更新、行业趋势）
- 信息的新鲜度和独特性
- 不是广告、不是水文

标题：{title}
来源：{source}
摘要：{summary}

只输出一个数字。"""

SCORE_RETRY_PROMPT = """请只输出一个 1 到 10 的阿拉伯数字，不要解释，不要输出任何其他文字。

标题：{title}
来源：{source}
摘要：{summary}"""

SUMMARY_PROMPT = """用一句中文（50字以内）概括这条 AI 资讯的核心信息。不要套话，直接说发生了什么。
同时给出一个准确的中文标题（20字以内）。

标题：{title}
摘要：{summary}

输出 JSON：{{"title_zh": "...", "summary_zh": "..."}}"""

SUMMARY_RETRY_PROMPT = """请严格输出一个 JSON 对象，不要解释，不要输出 Markdown，不要输出代码块。
格式必须是：{{"title_zh":"...","summary_zh":"..."}}

标题：{title}
摘要：{summary}"""
log = get_logger("score")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score and filter AIpulse source items")
    parser.add_argument("--date", help="Target date, format YYYY-MM-DD")
    parser.add_argument("--input", help="Explicit raw input path")
    parser.add_argument("--dry-run", action="store_true", help="Skip LLM calls and use heuristic scores/localized fields")
    return parser.parse_args()


def call_llm(prompt: str, model: str | None = None, temperature: float = 0.1, max_tokens: int = 200) -> str:
    """调用 LLM，返回文本响应"""
    config = load_app_config(require_api_key=True)
    api_key = config.api_key
    base_url = config.base_url
    model_name = model or os.environ.get("NULLCLAW_MODEL", config.model)

    response = requests.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=60,
    )
    response.raise_for_status()
    body = response.json()
    choice = body["choices"][0]
    content = (choice.get("message", {}).get("content") or "").strip()
    if content:
        return content
    reasoning = (choice.get("message", {}).get("reasoning_content") or "").strip()
    if reasoning:
        return reasoning
    raise ValueError(f"LLM returned empty content: finish_reason={choice.get('finish_reason')!r}")


def heuristic_score(item: dict) -> int:
    score = 5
    source = str(item.get("source", "")).lower()
    title = str(item.get("title", ""))
    summary = str(item.get("summary", ""))
    category = str(item.get("category", ""))

    if category in {"ai-models", "ai-products", "paper"}:
        score += 1
    if any(keyword in source for keyword in ("openai", "deepmind", "huggingface", "arxiv", "product hunt")):
        score += 1
    if len(title) > 20:
        score += 1
    if len(summary) > 80:
        score += 1
    if any(keyword in (title + " " + summary).lower() for keyword in ("model", "agent", "release", "benchmark", "paper", "launch")):
        score += 1
    return max(1, min(score, 10))


def heuristic_summary(item: dict) -> dict[str, str]:
    title = clean_text(str(item.get("title", "")).strip())
    summary = clean_text(str(item.get("summary", "")).strip())
    source = str(item.get("source", "")).strip()
    category = str(item.get("category", "")).strip()

    if category == "paper":
        prefix = "论文"
    elif category == "ai-models":
        prefix = "模型"
    elif category == "ai-products":
        prefix = "产品"
    else:
        prefix = "AI资讯"

    short_title = title[:18] if title else prefix
    title_zh = short_title if contains_chinese(short_title) else f"{prefix}更新：{short_title}"[:20]

    if summary:
        core = summary[:46]
    elif title:
        core = title[:46]
    else:
        core = f"{source}有新的{prefix}动态"

    summary_zh = core
    return {"title_zh": title_zh, "summary_zh": summary_zh}


def clean_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def contains_chinese(value: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in value)


def parse_score(text: str) -> int:
    match = re.search(r"\b([1-9]|10)\b", text)
    if not match:
        raise ValueError(f"Unable to parse score from: {text!r}")
    score = int(match.group(1))
    return max(1, min(score, 10))


def parse_summary_json(text: str) -> dict[str, str]:
    candidate = text.strip()
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"Unable to parse summary JSON from: {text!r}")
    payload = json.loads(candidate[start : end + 1])
    title_zh = str(payload.get("title_zh", "")).strip()
    summary_zh = str(payload.get("summary_zh", "")).strip()
    if not title_zh or not summary_zh:
        raise ValueError(f"Incomplete summary JSON: {text!r}")
    return {"title_zh": title_zh, "summary_zh": summary_zh}


def needs_translation(item: dict) -> bool:
    return is_mostly_ascii(item.get("title", "")) or is_mostly_ascii(item.get("summary", ""))


def score_item(item: dict) -> int:
    prompt = SCORE_PROMPT.format(
        title=item["title"],
        source=item["source"],
        summary=item["summary"],
    )
    try:
        return parse_score(call_llm(prompt, temperature=0.1, max_tokens=128))
    except ValueError:
        retry_prompt = SCORE_RETRY_PROMPT.format(
            title=item["title"],
            source=item["source"],
            summary=item["summary"],
        )
        return parse_score(call_llm(retry_prompt, temperature=0, max_tokens=32))


def summarize_item(item: dict) -> dict[str, str]:
    prompt = SUMMARY_PROMPT.format(title=item["title"], summary=item["summary"])
    try:
        return parse_summary_json(call_llm(prompt, temperature=0.3, max_tokens=256))
    except ValueError:
        retry_prompt = SUMMARY_RETRY_PROMPT.format(title=item["title"], summary=item["summary"])
        return parse_summary_json(call_llm(retry_prompt, temperature=0, max_tokens=256))


def prepare_item_for_scoring(item: dict) -> dict:
    enriched = dict(item)
    enriched["title"] = clean_text(str(item.get("title", "")).strip())
    enriched["summary"] = clean_text(str(item.get("summary", "")).strip())
    summary = enriched["summary"]
    if len(summary) >= 100:
        return enriched

    content = fetch_content(item["url"])
    if not content:
        return enriched

    enriched["summary"] = clean_text(content)[:4000]
    return enriched


def main() -> None:
    args = parse_args()
    ensure_data_dirs()
    target_date = args.date or today_str()
    input_path = Path(args.input) if args.input else Path(__file__).resolve().parent.parent / "data" / "raw" / f"{target_date}.json"
    raw_items = load_json(input_path, default=[])
    if not raw_items:
        raise RuntimeError(f"No raw items found at {input_path}")

    if not args.dry_run:
        config = load_app_config(require_api_key=False)
        if not config.api_key:
            raise RuntimeError(
                "NULLCLAW_API_KEY is required for scoring. "
                "Set NULLCLAW_API_KEY or rerun with --dry-run to validate the pipeline without LLM calls."
            )

    scored_items: list[dict] = []
    estimated_tokens = 0
    started_at = perf_counter()

    for index, item in enumerate(raw_items, start=1):
        try:
            score_input = prepare_item_for_scoring(item)
            if args.dry_run:
                score = heuristic_score(score_input)
            else:
                try:
                    score = score_item(score_input)
                except Exception as exc:  # noqa: BLE001
                    log.warning(
                        "score fallback",
                        extra={"item_id": item["id"], "error": str(exc)},
                    )
                    score = heuristic_score(score_input)
            estimated_tokens += estimate_tokens(score_input["title"], score_input["summary"])
            if score < 7:
                log.info(
                    "item filtered out",
                    extra={"item_id": item["id"], "score": score, "index": index, "total": len(raw_items)},
                )
                continue

            localized = {
                "title_zh": item["title"],
                "summary_zh": item["summary"],
            }
            if needs_translation(item):
                if args.dry_run:
                    localized = heuristic_summary(item)
                else:
                    try:
                        localized = summarize_item(item)
                        estimated_tokens += estimate_tokens(item["title"], item["summary"]) * 2
                    except Exception as exc:  # noqa: BLE001
                        log.warning(
                            "summary fallback",
                            extra={"item_id": item["id"], "error": str(exc)},
                        )
                        localized = heuristic_summary(item)

            scored_items.append(
                {
                    **item,
                    "score": score,
                    "title_zh": localized["title_zh"],
                    "summary_zh": localized["summary_zh"],
                }
            )
            log.info(
                "item selected",
                extra={"item_id": item["id"], "score": score, "index": index, "total": len(raw_items)},
            )
        except Exception as exc:  # noqa: BLE001
            log.error(
                "item scoring failed",
                extra={"item_id": item.get("id"), "error": str(exc), "index": index, "total": len(raw_items)},
            )

    duration_ms = int((perf_counter() - started_at) * 1000)
    output_path = SCORED_DIR / f"{target_date}.json"
    write_json(output_path, scored_items)
    log.info(
        "score complete",
        extra={
            "output": str(output_path.relative_to(output_path.parent.parent.parent)),
            "total_raw": len(raw_items),
            "total_selected": len(scored_items),
            "duration_ms": duration_ms,
            "estimated_tokens": estimated_tokens,
            "dry_run": args.dry_run,
        },
    )


if __name__ == "__main__":
    main()
