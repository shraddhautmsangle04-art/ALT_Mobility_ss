<<<<<<< HEAD
# ALT Mobility — Insurance Policy Dashboard

Extracts structured data from motor insurance policy PDFs and renders a static HTML
dashboard with an expiry tracker.

## What it produces

A single `dashboard/index.html` (open in any browser — no server) containing:

- KPI cards: total, active, expiring soon (≤30d), expired
- Expiry alerts table for policies expiring within 30 days or already expired
- Charts: status distribution, top insurers, monthly expiry timeline
- Full interactive policy table: search, sort, paginate, filter, export CSV

Plus `data/extracted.xlsx` and `data/extracted.json` for further analysis.

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

```bash
# 1. Extract (uses OpenAI structured output; caches per-PDF in data/cache/)
python scripts/extract.py --workers 8

# 2. Render dashboard
python scripts/build_dashboard.py

# 3. Open dashboard/index.html in a browser
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

## Project layout

```
src/
  schema.py         # Pydantic model + final column order
  pdf_extractor.py  # PyMuPDF text extraction
  ai_extractor.py   # OpenAI structured output call
  enrichment.py     # days_left, status, duration, policy_type
  pipeline.py       # orchestration + caching + concurrency
scripts/
  extract.py           # PDFs → JSON + XLSX
  build_dashboard.py   # JSON → static HTML
dashboard/
  template.html     # dashboard shell (data injected at build time)
  index.html        # generated output
data/
  cache/*.json      # per-PDF AI results (gitignored)
  extracted.json    # aggregated + enriched rows
  extracted.xlsx    # same, for Excel
```
=======
# ALT_Mobility_ss
>>>>>>> 91ef9b8360eb2d73ede96cb519ce6e15af104dd7
