# ALT Mobility — Insurance Policy Dashboard

Extracts structured data from motor insurance policy PDFs and renders an
interactive dashboard with an expiry tracker. Now also exposes a FastAPI
endpoint for incrementally uploading new PDFs from the dashboard UI.

## What it produces

- **`dashboard/index.html`** — interactive dashboard with KPI cards, expiry
  alerts, charts, search/sort/filter, **PDF upload button**, CSV/Excel export.
- **`data/extracted.json`** — all rows in JSON.
- **`data/extracted.xlsx`** — multi-sheet Excel (live formulas + pivots).

## Extraction reliability

The extractor uses a 3-tier escalation to handle the wide variety of PDF layouts
(scanned certificates, image-only PDFs, long multi-column policy schedules):

1. **Text + primary model** (`gpt-4o-mini`): fast, cheap — handles most PDFs.
2. **Text + page images + fallback model** (`gpt-4o` Vision): kicks in when
   Tier 1 misses any core field (`vehicle_chassis_number`, `insurance_company_name`,
   `policy_number`, `od_end_date`), or the PDF has little/no text layer.
3. **Text-only on fallback model**: last-resort retry.

The method used per file is recorded in `data/cache/<file>.json` under
`_extraction_method`, so you can audit which policies needed escalation.

## Extracted columns

| Column | Source |
|---|---|
| `vehicle_chassis_number` | extracted from PDF |
| `insurance_company_name` | extracted from PDF |
| `policy_number` | extracted from PDF |
| `od_start_date` | extracted, normalised to ISO |
| `od_end_date` | extracted, normalised to ISO |
| `fire_covered` | extracted (Yes/No) |
| `damage_coverage` | extracted, comma-separated perils |
| `premium_amount` | extracted (INR, numeric) |
| `days_left` | computed: `od_end_date − today` |
| `status` | computed: Active / Expiring Soon / Expired |
| `policy_duration` | computed: years between OD start & end |
| `policy_type` | computed: Annual (1y) / Multi-Year (≥2y) |

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env and set OPENAI_API_KEY
```

## Run

### Option A — FastAPI server (with upload UI)

```bash
uvicorn api:app --reload --port 8000
# open http://localhost:8000
```

The dashboard at `/` includes an **Upload PDF** button. Each upload runs the
extraction pipeline, dedupes by chassis number / filename, updates
`data/extracted.json` + `data/extracted.xlsx`, and regenerates
`dashboard/index.html`.

### Option B — CLI (batch)

```bash
# 1. Extract every PDF in ./300 Insurance Copy/
python scripts/extract.py --workers 8

# 2. Render the dashboard
python scripts/build_dashboard.py

# 3. Open it
open dashboard/index.html
```

### Useful flags

```bash
python scripts/extract.py --limit 20            # smoke-test on 20 PDFs
python scripts/extract.py --input-dir ./pdfs    # custom PDF source
python scripts/build_dashboard.py --from-cache  # render even if extract.py crashed mid-run
```

Re-running `extract.py` skips any PDF that already has a cached result — safe to
interrupt and resume.

## Deploying to Render

The repo includes a `render.yaml` blueprint. To deploy:

1. Push this branch to GitHub.
2. On [render.com](https://render.com), create a new **Blueprint** and point it
   at this repo.
3. In the service's **Environment** tab, add `OPENAI_API_KEY`.
4. Deploy. Render uses `runtime.txt` (Python 3.12) and the start command from
   `render.yaml`.

Free-tier note: filesystem is ephemeral, so uploaded PDFs and `extracted.json`
reset on every redeploy. Fine for a demo. For persistence, attach a Render disk
or move uploads to S3.

## Project layout

```
src/
  schema.py          # Pydantic model + final column order
  pdf_extractor.py   # PyMuPDF text extraction
  ai_extractor.py    # OpenAI structured output call
  enrichment.py      # days_left, status, duration, policy_type
  pipeline.py        # orchestration + caching + concurrency
  excel_exporter.py  # multi-sheet Excel writer (shared by CLI + API)
scripts/
  extract.py           # PDFs → JSON + XLSX
  build_dashboard.py   # JSON → static HTML
dashboard/
  template.html      # dashboard shell (data injected at build time)
  index.html         # generated output
api.py               # FastAPI app: POST /api/upload + static dashboard
data/
  cache/*.json       # per-PDF AI results (gitignored)
  uploads/*.pdf      # incoming uploads via API (gitignored)
  extracted.json     # aggregated + enriched rows
  extracted.xlsx     # same, for Excel
```
