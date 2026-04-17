from __future__ import annotations

import base64
from pathlib import Path

import fitz


def extract_text(pdf_path: Path) -> str:
    text_parts: list[str] = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            text_parts.append(page.get_text())
    return "\n".join(text_parts)


def render_pages_as_png_b64(pdf_path: Path, *, dpi: int = 160, max_pages: int = 4) -> list[str]:
    """Rasterize the first ``max_pages`` of a PDF as base64-encoded PNGs for Vision APIs."""
    images: list[str] = []
    zoom = dpi / 72
    mat = fitz.Matrix(zoom, zoom)
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            pix = page.get_pixmap(matrix=mat, alpha=False)
            images.append(base64.b64encode(pix.tobytes("png")).decode("ascii"))
    return images
