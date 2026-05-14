# CLAUDE.md

AI 编码助手的行为准则。本项目主要由 AI 维护和开发，遵守以下规则减少返工。

## 项目概览

AIpulse 是一个 AI 资讯聚合服务。两部分：
- `tools/` — Python 数据流水线（抓取 → 打分 → 生成日报）
- `src/` — Astro 静态前端

数据流：`tools/ → data branch (JSON) → Astro build → static pages`

## 1. 动手前先理解

- 读 `docs/aipulse-design.md` 了解架构
- 读 `docs/code-quality-tasks.md` 了解已知问题和改进计划
- 读 `tools/sources.yaml` 了解数据源配置
- 不确定就问，不要猜

## 2. Python 规范

- 用项目的 logger（`from logger import get_logger`），不要用 print
- 新函数必须有类型注解
- 错误处理：不要静默吞异常，至少 log.warning
- 新增数据源：加到 `sources.yaml`，不要硬编码 URL
- item dict 的字段名参考 `common.py` 中的 `build_raw_item` 模式
- 运行 `uv run python tools/fetch_sources.py` 验证抓取
- 依赖变更后更新 `uv.lock`（`uv lock`）

## 3. 前端规范

- TypeScript 严格模式，不要用 `any`
- 新分类加到 `src/lib/types.ts` 的 `PulseCategory` 和 `src/lib/categories.ts`
- 组件放 `src/components/`，页面放 `src/pages/`
- 样式用 Astro scoped `<style>`，全局类在 `src/styles/global.css`
- 不要引入客户端 JS 框架（保持零 JS 输出）

## 4. 数据分支

- `main` 分支：代码和文档
- `data` 分支：生产数据（由 GitHub Actions 生成，不要手动改）
- 本地测试产生的 `data/raw/`、`data/scored/`、`data/daily/` 不要提交到 main

## 5. 改动原则

- 只改需要改的。不要顺手重构不相关的代码
- 匹配现有风格（snake_case for Python, camelCase for TS）
- 新功能先改 `sources.yaml` 或 `categories.ts`，再改逻辑代码
- 每个 commit 只做一件事，message 用 conventional commits（feat/fix/chore/docs）

## 6. 验证

- Python 改动后跑 `uv run python tools/fetch_sources.py` 确认不报错
- 前端改动后跑 `pnpm build` 确认构建通过
- 如果改了打分逻辑，用 `data/evals/scoring_samples.jsonl` 验证

## 7. 不要做的事

- 不要改 `.github/workflows/fetch.yml` 的 cron 时间（除非明确要求）
- 不要删除 `data/evals/` 下的评估数据
- 不要在 Python 代码里 `import *`
- 不要引入新的 Python 依赖而不更新 pyproject.toml + uv.lock
- 不要把 API key 或 secret 写进代码
