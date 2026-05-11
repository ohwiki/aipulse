# AIpulse 数据分支方案任务拆分

> 目标：让后续大模型可以直接按任务顺序落地“`main` 代码分支 + `data` 数据分支 + Netlify 构建期同步数据”。

## T1: 固化分支职责与约束文档

输出：

- 更新 `README.md`
- 更新相关部署文档

要求：

- 明确 `main` 只放代码
- 明确 `data` 只放正式构建数据
- 明确本地验证不代表正式线上数据
- 明确 GitHub Actions 是唯一正式数据产出路径

验收：

- 文档中不再出现“workflow 把 data 提交回主干”的表述

## T2: 固化 `data` 分支的数据保留范围

输出：

- 文档和实现统一采用同一口径

本阶段固定为：

- 保留 `data/daily/*.json`
- 保留 `data/latest.json`
- 不保留 `data/raw/*.json`
- 不保留 `data/scored/*.json`

验收：

- workflow、同步脚本、文档都只围绕上述范围实现

## T3: 重构 GitHub Actions 输出策略

目标：

- 让 `.github/workflows/fetch.yml` 不再把数据 commit 到 `main`

要求：

1. checkout `main`
2. 运行抓取 / 打分 / 生成流程
3. 在独立临时目录 checkout `data` 分支
4. 将正式数据同步到该临时目录
5. commit 并 push 到 `data`

注意：

- 不要在主工作区直接切到 `data`
- 不要把 `main` 工作区作为最终 push 工作区

验收：

- workflow 成功后，新增数据 commit 出现在 `data` 分支
- `main` 不出现新的 daily data commit

## T4: 检查并固化 `data` 分支写入权限

目标：

- 避免 workflow 改完后卡在 push 权限问题

要求：

- 检查 `permissions: contents: write`
- 检查 `GITHUB_TOKEN` 是否允许写 `data` 分支
- 检查 `data` 分支保护规则是否阻止 bot 提交
- 把结论补进部署文档或专项说明

验收：

- 权限前提清楚，workflow 可以稳定 push `data`

## T5: 人工初始化 `data` 分支

目标：

- 在正式切换前完成一次明确的分支初始化

要求：

- 由维护者手动创建 `data` 分支
- 写入最小可用 `data/` 目录结构
- 不在每日 workflow 中发明自动建分支逻辑

验收：

- `data` 分支存在，后续 workflow 可直接使用

## T6: 新增构建前数据同步脚本

目标：

- 在 Netlify 或本地构建前，把 `origin/data` 的正式数据同步到当前工作区

建议输出：

- 一个 repo 内脚本，例如 `tools/sync_data_branch.*`

职责：

- 拉取 `origin/data`
- 导出 `data/` 目录
- 覆盖当前工作区的前端构建数据目录
- 缺失或失败时给出明确错误

验收：

- 本地可单独执行该脚本
- 执行后 `data/` 目录可用于 `pnpm build`

## T7: 调整 Netlify build command

目标：

- Netlify 构建前自动同步 `data` 分支，再执行前端构建

要求：

- `netlify.toml` 或站点 build command 更新为两阶段
- 先 sync data
- 再 `pnpm build`

验收：

- Netlify 构建日志能看到同步数据步骤
- 构建产物使用的是 `data` 分支最新数据

## T8: 接入 Netlify build hook 触发链路

目标：

- 让 `data` 分支更新后，线上站点一定触发新的构建

前置条件：

- `T3` 已完成，workflow 已稳定向 `data` 分支写正式数据
- `T6-T7` 已完成，Netlify 已具备构建前同步 `data` 分支数据的能力

要求：

- 在 GitHub Actions 成功 push `data` 分支后触发 Netlify build hook
- 在部署文档中记录所需 secret/config
- 明确失败日志和排查方式

验收：

- `data` 分支新增 commit 后，Netlify 有新的 build 记录

## T9: 保持 Astro 数据读取接口不变

目标：

- 不让这次分支拆分扩散成前端大改

要求：

- `src/lib/content.ts` 等读取逻辑继续读取工作区里的 `data/*.json`
- 不改为运行时 fetch
- 不改为外部 API 依赖

验收：

- 页面逻辑只依赖本地同步后的 `data/` 目录

## T10: 更新部署文档

输出：

- 更新 `docs/aipulse-deployment-guide.md`

要求：

- 写清 `main` / `data` 分支职责
- 写清 GitHub Actions 如何更新 `data`
- 写清 Netlify 如何在 build 前同步 `data`
- 写清失败排查点

验收：

- 新人只看部署文档也能理解整套链路

## T11: 验证主分支不再接收 daily data commit

目标：

- 确认设计目标真正生效

要求：

- 运行一次完整工作流后
- 检查 `main` 最近提交不包含 daily data commit
- 检查 `data` 分支包含当次数据提交

验收：

- 分支职责符合预期

## T12: 验证正式线上更新链路

目标：

- 确认“`data` 分支更新 -> Netlify 重建 -> 站点看到新数据”整条链路闭环

要求：

- 运行一次完整工作流
- 检查 `data` 分支新增提交
- 检查 Netlify 被 build hook 触发
- 检查 build 日志里执行了同步 `data` 分支步骤
- 检查线上页面可见新数据

验收：

- 正式数据更新链路完整可用

## T13: 补一个简短 handoff 文档

输出：

- 更新 `docs/resume-context.md` 或新增专项 handoff

要求：

- 记录当前采用的是“代码分支 / 数据分支分离方案”
- 记录 Netlify 构建依赖 `data` 分支同步
- 记录哪些工作已做完，哪些还未做

验收：

- 后续大模型接手时不会又把实现漂回“主干写数据”
