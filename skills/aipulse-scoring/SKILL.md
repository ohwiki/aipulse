---
name: aipulse-scoring
description: 用于 AIpulse 评分体系迭代的本地 Skill。适用于调整 `tools/score_and_filter.py` 的 rubric、打分 prompt、Product Hunt 权重和边界样本评估。不要把它当成 GitHub Actions 的运行时；工作流仍应直接运行 Python 代码。
---

# AIpulse Scoring

这个 Skill 只服务于 **评分体系迭代**，不直接参与生产工作流。

## 什么时候用

- 用户要优化 `score_and_filter.py` 的 prompt
- 用户要调整 Product Hunt 权重
- 用户要分析为什么某批条目被打高/打低
- 用户要建立或扩充评分样本集

不要在回答“今天有什么 AI 新闻”时使用本 Skill。

## 评分方法

采用三层结构：

1. `gate`
   - `is_ai_relevant`
   - `is_real_launch_or_update`
2. `rubric`
   - `novelty` 0-3
   - `practitioner_value` 0-3
   - `signal_over_promo` 0-2
   - `distribution_signal` 0-2
   - `confidence` 0-1
3. `rerank`
   - Product Hunt `votes_count`
   - `featured`
   - `topics`

入选和排序分离：

- 入选先看 `gate` 和 `final_score`
- 排序再看 `rank_score`

## 调整顺序

1. 先看 `data/evals/scoring_samples.jsonl`
2. 抽查 `data/scored/*.json` 里的 `score_details`
3. 只在下面三类地方改动：
   - rubric prompt
   - filter rule
   - Product Hunt rerank rule
4. 每次改动后至少重跑：

```bash
python tools/score_and_filter.py --dry-run
python tools/generate_daily.py
```

如果用户已经配好真实模型，再跑：

```bash
python tools/score_and_filter.py
python tools/generate_daily.py
```

## 边界判断

- 高票 Product Hunt AI 新品不应因为“像产品介绍”被机械打成低分
- 普通宣传稿即使带 AI 字样，也不应仅靠关键词过关
- 真正的模型/论文/开发工具更新，优先级高于泛泛观点文

## 参考文件

- 运行时代码：`tools/score_and_filter.py`
- 评估样本：`data/evals/scoring_samples.jsonl`
- 日产出：`data/scored/*.json`
