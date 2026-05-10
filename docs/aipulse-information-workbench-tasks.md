# AIpulse 信息工作台实现任务

> 对应文档：
> - `docs/aipulse-information-workbench-requirements.md`
> - `docs/aipulse-information-workbench-design.md`

目标：让后续大模型或工程师可以按任务块直接执行。

## T1. 首页重构为“今日总览”

目标：

- 弱化展示页感
- 提高首屏扫读效率

任务：

- 收缩头条区为 `1 主 + 3 副`
- 保持顶部概览信息稳定
- 分类导航前置
- 首页分类区与头条区去重
- 当剩余内容过少时，展示稀疏态提示，不强行拉长页面

涉及文件：

- `src/pages/index.astro`
- `src/components/DailyHero.astro`
- `src/components/SectionBlock.astro`
- `src/components/NewsCard.astro`

验收：

- 首页首屏更紧凑
- 不再出现同一条内容在头条区和分类区重复

## T2. 新增“全部动态”页

目标：

- 提供一个高密度、连续的全量资讯流页面

任务：

- 新增页面 `src/pages/latest.astro` 或 `src/pages/all.astro`
- 从 `latest.json` 读取最近聚合内容
- 提供分类筛选 UI
- 提供来源筛选 UI
- 提供排序切换：
  - 最新优先
  - `rankingScore` 优先

涉及文件：

- `src/pages/latest.astro`
- `src/lib/content.ts`
- `src/components/HeaderBar.astro`
- `src/components/NewsCard.astro`

验收：

- 用户可从主导航直接进入全部动态页
- 页面适合连续刷读

## T3. 分类页升级为专题流

目标：

- 让分类页成为真正可用的高频页面

任务：

- 按来源对分类内容分组
- 增加来源跳转锚点
- 加强每条卡片的理由和信号表达
- 保持真实聚合时间窗展示

涉及文件：

- `src/pages/category/[slug].astro`
- `src/components/NewsCard.astro`
- `src/lib/content.ts`

验收：

- 分类页不再只是单列长列表
- 用户可以快速定位某个来源的内容

## T4. 卡片改造成资讯卡

目标：

- 从博客卡片收紧为高密度资讯卡

任务：

- 明确固定层级：
  - 分类
  - 分数
  - 信号
  - 标题
  - 来源 + 时间
  - 摘要
  - 理由
- 对 hero / full / compact 三种变体做一致规则
- 减少无效留白

涉及文件：

- `src/components/NewsCard.astro`

验收：

- 列表页更适合扫读
- 原因和排序信号更清楚

## T5. 最新聚合去重

目标：

- 避免 `latest.json` 出现跨天重复条目

任务：

- 更新 `tools/generate_daily.py` 的 `collect_latest()`
- 对聚合项按 `id` 或 `url` 去重
- 去重冲突时保留：
  - `rankingScore` 更高的项
  - 若分数相同则保留时间更新的一项

涉及文件：

- `tools/generate_daily.py`

验收：

- 分类页和全部动态页不再被重复条目污染

## T6. 数据链路稳定性加固

目标：

- 提升无人值守可用性

任务：

- 确认工作流中只使用生产 `daily` 数据
- 确认仓库内不再包含 demo 产物
- 在 workflow 中加入前端构建检查：
  - `pnpm install`
  - `pnpm build`
- 若构建失败，不提交数据

涉及文件：

- `.github/workflows/fetch.yml`
- `README.md`

验收：

- 工作流既能产数，也能验证前端可构建

## T7. 归档页和单日页导航优化

目标：

- 提高回看效率

任务：

- 归档页增加最近几期快捷跳转
- 单日页增加版块跳转
- 保持前后日期切换可用

涉及文件：

- `src/pages/archive/index.astro`
- `src/pages/archive/[date].astro`
- `src/components/ArchiveDayCard.astro`

验收：

- 从归档到单日页的跳转成本下降

## T8. 稀疏态与空态设计优化

目标：

- 避免“没有很多数据时页面显得坏掉”

任务：

- 首页增加稀疏态提示
- 分类页空态增加更合适的返回路径
- 归档页和单日页空态保持页内语义一致

涉及文件：

- `src/pages/index.astro`
- `src/components/EmptyState.astro`
- `src/pages/category/[slug].astro`
- `src/pages/archive/index.astro`
- `src/pages/archive/[date].astro`

验收：

- 稀疏日页面依然自然
- 空态不再只会“返回首页”

## 推荐执行顺序

1. `T5` 最新聚合去重
2. `T6` 数据链路稳定性加固
3. `T2` 新增全部动态页
4. `T3` 分类页升级为专题流
5. `T4` 卡片改造成资讯卡
6. `T1` 首页重构为今日总览
7. `T7` 归档和单日页导航优化
8. `T8` 稀疏态与空态优化

## 每个任务统一验收动作

完成每个任务后至少执行：

```bash
pnpm check
pnpm build
```

如涉及 Python 产物结构变化，再执行：

```bash
uv run python tools/generate_daily.py
```
