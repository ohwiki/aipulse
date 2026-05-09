# AIpulse 前端渲染设计

> 面向 `aipulse-dev` P2 的页面层设计。
> 目标：在不改变 P1 数据流水线的前提下，构建一个适合 AI 资讯日报的静态前端。

## 1. 设计目标

AIpulse 前端需要解决的不是“文章发布”，而是“每日资讯浏览”。

因此页面层目标明确为：

- 让用户打开首页就能看到当天最重要的 AI 资讯
- 让用户可以按日期回看，保持“日报”产品心智
- 让用户可以按分类快速扫读近期动态
- 让静态构建足够简单，避免运行时耦合 API

## 2. 架构原则

### 2.1 数据单向流动

前端只消费两类数据：

- `data/daily/{date}.json`
- `data/latest.json`

不直接参与抓取、打分、摘要生成。

### 2.2 构建期优先

页面在 Astro 构建期完成数据读取与静态渲染。

优先级如下：

1. 构建期读取本地 JSON
2. 生成静态 HTML
3. 部署后直接分发

只有在后续确实需要实时筛选或更复杂检索时，再引入 Worker API 参与前端交互。

### 2.3 内容优先于装饰

页面风格服务于阅读效率，不做 marketing hero，不做花哨插画，不用博客模板来包资讯流。

## 3. 信息架构

```text
/
|-- 今日头条
|-- 分类精选
|-- 历史日报入口

/archive
|-- 按日期倒序的日报摘要列表

/archive/{date}
|-- 指定日期完整日报

/category/{slug}
|-- 最近 7 天该分类条目流

/about
|-- 产品说明 / 数据来源 / 更新频率
```

## 4. 页面职责

### 4.1 首页 `/`

首页是 AIpulse 最重要的页面，承担两个任务：

- 让第一次进入的用户立即理解“今天 AI 圈发生了什么”
- 让回访用户最快速完成扫读

建议结构：

1. 顶部信息条
   - 产品名
   - 今日日期
   - 最后生成时间
   - 归档入口
2. 今日头条
   - 3 至 5 条最高分资讯
3. 分类精选
   - 每个分类一个 section
4. 页面底部
   - 数据来源说明
   - 更新节奏说明
   - API / about 入口

### 4.2 归档页 `/archive`

这是“查哪天发生了什么”的入口页。

单日卡片建议包括：

- 日期
- 总条数
- 分类数量
- 当日 Top 2 标题
- 跳转到详情页的入口

### 4.3 单日日报页 `/archive/{date}`

使用和首页相同的日报呈现方式，但不再强调头条焦点，而是完整展示当日结构化内容。

页面内建议提供：

- 返回归档页
- 上一天 / 下一天
- 当日条数统计

### 4.4 分类页 `/category/{slug}`

分类页不是 taxonomy 文档页，而是该分类最近资讯流。

每条资讯显示最关键的 6 个字段：

- 标题
- 来源
- 发布时间
- 分数
- 摘要
- 原文链接

## 5. 数据适配设计

## 5.1 统一类型

建议前端定义统一数据类型，而不是在页面里直接操作原始 JSON。

```ts
export type PulseCategory =
  | "ai-models"
  | "ai-products"
  | "industry"
  | "paper"
  | "tip";

export interface PulseItem {
  id: string;
  title: string;
  titleEn?: string;
  url: string;
  source: string;
  category: PulseCategory;
  score: number;
  summary: string;
  publishedAt: string;
}

export interface DailySection {
  category: PulseCategory;
  label: string;
  items: PulseItem[];
}

export interface DailyDigest {
  date: string;
  generatedAt: string;
  total: number;
  sections: DailySection[];
}
```

### 5.2 数据适配层职责

建议 `src/lib/content.ts` 提供以下方法：

- `getLatestDailyDigest()`
- `getDailyDigest(date: string)`
- `listDailyDigests()`
- `listCategoryItems(category: string, days = 7)`
- `getTopItems(digest, take = 5)`

