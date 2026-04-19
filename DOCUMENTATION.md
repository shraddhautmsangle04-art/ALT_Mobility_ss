# ALT Mobility — Insurance Policy Dashboard
## Project Documentation

---

## 1. Overview

This project automates the extraction of structured data from motor insurance policy PDFs and presents it as an interactive dashboard with an expiry tracker. It was built as a data engineering assignment for ALT Mobility.

**The problem it solves:**  
ALT Mobility manages a large fleet of electric vehicles, each with its own insurance policy issued by different insurance companies in different document formats. Manually reading 315+ PDFs to track expiry dates, coverage details, and premium amounts is time-consuming and error-prone. This project automates that entirely.

**What it produces:**
- A self-contained `dashboard/index.html` (opens in any browser, no server needed) with live KPIs, expiry alerts, charts, and a searchable/filterable policy table
- A `data/extracted.xlsx` with 6 sheets — flat data + 5 summary/pivot views
- A `data/extracted.json` — raw structured data for any further analysis

---

## 2. Project Structure

```
ALT_Mobility/
├── src/                        # Core Python modules
│   ├── schema.py               # Pydantic model + column definitions
│   ├── pdf_extractor.py        # PDF → text + page images
│   ├── ai_extractor.py         # OpenAI structured extraction (3-tier)
│   ├── enrichment.py           # Derived columns (days_left, status, etc.)
│   └── pipeline.py             # Orchestration, caching, concurrency
│
├── scripts/
│   ├── extract.py              # CLI: process PDFs → JSON + Excel
│   └── build_dashboard.py      # CLI: JSON → static HTML dashboard
│
├── dashboard/
│   ├── template.html           # Dashboard shell (data injected at build time)
│   └── index.html              # Generated output — share this file
│
├── data/
│   ├── cache/                  # Per-PDF AI results (one JSON per PDF)
│   ├── extracted.json          # Aggregated + enriched, all 315 rows
│   └── extracted.xlsx          # Same data as multi-sheet Excel
│
├── 300 Insurance Copy/         # 315 source PDFs (gitignored)
├── assignment.md               # Original assignment specification
├── requirements.txt            # Python dependencies
├── .env.example                # API key template
└── README.md                   # Quick-start guide
```

---

## 3. The 12-Column Schema

Every policy row contains exactly these columns:

| # | Column | Source | Description |
|---|--------|--------|-------------|
| 1 | `vehicle_chassis_number` | AI extracted | Unique 17-character vehicle identifier (VIN). Distinct from engine number and registration number. |
| 2 | `insurance_company_name` | AI extracted | Issuing insurer (e.g. ICICI Lombard, Royal Sundaram, Go Digit, National Insurance). |
| 3 | `policy_number` | AI extracted | Certificate/policy number. Not the proposal number or receipt number. |
| 4 | `od_start_date` | AI extracted | Own Damage (OD) policy start date, ISO format YYYY-MM-DD. |
| 5 | `od_end_date` | AI extracted | Own Damage (OD) policy expiry date, ISO format YYYY-MM-DD. Used for all renewal tracking. |
| 6 | `fire_covered` | AI extracted | Yes/No — whether fire, explosion, self-ignition, or lightning is a covered peril under OD. |
| 7 | `damage_coverage` | AI extracted | Comma-separated list of perils covered under Own Damage (accident, fire, flood, theft, etc.). |
| 8 | `premium_amount` | AI extracted | Total premium payable in INR including GST. Plain number, no currency symbol. |
| 9 | `days_left` | Computed | Days until OD expiry from today's date. Negative = already expired. Auto-updates every time the dashboard or Excel is opened. |
| 10 | `status` | Computed | `Active` (>30 days left) / `Expiring Soon` (0–30 days) / `Expired` (past expiry). |
| 11 | `policy_duration` | Computed | Policy length in whole years (1, 2, or 3), derived from OD start/end dates. |
| 12 | `policy_type` | Computed | `Annual` (1 year) or `Multi-Year` (2+ years). |

**Columns 1–8** are extracted by the AI from the PDF text.  
**Columns 9–12** are computed by the Python enrichment module using pure arithmetic — no AI involved.

---

## 4. How the AI Extraction Works

### 4.1 The Tool: OpenAI Structured Outputs

The project uses OpenAI's **Structured Outputs** API (`client.beta.chat.completions.parse`). Unlike regular chat completions, this guarantees that the AI response exactly matches a predefined JSON schema — the Pydantic model `ExtractedPolicy` in `src/schema.py`. There is no regex parsing, no post-processing of free text.

