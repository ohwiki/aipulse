# AIpulse 实现计划 — P1 核心流程

> 设计文档：`~/workspace/docs/0509/aipulse-design.md`
> 目标：跑通「抓取 → LLM 打分 → 筛选 → 生成日报 JSON」的核心流程

## 仓库初始化

创建 GitHub 仓库 `ouraihub/aipulse`，结构如下：

```
aipulse/
├── .github/workflows/
│   └── fetch.yml           # 每日 cron
├── tools/
│   ├── sources.yaml        # 数据源配置
│   ├── fetch_sources.py    # 拉取所有源
│   ├── score_and_filter.py # LLM 打分筛选
│   └── generate_daily.py   # 生成日报 JSON
├── data/
│   └── .gitkeep
├── requirements.txt
└── README.md
```

---

## Tasks

### T1: 仓库骨架

创建上述目录结构和基础文件。

**requirements.txt:**
```
feedparser
requests
pyyaml
```

**README.md:** 简单说明项目是什么、怎么跑。

---

### T2: sources.yaml — 数据源配置

```yaml
rss:
  - name: OpenAI Blog
    url: https://openai.com/blog/rss.xml
    category: ai-models
  - name: Anthropic
    url: https://www.anthropic.com/rss.xml
    category: ai-models
  - name: Google DeepMind
    url: https://deepmind.google/blog/rss.xml
    category: ai-models
  - name: Meta AI
    url: https://ai.meta.com/blog/rss/
    category: ai-models
  - name: HuggingFace Blog
    url: https://huggingface.co/blog/feed.xml
    category: ai-products
  - name: Mistral AI
    url: https://mistral.ai/feed.xml
    category: ai-models
  - name: Product Hunt AI
    url: https://www.producthunt.com/feed?category=artificial-intelligence
    category: ai-products

api:
  - name: arXiv cs.AI
    type: arxiv
    query: "cat:cs.AI"
    max_results: 30
    category: paper
  - name: arXiv cs.CL
    type: arxiv
    query: "cat:cs.CL"
    max_results: 30
    category: paper
  - name: HuggingFace Daily Papers
    type: hf_papers
    url: https://huggingface.co/api/daily_papers
    category: paper
```

---

### T3: fetch_sources.py — 拉取所有源

**输入：** `sources.yaml`
**输出：** `data/raw/{date}.json`（当天所有原始条目）

逻辑：
1. 读取 `sources.yaml`
2. 对每个 RSS 源用 `feedparser` 拉取，过滤最近 24 小时的条目
3. 对 arXiv 用 urllib 调 API
4. 对 HuggingFace Daily Papers 用 requests 调 API
5. 每个条目统一为格式：
```json
{
  "id": "sha256(url)[:8]",
  "title": "原始标题",
  "url": "原始链接",
  "source": "来源名称",
  "category": "从 sources.yaml 继承",
  "summary": "RSS 的 description 或 API 返回的摘要",
  "published_at": "ISO 8601"
}
```
6. 去重（按 URL）
7. 写入 `data/raw/{date}.json`

**日志：** 每个源拉取成功/失败、条目数量、总条目数。

---

### T4: score_and_filter.py — LLM 打分筛选

**输入：** `data/raw/{date}.json`
**输出：** `data/scored/{date}.json`（带分数 + 中文标题/摘要）

逻辑：
1. 读取原始条目
2. 批量调 MiMo API 打分（每条一个请求，或批量 prompt）
3. 打分 prompt：
```
你是一个 AI 资讯编辑。请对以下条目打分（1-10），标准：
- 对中文 AI 从业者的价值（新模型发布、重要产品更新、行业趋势）
- 信息的新鲜度和独特性
- 不是广告、不是水文

标题：{title}
来源：{source}
摘要：{summary}

只输出一个数字。
```
4. 筛选 ≥7 分的条目
5. 对英文条目生成中文标题 + 50 字摘要：
```
用一句中文（50字以内）概括这条 AI 资讯的核心信息。不要套话，直接说发生了什么。
同时给出一个准确的中文标题（20字以内）。

标题：{title}
摘要：{summary}

输出 JSON：{"title_zh": "...", "summary_zh": "..."}
```
6. 写入 `data/scored/{date}.json`

**环境变量：**
- `NULLCLAW_API_KEY` — MiMo API Key
- `NULLCLAW_BASE_URL` — MiMo API Base URL（默认 `https://platform.xiaomimimo.com/v1`）
- `NULLCLAW_MODEL` — 模型名（默认 `mimo-v2.5-pro`）

**日志：** 总条目数、打分耗时、筛选后条目数、token 消耗估算。

---

### T5: generate_daily.py — 生成日报 JSON

**输入：** `data/scored/{date}.json`
**输出：** `data/daily/{date}.json` + `data/latest.json`

逻辑：
1. 读取打分后的条目
2. 按 category 分组
3. 按 score 降序排列
4. 生成日报 JSON：
```json
{
  "date": "2026-05-09",
  "generated_at": "ISO 8601",
  "total": 32,
  "sections": [
    {
      "category": "ai-models",
      "label": "模型发布/更新",
      "items": [...]
    },
    {
      "category": "ai-products",
      "label": "产品发布/更新",
      "items": [...]
    },
    {
      "category": "paper",
      "label": "论文研究",
      "items": [...]
    }
  ]
}
```
5. 同时更新 `data/latest.json`（最近 7 天合并）
6. category → label 映射：
   - `ai-models` → 模型发布/更新
   - `ai-products` → 产品发布/更新
   - `industry` → 行业动态
   - `paper` → 论文研究
   - `tip` → 技巧与观点

**日志：** 各分类条目数、总条目数。

---

### T6: fetch.yml — GitHub Actions Workflow

```yaml
name: Daily Fetch

on:
  schedule:
    - cron: '0 23 * * *'  # UTC 23:00 = 北京时间 07:00
  workflow_dispatch:

jobs:
  fetch:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Fetch sources
        run: python tools/fetch_sources.py

      - name: Score and filter
        env:
          NULLCLAW_API_KEY: ${{ secrets.NULLCLAW_API_KEY }}
          NULLCLAW_BASE_URL: ${{ secrets.NULLCLAW_BASE_URL }}
          NULLCLAW_MODEL: ${{ vars.NULLCLAW_MODEL }}
        run: python tools/score_and_filter.py

      - name: Generate daily
        run: python tools/generate_daily.py

      - name: Commit and push
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/
          git diff --cached --quiet || (git commit -m "daily: $(date +%Y-%m-%d)" && git push)
```

---

## 验收标准

P1 完成的标志：
1. 手动触发 workflow，能成功跑完
2. `data/daily/{date}.json` 生成，包含 20-50 条精选条目
3. 每条有中文标题、中文摘要、分数、分类
4. 日志清晰，能看到每一步的状态

---

## 给 Codex 的执行指令

> 请按照 `~/workspace/docs/0509/aipulse-tasks.md` 的 T1-T6 顺序实现 AIpulse P1。
> 仓库创建在 `/home/administrator/workspace/open-source/aipulse`。
> 设计文档在 `~/workspace/docs/0509/aipulse-design.md`。
> 每个 task 完成后 git commit。全部完成后 push 到 GitHub（org: ouraihub, repo: aipulse）。
> Python 代码要有结构化 JSON 日志（参考 msgflow 的 `tools/capabilities/logger.py` 风格）。
