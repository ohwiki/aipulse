# AIpulse 代码质量改进任务

> 基于代码评审结果，按优先级排列。Critical 已修复，Warning 和 Suggestion 待执行。

## 已修复（by Kiro）

- [x] T0-1: tarfile.extractall() 加 filter='data'
- [x] T0-2: 创建 astro.config.mjs
- [x] T0-3: pyproject.toml 锁定依赖版本

---

## Python Pipeline 改进

### T1: 加测试（优先级最高）

创建 `tests/` 目录，用 pytest。先覆盖纯函数：

```
tests/
├── test_common.py          # parse_datetime, today_str, item_id, normalize_whitespace
├── test_candidates.py      # is_candidate, select_candidates, with_inferred_category
├── test_scoring.py         # parse_score_payload, parse_summary_json, heuristic_score, should_filter
├── test_fetch.py           # dedupe_items, source_matches_keywords
└── test_generate.py        # build_sections, build_archive_entry
```

要求：
- 每个函数至少 2 个测试用例（正常 + 边界）
- LLM 调用用 mock，不要真实请求
- `pyproject.toml` 加 `[tool.pytest.ini_options]`

### T2: 定义数据模型（TypedDict）

在 `tools/models.py` 中定义：

```python
from typing import TypedDict

class RawItem(TypedDict):
    id: str
    title: str
    url: str
    source: str
    category: str
    summary: str
    published_at: str

class ScoredItem(RawItem):
    score: int
    rank_score: float
    score_reason: str
    title_zh: str
    summary_zh: str

class PublicItem(TypedDict):
    id: str
    title: str
    url: str
    source: str
    category: str
    summary: str
    publishedAt: str
    score: int
```

然后在各模块中使用这些类型替代裸 dict。

### T3: 拆分 score_and_filter.py

当前 650+ 行，拆成：

```
tools/
├── llm_client.py       # call_llm, call_llm_with_retry, parse_score_payload, parse_summary_json
├── scoring.py          # score_item, heuristic_score, should_filter, prepare_item_for_scoring
├── candidates.py       # is_candidate, select_candidates, candidate_priority, with_inferred_category
└── score_and_filter.py # 只保留 CLI 入口 + 编排逻辑（<100行）
```

### T4: 做成正式 package

- 加 `tools/__init__.py`
- 删除所有 `try: from common ... except: from tools.common ...` 模式
- `pyproject.toml` 加 `[project.scripts]` 或用 `python -m tools.fetch_sources` 方式运行
- 更新 workflow 中的调用方式

### T5: 改进错误处理

- `content_fetcher.py`: 所有 except 块加 `log.warning` 或 `log.error`，不要静默返回 None
- `fetch_sources.py`: catch-all 加 `exc_info=True` 记录 traceback
- `score_and_filter.py`: retry 失败时记录完整错误而不是只记 status code
- `sync_data_branch.py`: 用项目的 logger 替代 print()

### T6: 提取 build_item 工厂函数

在 `common.py` 中加：

```python
def build_raw_item(*, title: str, url: str, source: str, category: str, summary: str = "", published_at: str = "") -> RawItem:
    return {
        "id": item_id(url + title),
        "title": normalize_whitespace(title),
        "url": url,
        "source": source,
        "category": category,
        "summary": summary,
        "published_at": published_at or isoformat_z(utc_now()),
    }
```

替换 fetch_rss/fetch_arxiv/fetch_hf_papers/fetch_producthunt/fetch_jina_list 中重复的 dict 构造。

### T7: 配置统一

- `LOCAL_TZ` 改为从环境变量读取：`ZoneInfo(os.getenv("TZ", "Asia/Shanghai"))`
- 统一 AppConfig 覆盖所有配置（Product Hunt credentials、timezone、source limits）
- `.env.example` 和 `common.py` 默认值保持一致

---

## 前端改进

### T8: 创建 astro.config.mjs（已完成）

### T9: 加 JSON schema 校验

在 `src/lib/content.ts` 的 `readJson` 函数中加 Zod 校验：

```typescript
import { z } from 'zod';

const PulseItemSchema = z.object({
  id: z.string(),
  title: z.string().min(1),
  url: z.string().url(),
  source: z.string(),
  category: z.string(),
  summary: z.string(),
  publishedAt: z.string(),
});
```

parse 失败时 log warning 并跳过该条目，不要让整个 build 挂掉。

### T10: 修复无障碍问题

- `NewsCard`: 外链加 `aria-label="查看原文（新窗口打开）"`
- `ArchiveDayCard`: 改用 heading-link + `::after` stretch 模式
- `global.css`: `--text-soft` 从 `#7a7a85` 改为 `#6b6b75`

### T11: 提取共享常量

- 创建 `src/lib/constants.ts`，放 site links、breakpoints
- `TrustLinks` 和 `SiteFooter` 共用 link 列表
- `index.astro` 的 intro 改用 `PageIntro` 组件

### T12: 加 build-time 缓存

在 `src/lib/content.ts` 加模块级 Map 缓存：

```typescript
const jsonCache = new Map<string, unknown>();

function readJson<T>(path: string): T | null {
  if (jsonCache.has(path)) return jsonCache.get(path) as T;
  // ... read and parse ...
  jsonCache.set(path, result);
  return result;
}
```

---

## 给 Codex 的执行指令

> 按 T1 → T2 → T3 → T5 → T6 顺序执行 Python 改进。
> 按 T9 → T10 → T11 顺序执行前端改进。
> T4 和 T7 可以最后做。
> 每个 task 完成后 git commit。
> 测试用 pytest，前端类型用 Zod。
