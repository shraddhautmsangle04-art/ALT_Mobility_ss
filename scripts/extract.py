from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.pipeline import run  # noqa: E402
from src.schema import FINAL_COLUMNS  # noqa: E402


def _write_excel(df: pd.DataFrame, xlsx_path: Path) -> None:
    """Write the flat sheet plus pivot/analytics sheets used by reviewers."""
    df = df.copy()
    df["premium_amount"] = pd.to_numeric(df["premium_amount"], errors="coerce")
    df["od_end_date_dt"] = pd.to_datetime(df["od_end_date"], errors="coerce")

    by_status = (
        df.groupby("status", dropna=False)
        .agg(policies=("source_file", "count"), total_premium=("premium_amount", "sum"))
        .reset_index()
        .sort_values("policies", ascending=False)
    )

    by_company = (
        df.groupby("insurance_company_name", dropna=False)
        .agg(
            policies=("source_file", "count"),
            total_premium=("premium_amount", "sum"),
            avg_premium=("premium_amount", "mean"),
        )
        .reset_index()
        .sort_values("policies", ascending=False)
    )

    by_type = (
        df.groupby(["policy_type", "policy_duration"], dropna=False)
        .agg(policies=("source_file", "count"), total_premium=("premium_amount", "sum"))
        .reset_index()
        .sort_values("policies", ascending=False)
    )

    by_month = (
        df.assign(expiry_month=df["od_end_date_dt"].dt.strftime("%Y-%m"))
        .groupby("expiry_month", dropna=False)
        .agg(policies=("source_file", "count"))
        .reset_index()
        .sort_values("expiry_month")
    )

    alerts = (
        df[df["days_left"].apply(lambda v: isinstance(v, (int, float)) and v <= 30)]
        .sort_values("days_left")
        .drop(columns=["od_end_date_dt"])
    )

    df = df.drop(columns=["od_end_date_dt"])

    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="All Policies")
        alerts.to_excel(writer, index=False, sheet_name="Expiry Alerts (<=30d)")
        by_status.to_excel(writer, index=False, sheet_name="By Status")
        by_company.to_excel(writer, index=False, sheet_name="By Insurer")
        by_type.to_excel(writer, index=False, sheet_name="By Policy Type")
        by_month.to_excel(writer, index=False, sheet_name="By Expiry Month")


def main() -> int:
    load_dotenv(ROOT / ".env")

    parser = argparse.ArgumentParser(description="Extract structured data from insurance PDFs.")
    parser.add_argument("--input-dir", default=str(ROOT / "300 Insurance Copy"))
    parser.add_argument("--data-dir", default=str(ROOT / "data"))
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--limit", type=int, default=None, help="Process only the first N PDFs.")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = data_dir / "cache"

    if not input_dir.exists():
        print(f"Input directory not found: {input_dir}", file=sys.stderr)
        return 1

    import os
    if not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY not set. Copy .env.example to .env and set your key.", file=sys.stderr)
        return 1

    result = run(input_dir, cache_dir, workers=args.workers, limit=args.limit)

    ordered_cols = ["source_file", *FINAL_COLUMNS]
    df = pd.DataFrame(result.rows)
    for col in ordered_cols:
        if col not in df.columns:
            df[col] = None
    df = df[ordered_cols]

    json_path = data_dir / "extracted.json"
    xlsx_path = data_dir / "extracted.xlsx"

    json_path.write_text(json.dumps(result.rows, default=str, indent=2))
    _write_excel(df, xlsx_path)

    print(f"Extracted {len(result.rows)} policies -> {json_path}")
    print(f"Excel export -> {xlsx_path}")
    if result.failures:
        print(f"\n{len(result.failures)} failures:")
        for name, err in result.failures[:20]:
            print(f"  - {name}: {err}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