Each field in `ExtractedPolicy` has a detailed description that tells the AI:
- What the field means
- What labels to look for in the PDF (e.g. "Chassis No", "Chassis / Frame No", "VIN")
- What to avoid (e.g. "do NOT return the engine number")
- What format to return (ISO date, plain number, Yes/No)

### 4.2 The 3-Tier Escalation

Not all PDFs are the same. Some have clean text layers; others are scanned images with no text. The extractor uses a tiered approach to handle all cases:

```
Tier 1 ─── text only ──────────── gpt-4o-mini  (cheap, fast — ~$0.001/PDF)
              │
              │  if any core field is null
              ▼
Tier 2 ─── text + page images ─── gpt-4o Vision  (handles scanned PDFs)
              │
              │  if core fields still missing
              ▼
Tier 3 ─── text only ──────────── gpt-4o  (full model, last resort)
```

**Core fields** (the gate for escalation): `vehicle_chassis_number`, `insurance_company_name`, `policy_number`, `od_end_date`. If any of these is null after a tier, it escalates.

**Result across 315 PDFs:**
- 314 PDFs resolved on Tier 1 (gpt-4o-mini)
- 1 PDF escalated to Tier 3 (gpt-4o)
- Total cost: ~$0.23 (~₹19)

### 4.3 The System Prompt

The AI is given Indian motor insurance-specific context including:
- OD vs TP (Third Party) period distinction — only OD dates are relevant
- Package/Comprehensive vs Standalone TP policy distinction
- Fire coverage defaults (almost always Yes for package policies)
- Common document labels across different insurers
- Premium = GST-inclusive total, not net OD premium

### 4.4 Per-PDF Caching

Each PDF's AI result is saved as `data/cache/<filename>.json` immediately after extraction. This means:
- Re-running the extractor skips any already-processed PDFs — safe to interrupt
- If you want to re-extract a specific PDF (e.g. if the result looks wrong), just delete its cache file and re-run
- The cache file also records `_extraction_method` so you know which tier was used

---

## 5. The Pipeline

```
300 Insurance Copy/
        │
        │  src/pdf_extractor.py
        ▼
  Raw PDF text  ──────────────────────────────────────────────────
  + page images (if low/no text)                                  │
        │                                                         │
        │  src/ai_extractor.py                                    │
        ▼                                                         │
  ExtractedPolicy (8 fields)   ←── gpt-4o-mini / gpt-4o Vision   │
        │                                                         │
        │  src/enrichment.py                                      │
        ▼                                                         │
  Enriched row (12 fields)                                        │
        │                                                         │
        │  Cached to data/cache/<file>.json  ─────────────────────┘
        │
        ▼
  data/extracted.json  (315 rows)
  data/extracted.xlsx  (6 sheets)
        │
        │  scripts/build_dashboard.py
        ▼
  dashboard/index.html  (data baked in, self-contained)
```

The pipeline uses a `ThreadPoolExecutor` with 8 workers by default, processing up to 8 PDFs concurrently. The OpenAI client is configured with `max_retries=8` to automatically handle rate limit (429) errors with exponential backoff.

---

## 6. The Dashboard

`dashboard/index.html` is a **completely self-contained file** — all 315 rows of data are embedded inside it as JSON. It requires no server, no internet connection, and no installation. Double-click to open in any browser on any OS.

### 6.1 KPI Cards
Four cards at the top showing live counts:
- **Total Policies** — 315
- **Active** — policies with >30 days until expiry
- **Expiring Soon (≤30d)** — policies needing renewal attention
- **Expired** — policies past their OD end date

### 6.2 Expiry Alerts
A dedicated alert section listing all policies expiring within 30 days or already expired, sorted by days remaining (most urgent first). Shows chassis, policy number, insurer, expiry date, days left, and status.

### 6.3 Charts
Three charts for visual analysis:
- **Status distribution** — doughnut chart (Active / Expiring Soon / Expired)
- **Policies by insurer** — horizontal bar chart showing top 15 insurers by policy count
- **Expiry timeline** — bar chart showing how many policies expire each month

### 6.4 Full Policy Table
- Search across all fields
- Sort by any column
- Filter by status (Active / Expiring Soon / Expired)
- Filter by insurance company
- Pagination (25 rows per page)
- **Download Excel button** — generates a full 6-sheet Excel file in the browser using SheetJS, no server required. Respects active filters.

