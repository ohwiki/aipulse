# AIpulse 部署文档

> 部署目标：
> - GitHub Actions 负责每日抓取、打分、生成 `data/*.json`
> - Netlify 负责构建 Astro 前端并发布静态站

## 1. 当前推荐架构

AIpulse 当前采用：

```text
GitHub Actions (cron)
-> uv run python tools/fetch_sources.py
-> uv run python tools/score_and_filter.py
-> uv run python tools/generate_daily.py
-> commit data/*.json 回仓库
-> Netlify 监听仓库变更
-> pnpm build
-> 发布 dist/
```

这是一个典型的：

- 离线产数
- 静态构建
- 自动部署

架构。

## 2. 适用前提

当前方案适合：

- AI 日报 / AI 资讯聚合产品
- 每天固定更新一次
- 不依赖运行时 Python API
- 前端直接读取仓库内 JSON 构建静态页面

## 3. 仓库内关键文件

- `.github/workflows/fetch.yml`
  - 每日定时抓取和生成数据
- `netlify.toml`
  - Netlify 构建配置
- `pyproject.toml` / `uv.lock`
  - Python 依赖和锁文件
- `package.json` / `pnpm-lock.yaml`
  - 前端依赖和锁文件

## 4. 本地上线前自检

在 push 前，建议本地至少执行：

```bash
uv sync
pnpm install
pnpm check
pnpm build
```

如果要验证数据链路：

```bash
uv run python tools/fetch_sources.py
uv run python tools/score_and_filter.py --dry-run
uv run python tools/generate_daily.py
```

## 5. GitHub Actions 配置

## 5.1 工作流职责

当前 workflow 已经负责：

1. 安装 Python 环境（`uv`）
2. 抓取数据
3. 打分与筛选
4. 生成日报 JSON
5. 安装前端依赖
6. 构建 Astro 前端
7. 构建成功后才 commit `data/`

也就是说：

- 如果 Python 成功但前端构建失败，不会提交脏数据
- 只有整条链路都通过，才会更新仓库内容

此外，当前 workflow 已在 YAML 中显式声明：

```yaml
permissions:
  contents: write
```

这一步是为了允许 `GITHUB_TOKEN` 在 workflow 中执行 `git push`。

## 5.2 GitHub Secrets / Variables

进入：

- `GitHub Repo -> Settings -> Secrets and variables -> Actions`

需要配置：

### Secrets

- `PRODUCTHUNT_DEVELOPER_TOKEN`

如果没有 developer token，则改用：

- `PRODUCTHUNT_CLIENT_ID`
- `PRODUCTHUNT_CLIENT_SECRET`

另外还需要：

- `NULLCLAW_API_KEY`
- `NULLCLAW_BASE_URL`

### Variables

- `NULLCLAW_MODEL`

## 5.3 组织 / 仓库权限设置

如果仓库在 GitHub Organization 下，除了 workflow YAML 里的 `permissions:`，还必须检查 GitHub 后台的默认 token 权限。

### 仓库级页面

路径：

- `Repository -> Settings -> Actions -> General`

查看：

- `Workflow permissions`

如果这里是灰色不可编辑，说明它被组织级设置托管，不能在仓库里改。

### 组织级页面

路径：

- `Organization -> Settings -> Actions -> General`

找到：

- `Workflow permissions`

选择：

- `Read and write permissions`

说明：

- 这一步决定 `GITHUB_TOKEN` 默认是否有写仓库权限
- 如果这里只允许只读，即使 workflow 里写了 `permissions: contents: write`，`git push` 仍可能 403

### 不要混淆的设置

同一页面里还会有：

- `Allow all actions and reusable workflows`
- `Allow <org> actions and reusable workflows`

这一块只控制：

- 允许使用哪些 Actions

它**不等于** `GITHUB_TOKEN` 的读写权限设置，不能替代 `Workflow permissions`

## 5.3 定时执行时间

当前 cron：

```yaml
30 0 * * *
```

对应：

- `00:30 UTC`
- `08:30 Asia/Shanghai`

也就是每天北京时间早上 8:30 自动跑。

## 6. Netlify 配置

## 6.1 当前构建配置

仓库内已有：

- `netlify.toml`

内容等价于：

- Build command: `pnpm build`
- Publish directory: `dist`
- Node version: `22`
- pnpm version: `10`

## 6.2 接入步骤

1. 打开 Netlify
2. 点击 `Add new site`
3. 选择 `Import an existing project`
4. 连接 GitHub
5. 选择 `aipulse` 仓库
6. Netlify 会读取 `netlify.toml`
7. 确认构建命令和发布目录无误
8. 点击部署

## 6.3 部署触发方式

Netlify 会监听仓库变更。

因此：

- GitHub Actions 每天提交新的 `data/*.json`
- 仓库主分支有新 commit
- Netlify 自动重新构建并发布

## 7. 首次上线顺序

建议按这个顺序执行：

1. 把当前代码 push 到 GitHub 主分支
2. 在 GitHub 配好 Actions 的 secrets / variables
3. 在 GitHub 组织或仓库的 `Actions -> General` 中确认：
   - `Workflow permissions = Read and write permissions`
4. 在 Netlify 连接仓库并完成首次部署
5. 回到 GitHub Actions，手动运行一次 `Daily Fetch`
6. 等 workflow 完成
7. 检查仓库是否生成新的 `data/daily/*.json` 和 `data/latest.json`
8. 等 Netlify 自动重新部署
9. 打开线上站点验证页面结果

## 8. 验收清单

首次部署完成后，至少检查：

### 数据链路

- workflow 能手动触发成功
- `data/raw/*.json` 生成
- `data/scored/*.json` 生成
- `data/daily/*.json` 生成
- `data/latest.json` 更新

### 前端构建

- Netlify build 成功
- 首页可打开
- 归档页可打开
- 分类页可打开
- 单日页可打开

### 自动更新

- workflow 提交数据后，Netlify 能自动重新部署

### 权限链路

- workflow 中 `git push` 不再报 403
- `github-actions[bot]` 可以把 `data/daily` 和 `data/latest.json` 推回仓库

## 9. 当前已处理的上线前问题

当前仓库已经处理：

- Python 项目由 `uv` 管理
- 工作流中已使用 `uv sync --locked`
- demo 产物已清理
- 前端 demo 标记已移除
- workflow 已补上 `pnpm build` 验证
- workflow 已显式声明 `permissions: contents: write`
- `netlify.toml` 已提供

## 10. 当前仍建议后续优化的内容

这些不阻止上线，但建议后续尽快做：

1. `tools/generate_daily.py` 的 `latest.json` 聚合去重
2. 新增“全部动态”页
3. 分类页继续向高密度资讯流优化
4. 首页进一步弱化展示页感
5. 更充分利用 `score_details.reason`

## 11. 回滚策略

如果某天 workflow 产出的数据有问题：

1. 在 GitHub 上回退对应的 `data/` commit
2. Netlify 会跟着仓库自动重建

因为这是静态站：

- 没有运行时数据库迁移
- 没有后端在线状态依赖
- 回滚成本较低

## 12. 一句话总结

AIpulse 当前最适合的上线方式是：

- GitHub Actions 产数
- commit JSON 回仓库
- Netlify 自动构建和发布前端

先把这条链路跑通，再继续做产品体验优化。
