from __future__ import annotations

import argparse
import collections
import json
import time
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


SCORE_PROMPT = """你是一个 AI 资讯编辑。请用结构化 rubric 评估这条资讯是否值得进入中文 AI 从业者日报。

评分规则：
- is_ai_relevant: 是否明确与 AI/模型/Agent/AI开发工具相关
- is_real_launch_or_update: 是否是真实的新发布、公测、版本更新、论文发布或行业动态，而不是普通宣传页
- novelty: 0-3，信息新鲜度和独特性
- practitioner_value: 0-3，对中文 AI 从业者的实际价值
- signal_over_promo: 0-2，真实信号相对宣传腔的强弱
- distribution_signal: 0-2，外部热度/分发信号；仅当热度能说明这是个值得关注的发布时加分
- confidence: 0-1，你对判断的把握

额外要求：
- 如果是 Product Hunt 上高票、featured、且主题明确属于 AI/Agent/开发工具/模型应用的新品首发、公测或重要更新，应给予更高分数
- 不要因为文案像产品介绍就机械判低分，要判断它是否代表真实的产品发布和行业信号
- final_score 取 1-10 的整数。通常可按上述维度总和映射，但如果存在明显广告感或信息密度不足，可以下调

标题：{title}
来源：{source}
摘要：{summary}
补充信息：
{extra_context}

请严格输出 JSON：
{{"is_ai_relevant":true,"is_real_launch_or_update":true,"novelty":0,"practitioner_value":0,"signal_over_promo":0,"distribution_signal":0,"confidence":0,"reason":"不超过40字","final_score":1}}"""

SCORE_RETRY_PROMPT = """请严格输出一个 JSON 对象，不要解释，不要输出 Markdown，不要输出代码块。

字段必须完整：
{{"is_ai_relevant":true,"is_real_launch_or_update":true,"novelty":0,"practitioner_value":0,"signal_over_promo":0,"distribution_signal":0,"confidence":0,"reason":"简短理由","final_score":1}}

标题：{title}
来源：{source}
摘要：{summary}
补充信息：
{extra_context}"""

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


def is_producthunt_item(item: dict) -> bool:
    source = str(item.get("source", "")).lower()
    return "product hunt" in source


def producthunt_vote_bonus(item: dict) -> float:
    if not is_producthunt_item(item):
        return 0.0

    try:
        votes = int(item.get("votes_count") or 0)
    except (TypeError, ValueError):
        return 0.0

    if votes >= 120:
        return 1.0
    if votes >= 80:
        return 0.6
    if votes >= 50:
        return 0.3
    return 0.0


def ranking_score(item: dict, score: int) -> float:
    return round(score + producthunt_vote_bonus(item), 1)


def build_score_context(item: dict) -> str:
    if not is_producthunt_item(item):
        return "无"

    topics = ", ".join(
        str(topic.get("name", "")).strip()
        for topic in (item.get("topics") or [])
        if str(topic.get("name", "")).strip()
    ) or "无"
    votes = int(item.get("votes_count") or 0)
    featured = "是" if item.get("featured") else "否"
    website = str(item.get("website", "")).strip() or "无"
    return (
        f"Product Hunt votes: {votes}\n"
        f"Product Hunt featured: {featured}\n"
        f"Product Hunt topics: {topics}\n"
        f"Website: {website}"
    )


def score_floor(item: dict, llm_score: int, heuristic: int) -> int:
    if not is_producthunt_item(item):
        return llm_score

    try:
        votes = int(item.get("votes_count") or 0)
    except (TypeError, ValueError):
        votes = 0

    if votes >= 120 and heuristic >= 8:
        return max(llm_score, 6)
    if votes >= 80 and heuristic >= 8:
        return max(llm_score, 5)
    return llm_score


def fallback_score(item: dict, heuristic: int) -> int:
    if is_producthunt_item(item):
        votes = int(item.get("votes_count") or 0)
        if votes >= 120:
            return min(7, heuristic)
        if votes >= 70:
            return min(6, heuristic)
        return min(5, heuristic)

    category = str(item.get("category", ""))
    if category == "paper":
        return min(6, heuristic)
    if category == "ai-models":
        return min(6, heuristic)
    return min(5, heuristic)


def should_filter(item: dict, score: int, rank_score: float, score_payload: dict | None) -> bool:
    if score_payload and not score_payload.get("is_ai_relevant", True):
        return True

    if score >= 7:
        return False

    if not is_producthunt_item(item):
        return True

    if not score_payload:
        return True

    if not score_payload.get("is_real_launch_or_update", False):
        return True

    if rank_score >= 7 and int(item.get("votes_count") or 0) >= 70:
        return False

    return True


