# AIpulse i18n 技术实施任务清单

更新时间：2026-05-09

## 目的

本文档用于把 `AIpulse` 的双语支持方案落到具体实施步骤，方便后续模型或开发者直接按任务顺序推进，而不是每次重新设计国际化方案。

本文档默认以上游文档为准：

- `docs/aipulse-bilingual-support-design.md`

## 当前目标

当前阶段只做：

- 双语能力层
- 文案字典层
- 内容展示回退策略
- 页面 metadata 双语能力

当前阶段**不做**：

- `/en/` 独立路由体系
- `hreflang`
- 双语 sitemap
- 完整英文 SEO 站点

## 实施原则

1. 优先抽象能力，不先做表面按钮
2. 优先改共享层，不先逐页硬编码
3. 所有 locale 判断尽量收敛到 `lib/i18n` 层
4. 组件只消费已经决定好的文案和内容字段
5. 不把中英文逻辑散落到每个页面里

## 任务拆分

## T1. 建立 locale 基础类型与入口

### 目标

定义统一语言类型和最小 locale 获取逻辑。

### 建议新增

- `src/lib/i18n/types.ts`
- `src/lib/i18n/get-locale.ts`

### 最低要求

```ts
export type Locale = "zh-CN" | "en";
```

### 当前阶段建议

先支持以下任一方式即可：

1. query 参数：`?lang=en`
2. cookie
3. 本地默认常量

不要求一步到位做复杂状态管理。

## T2. 建立文案字典

### 目标

把通用 UI 文案从页面中抽离。

### 建议新增

- `src/lib/i18n/messages.ts`

### 第一批必须字典化的内容

1. Header 导航
2. Footer 文案
3. 通用按钮文案
4. TrustLinks 文案
5. PageIntro 中的固定说明文案

### 结果要求

后续组件不再直接写：

- `今日`
- `归档`
- `关于`
- `查看原文`
- `继续了解`

而应改为通过 locale 获取。

## T3. 建立内容展示策略函数

### 目标

把中英文内容字段回退逻辑集中起来。

### 建议新增

- `src/lib/i18n/content-display.ts`

### 建议函数

```ts
getDisplayTitle(item, locale)
getDisplaySecondaryTitle(item, locale)
getDisplaySummary(item, locale)
```

### 推荐规则

#### 中文模式

- 主标题：中文标题
- 副标题：英文原题（可选）
- 摘要：中文摘要

#### 英文模式

- 主标题：英文原题优先
- 副标题：中文标题可选
- 摘要：
  - 有英文摘要则用英文摘要
  - 没有则按策略回退或隐藏

### 注意

不要把这些判断直接散落在 `NewsCard` 组件里。

## T4. 改造 `BaseLayout` 的 locale 能力

### 目标

让页面元信息能跟着语言切换。

### 需要改的点

- `<html lang="...">`
- `title`
- `description`
- `og:locale`
- JSON-LD 中 `inLanguage`

### 建议方式

为 `BaseLayout` 增加 locale 入参，或传入已解析好的 metadata。

## T5. 抽 Header / Footer / TrustLinks 双语

### 目标

先改共享组件，覆盖最大页面范围。

### 需要改造的组件

- `src/components/HeaderBar.astro`
- `src/components/SiteFooter.astro`
- `src/components/TrustLinks.astro`

### 完成标准

这些组件不再含有中文硬编码 UI 文字。

## T6. 改 `NewsCard` 的双语展示逻辑

### 目标

让核心内容卡支持双语模式。

### 需要解决的问题

1. 英文模式下标题如何显示
2. 英文模式下摘要如何回退
3. 英文副标题是否显示
4. 卡片内来源、时间、按钮文案如何切换

### 完成标准

`NewsCard` 能在不复制组件的情况下支持中英文展示。

## T7. 改首页、分类页、单日页

### 目标

让核心内容页先具备双语运行能力。

### 改造优先级

1. 首页 `/`
2. 分类页 `/category/{slug}`
3. 单日页 `/archive/{date}`

### 原因

这三类页面最能体现双语产品体验，也最能暴露数据字段回退问题。

## T8. 改 About 与信任页

### 目标

让说明页不再出现“英文 UI + 中文正文”的割裂问题。

### 需要改造的页面

- `/about`
- `/privacy`
- `/contact`
- `/methodology`
- `/sources-and-attribution`

### 注意

这些页面不适合临时机翻后直接上线，文案要保持可信和自然。

## T9. 建立页面 metadata 字典

### 目标

避免每个页面自己手写中英文 SEO 文案。

### 建议新增

- `src/lib/i18n/page-meta.ts`

### 建议能力

```ts
getPageMeta({
  locale,
  pageType,
  data
})
```

例如支持：

- 首页
- 分类页
- 单日页
- 说明页

## T10. 增加语言切换 UI

### 目标

在基础能力稳定后，再增加用户可见的语言入口。

### 建议位置

- Header 右侧

### 当前阶段建议

只在以下条件满足后再做：

1. 文案字典已建立
2. 共享组件已双语化
3. 核心内容页已能正确显示

否则语言按钮只会暴露未完成状态。

## 建议实施顺序

### 第一阶段

1. T1 locale 基础
2. T2 文案字典
3. T3 内容展示策略
4. T4 BaseLayout locale 能力

### 第二阶段

1. T5 Header / Footer / TrustLinks
2. T6 NewsCard
3. T7 首页 / 分类页 / 单日页

### 第三阶段

1. T8 About 与信任页
2. T9 页面 metadata 字典
3. T10 语言切换 UI

## 验收标准

达到以下条件，才算当前阶段双语支持完成：

1. 已有统一 `Locale` 类型
2. 已有共享文案字典
3. 已有内容字段回退策略函数
4. Header / Footer / TrustLinks 已可双语
5. NewsCard 已可双语
6. 首页 / 分类页 / 单日页已可双语运行
7. About 与信任页已可双语运行
8. 页面 metadata 可随 locale 变化

## 当前阶段不要做的事

- 不要直接把页面复制成 `/en/`
- 不要先做语言切换按钮
- 不要让每个页面自己决定中英文显示逻辑
- 不要在组件里到处写 `locale === ...`
- 不要在没有英文摘要供应的前提下假装已经有完整英文内容体系

## 总结

`AIpulse` 的双语支持应当先成为一套稳定的底层能力，再逐步扩展到页面和路由，而不是从视觉按钮开始倒推工程结构。
