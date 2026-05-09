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
  category: PulseCategory | string;
  score: number;
  summary: string;
  publishedAt?: string;
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
