import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { CATEGORY_ORDER, getCategoryMeta } from "./categories";
import type {
  ArchiveEntry,
  ArchiveIndex,
  DailyDigest,
  DailySection,
  LatestDigest,
  PulseItem
} from "./types";

interface RawItem {
  id: string;
  title?: string;
  title_en?: string;
  title_zh?: string;
  url: string;
  source: string;
  category?: string;
  summary?: string;
  summary_zh?: string;
  published_at?: string;
  publishedAt?: string;
  score?: number;
  rank_score?: number;
  rankingScore?: number;
  source_type?: string;
  sourceType?: string;
  votes_count?: number;
  votesCount?: number;
  featured?: boolean;
  topics?: string[];
  score_details?: {
    reason?: string;
  };
}

interface RawDailySection {
  category: string;
  label?: string;
  items: RawItem[];
}

interface RawDailyDigest {
  date: string;
  generated_at?: string;
  generatedAt?: string;
  total?: number;
  sections: RawDailySection[];
}

interface RawArchiveIndexEntry {
  date: string;
  generated_at?: string;
  generatedAt?: string;
  total?: number;
  sectionCount?: number;
  highlights?: RawItem[];
}

interface RawArchiveIndex {
  generated_at?: string;
  generatedAt?: string;
  total?: number;
  count?: number;
  entries: RawArchiveIndexEntry[];
}

interface RawLatestDigest {
  generated_at?: string;
  generatedAt?: string;
  days?: number;
  total?: number;
  items: RawItem[];
}

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT_DIR = path.resolve(__dirname, "../..");
const DATA_DIR = path.join(ROOT_DIR, "data");
const DAILY_DIR = path.join(DATA_DIR, "daily");
const INDEX_PATH = path.join(DATA_DIR, "index.json");
const DAILY_FILENAME_RE = /^\d{4}-\d{2}-\d{2}\.json$/;

function normalizeItem(item: RawItem): PulseItem {
  const title = item.title_zh ?? item.title ?? "";
  const titleEn = item.title_en ?? item.title;

  return {
    id: item.id,
    title,
    titleEn: titleEn && titleEn !== title ? titleEn : undefined,
    url: item.url,
    source: item.source,
    sourceType: item.source_type ?? item.sourceType,
    category: item.category ?? "",
    score: item.score ?? 0,
    rankingScore: item.rankingScore ?? item.rank_score ?? item.score ?? 0,
    summary: item.summary_zh ?? item.summary ?? "",
    publishedAt: item.published_at ?? item.publishedAt,
    votesCount: item.votesCount ?? item.votes_count,
    featured: item.featured,
    topics: item.topics ?? [],
    rankingReason: item.score_details?.reason
  };
}

function sortItems(items: PulseItem[]) {
  return [...items].sort((left, right) => {
    const leftScore = left.rankingScore ?? left.score;
    const rightScore = right.rankingScore ?? right.score;
    const leftTime = left.publishedAt ? new Date(left.publishedAt).getTime() : 0;
    const rightTime = right.publishedAt ? new Date(right.publishedAt).getTime() : 0;

    if (leftScore !== rightScore) {
      return rightScore - leftScore;
    }

    return rightTime - leftTime;
  });
}

function sortSections(sections: DailySection[]) {
  return [...sections].sort((left, right) => {
    const leftOrder = CATEGORY_ORDER.indexOf(left.category as never);
    const rightOrder = CATEGORY_ORDER.indexOf(right.category as never);

    if (leftOrder === -1 && rightOrder === -1) return 0;
    if (leftOrder === -1) return 1;
    if (rightOrder === -1) return -1;
    return leftOrder - rightOrder;
  });
}

async function readJson<T>(filepath: string): Promise<T> {
  const content = await fs.readFile(filepath, "utf8");
  return JSON.parse(content) as T;
}

function normalizeDailySection(section: RawDailySection): DailySection {
  const meta = getCategoryMeta(section.category);

  return {
    category: section.category,
    label: section.label ?? meta.label,
    items: sortItems(section.items.map(normalizeItem))
  };
}

function normalizeArchiveEntry(entry: RawArchiveIndexEntry): ArchiveEntry {
  return {
    date: entry.date,
    generatedAt: entry.generated_at ?? entry.generatedAt ?? "",
    total: entry.total ?? 0,
    sectionCount: entry.sectionCount ?? 0,
    highlights: sortItems((entry.highlights ?? []).map(normalizeItem)).slice(0, 3)
  };
}

function normalizeArchiveEntries(entries: RawArchiveIndexEntry[]): ArchiveEntry[] {
  const byDate = new Map<string, ArchiveEntry>();

  for (const entry of entries) {
    if (!entry.date) continue;
    byDate.set(entry.date, normalizeArchiveEntry(entry));
  }

  return [...byDate.values()].sort((left, right) => right.date.localeCompare(left.date));
}

async function listDailyDatesFromFilesystem(): Promise<string[]> {
  const entries = await fs.readdir(DAILY_DIR);

  return entries
    .filter((entry: string) => DAILY_FILENAME_RE.test(entry))
    .map((entry: string) => entry.replace(/\.json$/, ""));
}

