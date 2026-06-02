# AIpulse

> 💡 Ecosystem Note: This entire project and its 6-layer modular monorepo architecture were fully co-developed, refactored, and optimized natively using AWS Kiro CLI

[中文文档](./README.zh-CN.md)

A daily AI news aggregation platform for Chinese-speaking AI practitioners.

The repository contains two integrated parts:

- **Python pipeline**: Fetches, scores, filters, and generates `data/*.json`
- **Astro frontend**: Syncs production JSON from the `data` branch at build time, generating static news pages

## Architecture

This is a single end-to-end pipeline:

```text
Python tools → data branch → Astro build → static pages
```

Branch strategy:

- `main`: Code and documentation
- `data`: Production data files
- GitHub Actions: Daily data generation and push
- Netlify: Syncs `data` branch before build; can be triggered via build hook on data updates

To enable automatic Netlify rebuilds, configure `NETLIFY_BUILD_HOOK_URL` in GitHub Secrets.

## Directory Structure

```text
aipulse/
├── data/          # Local outputs, evaluation samples, build-time synced data
├── docs/          # Design docs and task docs
├── src/           # Astro frontend source
├── tools/         # Python data pipeline
├── .github/       # GitHub Actions
├── package.json   # Frontend dependencies and scripts
├── pnpm-lock.yaml
├── pyproject.toml
├── uv.lock
└── README.md
```

## Python Data Pipeline

Current capabilities:

- Fetches entries from RSS, arXiv, and HuggingFace Daily Papers (last 24 hours)
- Pulls high-vote new products from Product Hunt GraphQL API, filtered by AI keywords
- Calls MiMo-compatible API for scoring and filtering high-value news
- Generates category-organized daily JSON and 7-day aggregated data
- Supports scheduled GitHub Actions execution

### Setup

```bash
uv sync
```

### Local Configuration

AIpulse reads `.env` and `.env.local` from the repository root.

```bash
cp .env.example .env
```

Fill in your keys in `.env`:

- `NULLCLAW_API_KEY`
- `PRODUCTHUNT_DEVELOPER_TOKEN`

Alternatively, use:

- `PRODUCTHUNT_CLIENT_ID`
- `PRODUCTHUNT_CLIENT_SECRET`

### Running the Pipeline

1. Fetch raw data:

```bash
uv run python tools/fetch_sources.py
```

2. Score and filter:

```bash
uv run python tools/score_and_filter.py        # Real LLM mode
uv run python tools/score_and_filter.py --dry-run  # Dry-run mode (no API key needed)
```

3. Generate daily report:

```bash
uv run python tools/generate_daily.py
```

Full dry-run sequence:

```bash
uv run python tools/fetch_sources.py
uv run python tools/score_and_filter.py --dry-run
uv run python tools/generate_daily.py
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `NULLCLAW_API_KEY` | MiMo API Key | — |
| `NULLCLAW_BASE_URL` | API Base URL | `https://platform.xiaomimimo.com/v1` |
| `NULLCLAW_MODEL` | Model name | `mimo-v2.5-pro` |
| `PRODUCTHUNT_DEVELOPER_TOKEN` | Product Hunt developer token | — |
| `PRODUCTHUNT_CLIENT_ID` / `SECRET` | Alternative PH credentials | — |

Priority: process env → `.env.local` → `.env`

Without `NULLCLAW_API_KEY`:
- Normal mode will error with a prompt to configure the key
- `--dry-run` mode skips real LLM calls, using heuristic scores and placeholder summaries

### Output

| Path | Description |
|------|-------------|
| `data/raw/YYYY-MM-DD.json` | Raw fetch results |
| `data/scored/YYYY-MM-DD.json` | Scored and localized results |
| `data/daily/YYYY-MM-DD.json` | Daily report |
| `data/index.json` | Report archive index |
| `data/latest.json` | Last 7 days aggregated |

- Local runs write to `data/` in the working directory
- In production, GitHub Actions publishes to the `data` branch
- `main` branch does not carry production JSON

### Data Source Management

- `tools/sources.yaml` supports `enabled: false` to disable sources
- Optional `note` field appears in fetch logs
- `daily.category_limits` controls per-category display counts
- Lightweight reclassification runs before scoring to correct category assignments

## Astro Frontend

The frontend syncs `data/daily/*.json`, `data/index.json`, and `data/latest.json` from the `data` branch before building static pages.

### Pages

| Route | Description |
|-------|-------------|
| `/` | Today's picks |
| `/archive` | Report archive |
| `/archive/{date}` | Single-day report |
| `/category/{slug}` | Category browse |
| `/about` | About |
| `/privacy` | Privacy policy |
| `/contact` | Contact |
| `/methodology` | Methodology |
| `/sources-and-attribution` | Sources and attribution |
| `/sitemap.xml` | Sitemap |
| `/robots.txt` | Crawler rules |

### Frontend Commands

```bash
pnpm install          # Install dependencies
pnpm dev              # Development mode
pnpm check            # Type and Astro diagnostics
pnpm build            # Production build
pnpm sync:data && pnpm build  # Simulate production build
```

## Current Status

- Python pipeline produces `data/raw`, `data/scored`, `data/daily`, `data/latest`
- Frontend uses `pnpm`
- `pnpm check` passes
- `pnpm build` passes

## License

MIT
