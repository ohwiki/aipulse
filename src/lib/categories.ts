import type { PulseCategory } from "./types";

export const CATEGORY_ORDER: PulseCategory[] = [
  "ai-models",
  "ai-products",
  "industry",
  "paper",
  "tip"
];

export const CATEGORY_META: Record<
  PulseCategory,
  { label: string; description: string }
> = {
  "ai-models": {
    label: "模型发布/更新",
    description: "模型能力、版本与接口更新。"
  },
  "ai-products": {
    label: "产品发布/更新",
    description: "AI 产品、功能和平台发布。"
  },
  industry: {
    label: "行业动态",
    description: "公司、融资、合作与行业趋势。"
  },
  paper: {
    label: "论文研究",
    description: "值得关注的论文与研究成果。"
  },
  tip: {
    label: "技巧与观点",
    description: "实践经验、方法论与观察。"
  }
};

export function getCategoryMeta(category: string) {
  return CATEGORY_META[category as PulseCategory] ?? {
    label: category,
    description: "近期条目。"
  };
}
