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


from src.excel_exporter import _write_excel

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
