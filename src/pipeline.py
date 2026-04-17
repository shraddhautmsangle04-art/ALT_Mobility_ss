from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from tqdm import tqdm

from .ai_extractor import extract_policy
from .enrichment import enrich
from .pdf_extractor import extract_text, render_pages_as_png_b64


@dataclass
class PipelineResult:
    rows: list[dict]
    failures: list[tuple[str, str]]


def _process_one(pdf_path: Path, cache_dir: Path) -> dict:
    cache_file = cache_dir / f"{pdf_path.stem}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text())

    raw_text = extract_text(pdf_path)
    images: list[str] = []
    if len(raw_text.strip()) < 400:
        # Likely scanned or image-only — render pages for Vision fallback.
        images = render_pages_as_png_b64(pdf_path)
    else:
        # Render a small sample for Tier-2 escalation if needed.
        images = render_pages_as_png_b64(pdf_path, max_pages=2)

    data, method = extract_policy(raw_text, images)
    data["source_file"] = pdf_path.name
    data["_extraction_method"] = method
    cache_file.write_text(json.dumps(data, default=str, indent=2))
    return data


def run(
    input_dir: Path,
    cache_dir: Path,
    *,
    workers: int = 8,
    limit: int | None = None,
) -> PipelineResult:
    cache_dir.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(p for p in input_dir.glob("*.pdf"))
    if limit is not None:
        pdfs = pdfs[:limit]

    rows: list[dict] = []
    failures: list[tuple[str, str]] = []

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_process_one, p, cache_dir): p for p in pdfs}
        for fut in tqdm(as_completed(futures), total=len(futures), desc="Extracting"):
            pdf = futures[fut]
            try:
                rows.append(enrich(fut.result()))
            except Exception as e:  # noqa: BLE001
                failures.append((pdf.name, str(e)))

    rows.sort(key=lambda r: r.get("source_file", ""))
    return PipelineResult(rows=rows, failures=failures)
