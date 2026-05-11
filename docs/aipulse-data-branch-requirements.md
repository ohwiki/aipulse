# AIpulse 数据分支方案需求文档

> 范围：把当前“主分支同时承载代码与每日数据”的实现，调整为“`main` 只维护代码，`data` 分支只维护构建数据”。
> 目标：保证代码历史干净，数据更新仍由 GitHub Actions 自动产出，并且 Netlify 能在构建时拉取最新数据。

## 1. 背景

当前仓库的实际行为是：

- GitHub Actions 每日运行抓取、打分、生成流程
- workflow 直接把 `data/daily/*.json` 和 `data/latest.json` commit 回当前分支
- Netlify 从主分支读取仓库内容并执行 Astro 构建

这个实现的问题是：

- `main` 分支同时承载代码提交与每日数据提交
- 每日数据 commit 会污染代码历史
- review、回滚、变更追踪会混入大量与代码无关的 daily commit
- “本地只维护代码，正式数据只由工作流生成”的边界不够清晰

## 2. 目标

新的目标架构必须满足：

1. `main` 分支只保存代码、文档、前端、workflow 和工具脚本
2. `data` 分支只保存前端构建所需的正式数据文件
3. 每日数据只能由 GitHub Actions 正式工作流产出
4. 本地开发可以生成数据用于验证，但不得将本地生成数据作为正式数据提交
5. Netlify 仍然可以基于 `main` 构建站点，但构建前需要拿到 `data` 分支内容
6. `data` 分支更新后必须能触发新的 Netlify 构建

## 3. 非目标

这次调整不包含：

- 改成外部数据库
- 改成运行时 API 动态查询
- 改成另一个独立数据仓库
- 重做前端页面结构

## 4. 角色与职责

### 4.1 `main` 分支职责

- 保存 Astro 前端代码
- 保存 Python pipeline 代码
- 保存 GitHub Actions workflow
- 保存 Netlify 构建配置
- 保存文档与说明
- 可保留空的 `data/` 目录占位或本地开发样例，但不承载正式生产数据

### 4.2 `data` 分支职责

- 保存 `data/daily/*.json`
- 保存 `data/latest.json`

第一阶段明确不保存：

- `data/raw/*.json`
- `data/scored/*.json`

### 4.3 GitHub Actions 职责

- 每日抓取、打分、筛选、生成数据
- 将正式产出写入 `data` 分支
- 不把生成数据回写到 `main`

### 4.4 Netlify 职责

- 以 `main` 为代码来源触发构建
- 在构建前显式拉取 `data` 分支数据
- 将数据文件放入当前工作目录后再执行 `pnpm build`
- 在 `data` 分支数据更新后，通过显式触发重新执行构建

## 5. 功能需求

### 5.1 分支分离

必须支持：

- `main` 不再接收 daily data commit
- `data` 分支可独立持续追加每日数据提交
- 前端代码更新与数据更新互不污染提交历史

### 5.2 工作流写入策略

必须支持：

- workflow 在 `data` 分支完成 `git add / commit / push`
- workflow 失败时不影响 `main` 分支代码状态
- workflow 的分支推送权限有明确检查项
- `data` 分支首次初始化方式明确且不依赖每日 workflow 自动推断

### 5.3 Netlify 构建期取数

必须支持：

- Netlify 构建时拉取 `data` 分支
- 将 `data` 分支中的 `data/` 目录同步到当前构建工作区
- Astro 构建仍然从本地 `data/*.json` 读取，不改页面数据读取接口
- `data` 分支数据更新后能触发新的 Netlify 构建

### 5.4 本地开发边界

必须支持：

- 本地可运行 pipeline 做验证
- 默认不把本地生成数据作为正式数据提交到 `main` 或 `data`
- 文档要明确“正式数据以工作流结果为准”

## 6. 约束

- 不增加新的运行时后端依赖
- 不改前端读取数据的主路径接口，仍保持 `data/daily/*.json` 与 `data/latest.json`
- 不要求开发者在本地手动维护 `data` 分支
- 配置应尽量收敛在 workflow、build script 和 Netlify 配置中

## 7. 验收标准

满足以下条件可视为完成：

1. `main` 上不再出现新的 daily data commit
2. `data` 分支持续新增正式数据提交
3. Netlify 从 `main` 构建时能拿到 `data` 分支最新数据
4. `data` 分支更新后能够触发新的 Netlify 构建
5. 首页、归档页、分类页、单日页构建结果不因分支拆分而失效
6. README / 部署文档清楚说明代码分支与数据分支职责

## 8. 风险

主要风险：

- Netlify 构建环境未正确拉到 `data` 分支
- workflow 推送 `data` 分支时权限不足
- `data` 分支首次初始化策略不清晰
- `data` 分支更新后没有触发新的 Netlify build
- 文档未更新导致后续模型又把数据回写到 `main`

因此需要在设计中明确：

- workflow 如何切换目标分支
- Netlify 如何在 build 前 fetch/sync 数据
- `data` 分支更新后如何触发 Netlify 构建
- `data` 分支权限与初始化方式如何固化
- `.gitignore`、README、部署文档如何更新
