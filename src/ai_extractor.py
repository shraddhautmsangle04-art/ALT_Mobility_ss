from __future__ import annotations

import os
from typing import Iterable

from openai import OpenAI

from .schema import CORE_FIELDS, ExtractedPolicy

_SYSTEM_PROMPT = (
    "You are an expert reader of Indian motor insurance policy documents (private car, "
    "two-wheeler, goods/passenger commercial vehicle). You extract structured fields "
    "from raw PDF text or page images. "
    "Rules:\n"
    "- Always normalise dates to ISO YYYY-MM-DD.\n"
    "- Use the Own Damage (Section I / OD) period for od_start_date / od_end_date. "
    "If only a single 'Period of Insurance' is present, use it.\n"
    "- fire_covered is 'Yes' for any Package / Comprehensive / Bundled (OD+TP) policy "
    "unless fire is explicitly excluded. It is 'No' for Standalone-TP / Act-only policies.\n"
    "- damage_coverage must be a short comma-separated list of perils drawn from the "
    "Own Damage covered-perils section (accident, fire, explosion, self-ignition, lightning, "
    "theft, burglary, flood, cyclone, storm, earthquake, landslide, riot, strike, terrorism, "
    "malicious act, transit). For Standalone-TP policies return 'third-party only'.\n"
    "- premium_amount is the final total premium payable in INR including GST, as a plain number.\n"
    "- Never invent data. If a field is genuinely absent, return null.\n"
    "- Do NOT confuse the engine number with the chassis number."
)


_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], max_retries=8, timeout=60.0)
    return _client


def _primary_model() -> str:
    return os.environ.get("OPENAI_MODEL", "gpt-4o-mini")


def _fallback_model() -> str:
    return os.environ.get("OPENAI_FALLBACK_MODEL", "gpt-4o")


def _missing_core(data: dict) -> list[str]:
    return [f for f in CORE_FIELDS if not data.get(f)]


def _parse_text(text: str, model: str) -> ExtractedPolicy:
    completion = _get_client().beta.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"Policy document text:\n\n{text[:100000]}"},
        ],
        response_format=ExtractedPolicy,
        temperature=0.0,
    )
    return completion.choices[0].message.parsed


def _parse_with_images(text: str, images_b64: Iterable[str], model: str) -> ExtractedPolicy:
    content: list[dict] = [
        {"type": "text", "text": f"Policy document text (may be empty or noisy):\n\n{text[:60000]}"},
    ]
    for b64 in images_b64:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64}"},
        })
    completion = _get_client().beta.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        response_format=ExtractedPolicy,
        temperature=0.0,
    )
    return completion.choices[0].message.parsed


def extract_policy(text: str, images_b64: list[str] | None = None) -> tuple[dict, str]:
    """Return ``(data_dict, method_tag)``. Escalates through tiers if core fields are missing."""
    text = text or ""
    has_text = len(text.strip()) >= 200
    images_b64 = images_b64 or []

    # Tier 1 — text-only on primary model (cheap, fast).
    if has_text:
        data = _parse_text(text, _primary_model()).model_dump()
        if not _missing_core(data):
            return data, f"text:{_primary_model()}"
    else:
        data = {}

    # Tier 2 — text + images on fallback model (handles scanned / low-text PDFs).
    if images_b64:
        data2 = _parse_with_images(text, images_b64, _fallback_model()).model_dump()
        # Merge: prefer tier-2 values, fall back to tier-1 for fields tier-2 left null.
        merged = {k: (data2.get(k) if data2.get(k) not in (None, "") else data.get(k))
                  for k in set(data) | set(data2)}
        if not _missing_core(merged) or not has_text:
            return merged, f"vision:{_fallback_model()}"
        data = merged

    # Tier 3 — text-only on fallback model as a last resort.
    if has_text:
        data3 = _parse_text(text, _fallback_model()).model_dump()
        merged = {k: (data3.get(k) if data3.get(k) not in (None, "") else data.get(k))
                  for k in set(data) | set(data3)}
        return merged, f"text:{_fallback_model()}"

    return data, "insufficient_input"