这样页面组件不关心 JSON 文件格式细节，只消费适配后的结构。

### 5.3 分类元数据

建议单独维护 `src/lib/categories.ts`：

```ts
export const CATEGORY_META = {
  "ai-models": { label: "模型发布/更新", description: "模型能力、版本与接口更新" },
  "ai-products": { label: "产品发布/更新", description: "AI 产品、功能和平台发布" },
  industry: { label: "行业动态", description: "公司、融资、合作与行业趋势" },
  paper: { label: "论文研究", description: "值得关注的论文与研究成果" },
  tip: { label: "技巧与观点", description: "实践经验、方法论与观察" },
};
```

## 6. 组件设计

### 6.1 `BaseLayout`

职责：

- 页面 `title` / `description`
- canonical / open graph 基础元信息
- 页面宽度、留白、页脚

### 6.2 `HeaderBar`

职责：

- 品牌名
- 当前日期或页面标题
- 主导航：今日 / 归档 / 分类 / 关于

### 6.3 `DailyHero`

职责：

- 展示首页 Top 3-5 条
- 第一条重点强化，其余保持紧凑

### 6.4 `SectionBlock`

职责：

- 一个分类标题
- 分类描述
- 该分类条目列表

### 6.5 `NewsCard`

职责：

- 承载单条资讯所有核心字段
- 适配首页、单日页、分类页三种上下文

建议支持 `compact` 和 `full` 两种模式：

- `compact`: 首页次要列表、归档摘要引用
- `full`: 单日页、分类页主列表

### 6.6 `ArchiveDayCard`

职责：

- 展示某天的日报摘要
- 让用户一眼判断那天值不值得点进去

## 7. 响应式布局建议

### 移动端

- 单列布局
- 标题与摘要优先完整展示
- 来源、分数、时间做紧凑行内信息

### 平板

- 首页头条区可做 1 主 2 次布局
- 分类区保持单列 section，内部列表稍加留白

### 桌面

- 页面最大宽度建议控制在 1100-1200px
- 首页头条区可双栏
- 分类区继续纵向阅读，不做复杂 masonry

## 8. 视觉规范

建议采用下面的视觉基调：

- 背景：近白
- 正文：近黑
- 次级信息：中灰
- 强调色：品牌紫
- 分割线：浅灰

风格上要避免：

- 博客封面图思路
- 大面积营销区
- 过多卡片嵌套
- 装饰性渐变背景

## 9. SEO 与可分享性

尽管是资讯聚合站，仍建议保持基础 SEO：

- 首页 title: `AIpulse | 今日 AI 资讯精选`
- 单日页 title: `AIpulse | 2026-05-09 AI 日报`
- 分类页 title: `AIpulse | 模型发布/更新`
- 每页提供简短 description
- RSS 可以作为后续增强项，不作为 P2 阻塞项

## 10. 与 Worker API 的关系

P2 静态站应当可以完全脱离 Worker API 独立工作。

关系划分如下：

- `data/*.json`: 页面构建主数据源
- `Worker API`: 对外查询接口、技能调用入口、后续动态能力扩展

这意味着：

- GitHub Pages 可直接承载静态站
- Worker 可以独立部署在 `pulse.ouraihub.com/api/*`
- 两者生命周期分离，不互相阻塞

## 11. 实施建议

P2 建议拆成以下小任务：

1. 初始化 Astro 项目与目录结构
2. 实现 `src/lib` 数据适配层
3. 实现基础布局和导航
4. 实现首页
5. 实现归档页和单日页
6. 实现分类页
7. 补充 about 页与基础 SEO
8. 本地构建和移动端验收

## 12. 验收标准

- 构建时能正确读取本地 `data/*.json`
- 首页能突出今日重点内容
- 归档与分类路径可静态生成
- 页面无需运行时请求即可完整展示内容
- 移动端阅读体验良好