async function loadArchiveIndex(): Promise<ArchiveIndex | null> {
  try {
    const raw = await readJson<RawArchiveIndex>(INDEX_PATH);
    const entries = Array.isArray(raw.entries) ? normalizeArchiveEntries(raw.entries) : [];
    if (!entries.length) {
      return null;
    }

    return {
      generatedAt: raw.generated_at ?? raw.generatedAt ?? "",
      total: raw.total ?? raw.count ?? entries.length,
      count: raw.count ?? raw.total ?? entries.length,
      entries
    };
  } catch {
    return null;
  }
}

export async function getDailyDates(): Promise<string[]> {
  const archiveIndex = await loadArchiveIndex();
  const indexedDates = archiveIndex?.entries.map((entry) => entry.date) ?? [];
  const fileDates = await listDailyDatesFromFilesystem();
  const merged = new Set<string>([...indexedDates, ...fileDates]);

  return [...merged].sort((left: string, right: string) => right.localeCompare(left));
}

export async function getDailyDigest(date: string): Promise<DailyDigest | null> {
  try {
    const raw = await readJson<RawDailyDigest>(path.join(DAILY_DIR, `${date}.json`));

    return {
      date: raw.date,
      generatedAt: raw.generated_at ?? raw.generatedAt ?? "",
      total: raw.total ?? raw.sections.flatMap((section) => section.items).length,
      sections: sortSections(raw.sections.map(normalizeDailySection))
    };
  } catch {
    return null;
  }
}

export async function getLatestDailyDigest(): Promise<DailyDigest | null> {
  const dates = await getDailyDates();
  const latestDate = dates[0];

  if (!latestDate) {
    return null;
  }

  return getDailyDigest(latestDate);
}

export async function getLatestDigest(): Promise<LatestDigest> {
  try {
    const raw = await readJson<RawLatestDigest>(path.join(DATA_DIR, "latest.json"));

    return {
      generatedAt: raw.generated_at ?? raw.generatedAt ?? "",
      days: raw.days ?? 0,
      total: raw.total ?? raw.items.length,
      items: sortItems(raw.items.map(normalizeItem))
    };
  } catch {
    return {
      generatedAt: "",
      days: 0,
      total: 0,
      items: []
    };
  }
}

export interface ItemQuery {
  category?: string;
  q?: string;
  since?: string;
  take?: number;
}

export async function listArchiveEntries(): Promise<ArchiveEntry[]> {
  const archiveIndex = await loadArchiveIndex();
  if (archiveIndex?.entries.length) {
    const indexedDates = new Set(archiveIndex.entries.map((entry) => entry.date));
    const fileDates = await listDailyDatesFromFilesystem();
    const missingDates = fileDates.filter((date) => !indexedDates.has(date));

    if (!missingDates.length) {
      return archiveIndex.entries;
    }

    const missingDigests = await Promise.all(missingDates.map((date) => getDailyDigest(date)));
    const missingEntries = missingDigests.filter((digest): digest is DailyDigest => digest !== null).map((digest) => ({
      date: digest.date,
      generatedAt: digest.generatedAt,
      total: digest.total,
      sectionCount: digest.sections.length,
      highlights: sortItems(digest.sections.flatMap((section) => section.items)).slice(0, 3)
    }));

    return [...archiveIndex.entries, ...missingEntries].sort((left, right) => right.date.localeCompare(left.date));
  }

  const dates = await getDailyDates();
  const digests = await Promise.all(dates.map((date) => getDailyDigest(date)));

  return digests
    .filter((digest): digest is DailyDigest => digest !== null)
    .map((digest) => ({
      date: digest.date,
      generatedAt: digest.generatedAt,
      total: digest.total,
      sectionCount: digest.sections.length,
      highlights: sortItems(digest.sections.flatMap((section) => section.items)).slice(0, 3)
    }));
}

export async function listCategoryItems(category: string): Promise<PulseItem[]> {
  const latest = await getLatestDigest();
  return latest.items.filter((item) => item.category === category);
}

export function getTopItems(digest: DailyDigest, take = 5): PulseItem[] {
  return sortItems(digest.sections.flatMap((section) => section.items)).slice(0, take);
}

export async function queryItems(params: ItemQuery = {}): Promise<PulseItem[]> {
  const latest = await getLatestDigest();
  let items = [...latest.items];

  if (params.category) {
    items = items.filter((item) => item.category === params.category);
  }

  if (params.q) {
    const keyword = params.q.trim().toLowerCase();
    if (keyword) {
      items = items.filter((item) =>
        [item.title, item.titleEn, item.summary, item.source]
          .filter(Boolean)
          .some((value) => value!.toLowerCase().includes(keyword))
      );
    }
  }

  if (params.since) {
    const sinceMs = Date.parse(params.since);
    if (!Number.isNaN(sinceMs)) {
      items = items.filter((item) => {
        if (!item.publishedAt) return false;
        const publishedMs = Date.parse(item.publishedAt);
        return !Number.isNaN(publishedMs) && publishedMs >= sinceMs;
      });
    }
  }

  const take = Math.max(1, Math.min(params.take ?? 50, 100));
  return sortItems(items).slice(0, take);
}
