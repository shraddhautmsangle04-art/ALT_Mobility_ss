from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def build(data_path: Path, template_path: Path, out_path: Path, from_cache: bool = False) -> list[dict]:
    rows: list[dict] = []

    if data_path.exists():
        rows = json.loads(data_path.read_text())
    elif from_cache:
        sys.path.insert(0, str(ROOT))
        from src.enrichment import enrich  # noqa: WPS433
        cache_dir = ROOT / "data" / "cache"
        for f in sorted(cache_dir.glob("*.json")):
            try:
                rows.append(enrich(json.loads(f.read_text())))
            except Exception as e:  # noqa: BLE001
                print(f"Skipped {f.name}: {e}", file=sys.stderr)
    else:
        raise FileNotFoundError(f"No data found at {data_path} and from_cache=False")

    template = template_path.read_text()
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rows": rows,
    }
    html = template.replace(
        "__DATA_JSON__",
        json.dumps(payload, default=str).replace("</", "<\\/"),
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the static HTML dashboard from extracted data.")
    parser.add_argument("--data", default=str(ROOT / "data" / "extracted.json"))
    parser.add_argument("--template", default=str(ROOT / "dashboard" / "template.html"))
    parser.add_argument("--out", default=str(ROOT / "dashboard" / "index.html"))
    parser.add_argument("--from-cache", action="store_true",
                        help="If extracted.json is missing, build from data/cache/*.json plus enrichment.")
    args = parser.parse_args()

    try:
        rows = build(Path(args.data), Path(args.template), Path(args.out), args.from_cache)
        print(f"Dashboard rendered: {args.out} ({len(rows)} rows)")
    except Exception as e:
        print(e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