def is_candidate(item: dict) -> bool:
    category = str(item.get("category", ""))
    title = str(item.get("title", "")).lower()
    summary = str(item.get("summary", "")).lower()
    text = f"{title} {summary}"

    if category == "paper":
        paper_keywords = (
            "llm",
            "language model",
            "agent",
            "reasoning",
            "benchmark",
            "retrieval",
            "rag",
            "multimodal",
            "diffusion",
            "world model",
            "inference",
        )
        return any(keyword in text for keyword in paper_keywords) and len(title) >= 20

    if category == "ai-models":
        model_keywords = (
            "release",
            "launch",
            "changelog",
            "update",
            "model",
            "gemini",
            "gpt",
            "claude",
            "mistral",
            "openai",
        )
        return any(keyword in text for keyword in model_keywords)

    if is_producthunt_item(item):
        votes = int(item.get("votes_count") or 0)
        featured = bool(item.get("featured"))
        topics = " ".join(
            str(topic.get("name", "")).lower()
            for topic in (item.get("topics") or [])
            if isinstance(topic, dict)
        )
        return votes >= 70 or featured or (
            votes >= 50 and any(keyword in topics for keyword in ("artificial intelligence", "developer tools"))
        )

    if category == "ai-products":
        product_keywords = (
            "agent",
            "copilot",
            "assistant",
            "workflow",
            "developer",
            "coding",
            "ai",
            "automation",
            "launch",
            "release",
        )
        return any(keyword in text for keyword in product_keywords) and len(summary) >= 80

    return False


def candidate_priority(item: dict) -> tuple:
    category = str(item.get("category", ""))
    if is_producthunt_item(item):
        return (
            0,
            -int(bool(item.get("featured"))),
            -int(item.get("votes_count") or 0),
            item.get("published_at", ""),
        )
    if category == "ai-models":
        source = str(item.get("source", "")).lower()
        source_weight = 0 if "openai" in source else 1
        return (1, source_weight, item.get("published_at", ""))
    if category == "paper":
        title = str(item.get("title", "")).lower()
        strong_terms = sum(
            keyword in title
            for keyword in ("llm", "agent", "reasoning", "benchmark", "retrieval", "multimodal", "diffusion")
        )
        return (2, -strong_terms, item.get("published_at", ""))
    return (3, item.get("published_at", ""))


def select_candidates(items: list[dict]) -> list[dict]:
    filtered = [item for item in items if is_candidate(item)]
    by_source: dict[str, list[dict]] = collections.defaultdict(list)
    for item in filtered:
        by_source[str(item.get("source", ""))].append(item)

    source_limits = {
        "OpenAI Blog": 4,
        "Google AI Blog": 3,
        "Google Developers Blog AI": 2,
        "Google DeepMind": 3,
        "HuggingFace Blog": 3,
        "Product Hunt AI": 6,
        "HuggingFace Daily Papers": 8,
        "arXiv cs.AI": 5,
        "arXiv cs.CL": 5,
        "arXiv cs.LG": 5,
        "arXiv cs.IR": 4,
        "arXiv cs.CV": 4,
    }

    selected: list[dict] = []
    for source, source_items in by_source.items():
        limit = source_limits.get(source, 3)
        ordered = sorted(source_items, key=candidate_priority)
        selected.extend(ordered[:limit])

    selected.sort(key=candidate_priority)
    return selected


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


def parse_score_payload(text: str) -> dict:
    candidate = text.strip()
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"Unable to parse score JSON from: {text!r}")
    payload = json.loads(candidate[start : end + 1])
    final_score = int(payload["final_score"])
    return {
        "is_ai_relevant": bool(payload.get("is_ai_relevant")),
        "is_real_launch_or_update": bool(payload.get("is_real_launch_or_update")),
        "novelty": max(0, min(int(payload.get("novelty", 0)), 3)),
        "practitioner_value": max(0, min(int(payload.get("practitioner_value", 0)), 3)),
        "signal_over_promo": max(0, min(int(payload.get("signal_over_promo", 0)), 2)),
        "distribution_signal": max(0, min(int(payload.get("distribution_signal", 0)), 2)),
        "confidence": max(0, min(int(payload.get("confidence", 0)), 1)),
        "reason": str(payload.get("reason", "")).strip(),
        "final_score": max(1, min(final_score, 10)),
    }


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