### 6.5 Live Date Calculation
`days_left` and `status` are **recalculated every time the dashboard is opened** using JavaScript's `Date()` against today's date. They do not use the stored values from extraction time. This means the dashboard is always current without needing to re-run the extractor.

---

## 7. The Excel File

`data/extracted.xlsx` has 6 sheets:

| Sheet | Contents |
|-------|----------|
| **All Policies** | All 315 rows with all 12 columns. `days_left` and `status` columns use Excel `TODAY()` formulas — auto-update every time the file is opened. Has auto-filter and frozen header row. |
| **Expiry Alerts (≤30d)** | Filtered view of policies expiring within 30 days, sorted by urgency. |
| **By Status** | Policy count and total premium grouped by Active/Expiring Soon/Expired. |
| **By Insurer** | Policy count, total premium, and average premium per insurance company. |
| **By Policy Type** | Breakdown by Annual vs Multi-Year policies. |
| **By Expiry Month** | Count of policies expiring per calendar month. |

---

## 8. Data Quality & Verification

### 8.1 Automated Cross-Check Results
Since many PDF filenames contain the chassis number or policy number, the extractor was verified by cross-referencing filenames against extracted values:
- **98 PDFs** with chassis-number filenames → 100% match
- **32 PDFs** with policy-number filenames → 100% match
- **4 PDFs** with registration-number filenames → correctly extracted chassis from inside the PDF
- **Zero null fields** across all 315 rows (except 1 policy number — see below)

### 8.2 The One Null Policy Number
`ALT-DDCO-4601.pdf` returns `null` for `policy_number`. This is **correct** — the document is a **Proposal Form** (pre-policy), not an insurance certificate. It contains a Proposal No. `PF16793181` but no policy number, because the policy number is only assigned after the insurer accepts and processes the proposal.

### 8.3 Extraction Cost
- **Primary model:** gpt-4o-mini — handles 99.7% of PDFs
- **Fallback model:** gpt-4o — used for 0.3% (1 PDF)
- **Total cost for all 315 PDFs:** ~$0.23 (~₹19)

---

## 9. How to Run

### First-time setup
```bash
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### Extract data
```bash
python scripts/extract.py --workers 8
```
- Skips PDFs that already have a cache file — safe to interrupt and resume
- Add `--limit 10` to test on a small sample first

### Build the dashboard
```bash
python scripts/build_dashboard.py
```

### Open
```bash
open dashboard/index.html       # macOS
start dashboard\index.html      # Windows
```

### Re-extract a single PDF
```bash
rm data/cache/<filename>.json
python scripts/extract.py --workers 4
```

---

## 10. Technology Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| PDF text extraction | PyMuPDF (fitz) | Fast, reliable, handles both text and image PDFs |
| PDF page rendering | PyMuPDF Pixmap | Rasterises pages for Vision API fallback |
| AI extraction | OpenAI gpt-4o-mini / gpt-4o | Structured outputs guarantee schema compliance |
| Schema validation | Pydantic v2 | Type-safe, self-documenting field definitions |
| Data processing | pandas | Aggregations, Excel writing |
| Excel output | openpyxl | Multi-sheet workbook with live formulas |
| Concurrency | ThreadPoolExecutor | Parallel API calls, 8x throughput |
| Dashboard | Tailwind CSS + Chart.js + Grid.js + SheetJS | Single-file, no build step, works offline |
| Env management | python-dotenv | Keeps API keys out of code |

---

## 11. Key Design Decisions

**Why a static HTML dashboard instead of a web app?**  
The assignment is a one-time analysis of a fixed set of PDFs, not a product. A static file is zero-infrastructure — the reviewer opens one file, no server to start, no dependencies to install. It can be emailed, uploaded to Drive, or shared via GitHub.

**Why cache per-PDF results?**  
Processing 315 PDFs with an LLM takes time and costs money. Caching means: (a) the run can be interrupted and resumed, (b) re-running after fixing a bug costs nothing for already-processed files, (c) individual PDFs can be re-extracted in isolation.

**Why structured outputs instead of prompt engineering?**  
Regular chat completions return free text that must be parsed with regex or JSON.loads — brittle and error-prone. Structured outputs force the model to return exactly the Pydantic schema, with the right types, every time. No parsing needed.

**Why live formulas in Excel?**  
If `days_left` and `status` were stored as static numbers, the file would show wrong values the next day. Excel's `TODAY()` function makes these columns self-updating — the file is always correct when opened.
