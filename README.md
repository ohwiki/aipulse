# AIpulse

AIpulse 是一个面向中文 AI 从业者的每日资讯聚合项目。

当前仓库同时包含两部分：

- **Python pipeline**：抓取、打分、筛选、生成 `data/*.json`
- **Astro 前端**：读取本地 JSON，生成静态资讯页面

这不是两个无关项目，而是一条完整链路：

```text
Python tools -> data/*.json -> Astro pages
```

## 目录结构

```text
aipulse-dev/
├── data/          # 抓取结果、打分结果、日报 JSON
├── docs/          # 设计文档与任务文档
├── src/           # Astro 前端源码
├── tools/         # Python 数据流水线
├── .github/       # GitHub Actions
├── package.json   # 前端依赖与脚本
├── pnpm-lock.yaml
├── requirements.txt
└── README.md
```

## Python 数据流水线

当前 P1 能力：

- 从 RSS、arXiv、HuggingFace Daily Papers 拉取最近 24 小时条目
- 调用 MiMo 兼容接口打分并筛选高价值资讯
- 生成按分类组织的日报 JSON 和最近 7 天聚合数据
- 支持 GitHub Actions 定时执行

### 安装依赖

```bash
python -m pip install -r requirements.txt
```

### 运行顺序

1. 拉取原始数据

```bash
python tools/fetch_sources.py
```

2. 打分和筛选

真实 LLM 模式：

```bash
python tools/score_and_filter.py
```

如果还没配置 MiMo，先用演练模式跑通全链路：

```bash
python tools/score_and_filter.py --dry-run
```

3. 生成日报

```bash
python tools/generate_daily.py
```

完整演练顺序：

```bash
python tools/fetch_sources.py
python tools/score_and_filter.py --dry-run
python tools/generate_daily.py
```

### 环境变量

- `NULLCLAW_API_KEY`: MiMo API Key
- `NULLCLAW_BASE_URL`: API Base URL，默认 `https://platform.xiaomimimo.com/v1`
- `NULLCLAW_MODEL`: 模型名，默认 `mimo-v2.5-pro`

未设置 `NULLCLAW_API_KEY` 时：

- `python tools/score_and_filter.py` 会直接报错并提示你配置 Key
- `python tools/score_and_filter.py --dry-run` 会跳过真实 LLM 调用，使用启发式分数和本地占位摘要

### 输出目录

- `data/raw/YYYY-MM-DD.json`: 原始抓取结果
- `data/scored/YYYY-MM-DD.json`: 打分和中文化后的结果
- `data/daily/YYYY-MM-DD.json`: 当日日报
- `data/latest.json`: 最近 7 天聚合结果

## Skill

仓库已补充项目自己的 Skill：

- [skills/aipulse/SKILL.md](E:/workspace/mowen-dev/aipulse-dev/skills/aipulse/SKILL.md)

用途：

- 作为未来查询层 / Agent 集成的设计稿
- 固化 `AI 日报`、`最近 AI 圈`、`最近模型发布` 这类自然语言查询的目标输出形态
- 当前仓库仍是 **纯静态 Astro 站点**，这份 Skill 不代表运行时 API 已经对外保留

### 数据源维护

- `tools/sources.yaml` 支持 `enabled: false`，可临时禁用失效源
- 可选 `note` 字段会进入抓取日志，方便区分“源被禁用”和“抓取失败”

## Astro 前端

前端读取 `data/daily/*.json` 和 `data/latest.json`，生成静态页面。

当前已实现页面：

- `/` 今日精选
- `/archive` 日报归档
- `/archive/{date}` 单日日报
- `/category/{slug}` 分类浏览
- `/about` 关于页
- `/privacy` 隐私政策
- `/contact` 联系方式
- `/methodology` 方法说明
- `/sources-and-attribution` 来源与版权说明
- `/sitemap.xml` 站点地图
- `/robots.txt` 搜索引擎抓取说明

### 安装前端依赖

```bash
pnpm install
```

### 前端命令

开发模式：

```bash
pnpm dev
```

类型和 Astro 诊断：

```bash
pnpm check
```

生产构建：

```bash
pnpm build
```

## 设计文档

- `aipulse-design.md`
- `aipulse-frontend-design.md`
- `aipulse-ui-design.md`
- `aipulse-reusable-components.md`
- `aipulse-tasks.md`

## 当前状态

- Python pipeline 已能产出 `data/raw`、`data/scored`、`data/daily`、`data/latest`
- 前端已切到 `pnpm`
- `pnpm check` 通过
- `pnpm build` 通过