def score_item(item: dict) -> dict:
    extra_context = build_score_context(item)
    prompt = SCORE_PROMPT.format(
        title=item["title"],
        source=item["source"],
        summary=item["summary"],
        extra_context=extra_context,
    )
    try:
        return parse_score_payload(call_llm(prompt, temperature=0.1, max_tokens=256))
    except (ValueError, KeyError, json.JSONDecodeError, TypeError):
        retry_prompt = SCORE_RETRY_PROMPT.format(
            title=item["title"],
            source=item["source"],
            summary=item["summary"],
            extra_context=extra_context,
        )
        return parse_score_payload(call_llm(retry_prompt, temperature=0, max_tokens=256))


def score_item_with_retry(item: dict) -> dict:
    backoffs = (3, 8, 15)
    attempt = 0
    while True:
        try:
            return score_item(item)
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            if status_code != 429 or attempt >= len(backoffs):
                raise
            delay = backoffs[attempt]
            attempt += 1
            log.warning(
                "score rate limited",
                extra={"item_id": item.get("id"), "retry_in_s": delay, "attempt": attempt},
            )
            time.sleep(delay)


def summarize_item(item: dict) -> dict[str, str]:
    prompt = SUMMARY_PROMPT.format(title=item["title"], summary=item["summary"])
    try:
        return parse_summary_json(call_llm(prompt, temperature=0.3, max_tokens=256))
    except ValueError:
        retry_prompt = SUMMARY_RETRY_PROMPT.format(title=item["title"], summary=item["summary"])
        return parse_summary_json(call_llm(retry_prompt, temperature=0, max_tokens=256))


def attach_score_details(item: dict, score_payload: dict | None) -> dict:
    if not score_payload:
        return {}
    return {
        "score_details": {
            "is_ai_relevant": score_payload["is_ai_relevant"],
            "is_real_launch_or_update": score_payload["is_real_launch_or_update"],
            "novelty": score_payload["novelty"],
            "practitioner_value": score_payload["practitioner_value"],
            "signal_over_promo": score_payload["signal_over_promo"],
            "distribution_signal": score_payload["distribution_signal"],
            "confidence": score_payload["confidence"],
            "reason": score_payload["reason"],
        }
    }


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
    candidate_items = select_candidates(raw_items)

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

    log.info(
        "candidate selection complete",
        extra={"total_raw": len(raw_items), "total_candidates": len(candidate_items)},
    )

    for index, item in enumerate(candidate_items, start=1):
        try:
            score_input = prepare_item_for_scoring(item)
            heuristic = heuristic_score(score_input)
            score_payload: dict | None = None
            if args.dry_run:
                score = heuristic
            else:
                try:
                    score_payload = score_item_with_retry(score_input)
                    score = score_floor(score_input, score_payload["final_score"], heuristic)
                except Exception as exc:  # noqa: BLE001
                    log.warning(
                        "score fallback",
                        extra={"item_id": item["id"], "error": str(exc)},
                    )
                    score = fallback_score(score_input, heuristic)
            rank_score = ranking_score(score_input, score)
            estimated_tokens += estimate_tokens(score_input["title"], score_input["summary"])
            if should_filter(score_input, score, rank_score, score_payload):
                log.info(
                    "item filtered out",
                    extra={
                        "item_id": item["id"],
                        "score": score,
                        "rank_score": rank_score,
                        "index": index,
                        "total": len(candidate_items),
                    },
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
                    "rank_score": rank_score,
                    **attach_score_details(item, score_payload),
                    "title_zh": localized["title_zh"],
                    "summary_zh": localized["summary_zh"],
                }
            )
            log.info(
                "item selected",
                extra={
                    "item_id": item["id"],
                    "score": score,
                    "rank_score": rank_score,
                    "index": index,
                    "total": len(candidate_items),
                },
            )
        except Exception as exc:  # noqa: BLE001
            log.error(
                "item scoring failed",
                extra={"item_id": item.get("id"), "error": str(exc), "index": index, "total": len(candidate_items)},
            )

    duration_ms = int((perf_counter() - started_at) * 1000)
    output_path = SCORED_DIR / f"{target_date}.json"
    write_json(output_path, scored_items)
    log.info(
        "score complete",
        extra={
            "output": str(output_path.relative_to(output_path.parent.parent.parent)),
            "total_raw": len(raw_items),
            "total_candidates": len(candidate_items),
            "total_selected": len(scored_items),
            "duration_ms": duration_ms,
            "estimated_tokens": estimated_tokens,
            "dry_run": args.dry_run,
        },
    )


if __name__ == "__main__":
    main()
