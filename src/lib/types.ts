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
  sourceType?: string;
  category: PulseCategory | string;
  score: number;
  rankingScore?: number;
  summary: string;
  publishedAt?: string;
  votesCount?: number;
  featured?: boolean;
  topics?: string[];
  rankingReason?: string;
}

export interface DailySection {
  category: PulseCategory | string;
  label: string;
  items: PulseItem[];
}

export interface DailyDigest {
  date: string;
  generatedAt: string;
  total: number;
  sections: DailySection[];
}

export interface LatestDigest {
  generatedAt: string;
  days: number;
  total: number;
  items: PulseItem[];
}

export interface ArchiveEntry {
  date: string;
  generatedAt: string;
  total: number;
  sectionCount: number;
  highlights: PulseItem[];
}

export interface ArchiveIndex {
  generatedAt: string;
  total: number;
  count?: number;
  entries: ArchiveEntry[];
}
