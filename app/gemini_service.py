"""VTU AIDS: generate diary entries JSON via Google Gemini."""

from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Any

from app.deps import import_genai
from app.entries_store import save_entries
from app.paths import skills_path

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"

# Tried in order after the user's Settings model (429 quota → next model).
RECOMMENDED_MODELS: tuple[str, ...] = (
    "gemini-2.5-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
    "gemini-2.0-flash",
)

# Free tier often has limit 0 for this model; map to a working default.
LEGACY_MODEL_MAP: dict[str, str] = {
    "gemini-2.0-flash": "gemini-2.5-flash",
    "gemini-2.0-flash-001": "gemini-2.5-flash",
}

REQUIRED_KEYS = (
    "date",
    "internship",
    "description",
    "hoursWorked",
    "learningOutcomes",
    "skillsUsed",
)


def normalize_model_name(model: str) -> str:
    m = (model or "").strip() or DEFAULT_GEMINI_MODEL
    return LEGACY_MODEL_MAP.get(m, m)


def models_to_try(preferred: str) -> list[str]:
    preferred = normalize_model_name(preferred)
    seen: set[str] = set()
    order: list[str] = []
    for m in [preferred, *RECOMMENDED_MODELS]:
        if m and m not in seen:
            seen.add(m)
            order.append(m)
    return order


def _load_skills_snippet(max_chars: int = 6000) -> str:
    path = skills_path()
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8")
    return text[:max_chars]


def _extract_json(text: str) -> Any:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    return json.loads(text)


def _validate_entry(raw: dict[str, Any], idx: int) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in REQUIRED_KEYS:
        if key not in raw:
            raise ValueError(f"Entry {idx}: missing {key}")
        val = raw[key]
        if key == "hoursWorked":
            out[key] = val
        else:
            s = str(val).strip()
            if not s and key != "referenceLinks":
                raise ValueError(f"Entry {idx}: empty {key}")
            out[key] = s
    out["referenceLinks"] = str(raw.get("referenceLinks", "")).strip()
    out["blockersRisks"] = str(raw.get("blockersRisks", "")).strip()
    if len(str(out["date"])) < 10:
        raise ValueError(f"Entry {idx}: invalid date")
    return out


def _snapshot_original(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "description": str(entry.get("description", "")),
        "hoursWorked": entry.get("hoursWorked"),
        "skillsUsed": str(entry.get("skillsUsed", "")),
        "learningOutcomes": str(entry.get("learningOutcomes", "")),
    }


def _clamp_hours(value: float) -> float:
    return max(0.0, min(24.0, round(float(value) * 4) / 4))


def apply_hours_to_entries(
    entries: list[dict[str, Any]],
    *,
    hours_mode: str,
    hours_constant: float,
    hours_min: float,
    hours_max: float,
) -> None:
    """Set hoursWorked per entry: fixed value or random in [min, max]."""
    mode = (hours_mode or "constant").strip().lower()
    if mode == "range":
        lo = _clamp_hours(min(hours_min, hours_max))
        hi = _clamp_hours(max(hours_min, hours_max))
        if lo == hi:
            for entry in entries:
                entry["hoursWorked"] = lo
            return
        for entry in entries:
            entry["hoursWorked"] = round(random.uniform(lo, hi) * 4) / 4
    else:
        fixed = _clamp_hours(hours_constant)
        for entry in entries:
            entry["hoursWorked"] = fixed


def merge_work_context(work_description: str, reference_context: str = "") -> str:
    """Combine manual description and uploaded document text for the prompt."""
    parts: list[str] = []
    if work_description.strip():
        parts.append(work_description.strip())
    if reference_context.strip():
        parts.append(
            "Reference material from uploaded documents (use for factual detail and vocabulary):\n"
            + reference_context.strip()
        )
    if not parts:
        raise ValueError(
            "Enter what you did in Step 2 and/or upload a reference document (PDF, images, code, etc.)."
        )
    return "\n\n".join(parts)


def build_prompt(
    dates: list[str],
    work_description: str,
    internship: str,
    default_hours: float | int,
    description_words: int = 80,
    *,
    reference_context: str = "",
) -> str:
    skills = _load_skills_snippet()
    dates_json = json.dumps(dates)
    combined_work = merge_work_context(work_description, reference_context)
    return f"""You are helping a VTU engineering student fill an internship diary.

For EACH date in this list, write one diary entry object.
Dates: {dates_json}

Student's overall work description and reference notes for this period:
{combined_work}

Internship label (use exactly for every entry): {internship.strip()}

Default hours per day: {default_hours}

Target length per entry:
- description: about {description_words} words (not characters)
- learningOutcomes: about {max(20, description_words // 2)} words

Rules:
- Return ONLY valid JSON, no markdown: {{"entries": [ ... ]}}
- One object per date in the list, same order as dates.
- Each object must have these keys exactly:
  date (YYYY-MM-DD), internship, description, hoursWorked (number),
  learningOutcomes, skillsUsed (comma-separated),
  referenceLinks (string, can be ""), blockersRisks (string, can be "")
- skillsUsed: pick only from the VTU skills list below (exact spelling).
- Vary description and learningOutcomes per day realistically based on the work description.
- internship must be identical on every row.

VTU skills list:
{skills}
"""


