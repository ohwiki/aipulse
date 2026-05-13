import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_ROOT_DIR = path.resolve(__dirname, "..");

function parseArgs(argv) {
  let rootDir = DEFAULT_ROOT_DIR;

  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--root") {
      rootDir = path.resolve(argv[index + 1] || rootDir);
      index += 1;
    }
  }

  return { rootDir };
}

function sortScore(item) {
  const rankScore = item?.rank_score ?? item?.rankingScore ?? item?.score ?? 0;
  return Number(rankScore) || 0;
}

function sortItems(items) {
  return [...items].sort((left, right) => {
    const leftScore = sortScore(left);
    const rightScore = sortScore(right);
    const leftTime = left?.published_at ?? left?.publishedAt ?? "";
    const rightTime = right?.published_at ?? right?.publishedAt ?? "";

    if (leftScore !== rightScore) {
      return rightScore - leftScore;
    }

    return String(rightTime).localeCompare(String(leftTime));
  });
}

function buildEntry(payload) {
  const sections = Array.isArray(payload?.sections) ? payload.sections : [];
  const items = Array.isArray(payload?.items)
    ? payload.items
    : sections.flatMap((section) => (Array.isArray(section?.items) ? section.items : []));
  const generatedAt = String(payload?.generatedAt ?? payload?.generated_at ?? "");

  return {
    date: String(payload?.date ?? ""),
    generated_at: generatedAt,
    generatedAt,
    total: Number(payload?.total ?? items.length) || 0,
    sectionCount: sections.length,
    highlights: sortItems(items).slice(0, 3)
  };
}

async function rebuildIndex(rootDir) {
  const dataDir = path.join(rootDir, "data");
  const dailyDir = path.join(dataDir, "daily");
  const indexPath = path.join(dataDir, "index.json");

  const entries = [];
  const files = await fs.readdir(dailyDir);
  for (const file of files.filter((name) => /^\d{4}-\d{2}-\d{2}\.json$/.test(name)).sort().reverse()) {
    const payloadPath = path.join(dailyDir, file);
    const payload = JSON.parse(await fs.readFile(payloadPath, "utf8"));
    if (!payload?.date) {
      continue;
    }
    entries.push(buildEntry(payload));
  }

  const normalizedEntries = entries
    .filter((entry) => entry.date)
    .sort((left, right) => right.date.localeCompare(left.date));

  const generatedAt = normalizedEntries[0]?.generatedAt || new Date().toISOString();
  const indexPayload = {
    generated_at: generatedAt,
    generatedAt,
    count: normalizedEntries.length,
    total: normalizedEntries.length,
    entries: normalizedEntries
  };

  await fs.writeFile(indexPath, `${JSON.stringify(indexPayload, null, 2)}\n`, "utf8");
  return indexPayload;
}

async function main() {
  const { rootDir } = parseArgs(process.argv.slice(2));
  await rebuildIndex(rootDir);
}

main().catch((error) => {
  console.error("[rebuild-generated-index] failed", error);
  process.exit(1);
});