def _response_text(response: Any) -> str:
    raw_text = getattr(response, "text", None) or ""
    if not raw_text and getattr(response, "candidates", None):
        parts = response.candidates[0].content.parts
        raw_text = "".join(getattr(p, "text", "") or "" for p in parts)
    return raw_text


def _call_gemini_with_fallback(client: Any, models: list[str], prompt: str) -> tuple[str, str]:
    from google.genai import errors as genai_errors

    last_err: Exception | None = None
    quota_models: list[str] = []

    for model in models:
        try:
            response = client.models.generate_content(model=model, contents=prompt)
            return model, _response_text(response)
        except genai_errors.ClientError as e:
            last_err = e
            code = getattr(e, "status_code", None)
            msg = str(e)
            if (
                "API_KEY_INVALID" in msg
                or "API key not valid" in msg
                or (code == 400 and "INVALID_ARGUMENT" in msg and "API key" in msg)
            ):
                raise ValueError(
                    "Your Gemini API key was rejected by Google (invalid or revoked). "
                    "Create a new key at https://aistudio.google.com/apikey — open Settings, "
                    "paste the full key (starts with AIza), and click Save. "
                    "You can also set GEMINI_API_KEY in the environment."
                ) from e
            if code == 429 or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
                quota_models.append(model)
                continue
            raise ValueError(f"Gemini API error ({model}): {msg}") from e

    tried = ", ".join(quota_models) if quota_models else ", ".join(models)
    raise ValueError(
        "Gemini quota or rate limit exceeded for all tried models: "
        f"{tried}. Wait a minute and retry, or choose another model in Settings "
        "(recommended: gemini-2.5-flash or gemini-2.0-flash-lite). "
        "See https://ai.google.dev/gemini-api/docs/rate-limits"
    ) from last_err


def generate_entries(
    *,
    api_key: str,
    model: str,
    dates: list[str],
    work_description: str,
    internship: str,
    default_hours: float | int = 6,
    description_words: int = 80,
    hours_mode: str = "constant",
    hours_constant: float | int = 6,
    hours_min: float | int = 5,
    hours_max: float | int = 8,
    reference_context: str = "",
    persist: bool = True,
) -> dict[str, Any]:
    from app.config_store import normalize_api_key, validate_api_key_format

    api_key = normalize_api_key(api_key)
    validate_api_key_format(api_key)
    if not dates:
        raise ValueError("No dates selected.")
    if not internship.strip():
        raise ValueError("Internship name is required.")
    description_words = max(20, min(500, int(description_words)))
    mode = (hours_mode or "constant").strip().lower()
    if mode == "range":
        lo = _clamp_hours(min(hours_min, hours_max))
        hi = _clamp_hours(max(hours_min, hours_max))
        prompt_hours = (lo + hi) / 2
    else:
        prompt_hours = _clamp_hours(hours_constant if hours_constant is not None else default_hours)

    merge_work_context(work_description, reference_context)
    prompt = build_prompt(
        dates,
        work_description,
        internship,
        prompt_hours,
        description_words,
        reference_context=reference_context,
    )

    from app.paths import ensure_ssl_certificates

    ensure_ssl_certificates()
    genai = import_genai()
    client = genai.Client(api_key=api_key)
    models = models_to_try(model)
    model_used, raw_text = _call_gemini_with_fallback(client, models, prompt)

    try:
        parsed = _extract_json(raw_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Gemini did not return valid JSON: {e}\n\nRaw:\n{raw_text[:2000]}") from e

    if isinstance(parsed, list):
        items = parsed
    elif isinstance(parsed, dict) and "entries" in parsed:
        items = parsed["entries"]
    else:
        raise ValueError('Expected {"entries": [...]} or a JSON array.')

    entries = [_validate_entry(item, i + 1) for i, item in enumerate(items)]
    if len(entries) != len(dates):
        raise ValueError(f"Expected {len(dates)} entries, got {len(entries)}.")

    for expected, entry in zip(dates, entries):
        if entry["date"][:10] != expected[:10]:
            entry["date"] = expected

    apply_hours_to_entries(
        entries,
        hours_mode=mode,
        hours_constant=hours_constant if hours_constant is not None else default_hours,
        hours_min=hours_min,
        hours_max=hours_max,
    )
    for entry in entries:
        entry.setdefault("modified", False)
        entry["original"] = _snapshot_original(entry)
    if persist:
        save_entries(entries)
    payload: dict[str, Any] = {"entries": entries, "model_used": model_used}
    return payload


def generate_single_entry(
    *,
    api_key: str,
    model: str,
    date: str,
    work_description: str,
    internship: str,
    default_hours: float | int = 6,
    description_words: int = 80,
    hours_mode: str = "constant",
    hours_constant: float | int = 6,
    hours_min: float | int = 5,
    hours_max: float | int = 8,
    reference_context: str = "",
) -> dict[str, Any]:
    """Generate one diary entry with Gemini (does not write entries.json)."""
    date = str(date).strip()[:10]
    if len(date) < 10:
        raise ValueError("Invalid date.")
    payload = generate_entries(
        api_key=api_key,
        model=model,
        dates=[date],
        work_description=work_description,
        internship=internship,
        default_hours=default_hours,
        description_words=description_words,
        hours_mode=hours_mode,
        hours_constant=hours_constant,
        hours_min=hours_min,
        hours_max=hours_max,
        reference_context=reference_context,
        persist=False,
    )
    return {"entry": payload["entries"][0], "model_used": payload.get("model_used")}
