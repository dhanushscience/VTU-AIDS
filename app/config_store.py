"""Load/save student_config.json (credentials and Gemini settings)."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from app.paths import config_path

DEFAULT_CONFIG: dict[str, Any] = {
    "username": "",
    "password": "",
    "gemini_api_key": "",
    "gemini_model": "gemini-2.5-flash",
    "default_internship": "",
    "default_hours": 6,
    "default_description_words": 80,
    "hours_mode": "constant",
    "hours_constant": 6,
    "hours_min": 5,
    "hours_max": 8,
}

_LEGACY_MODELS = {
    "gemini-2.0-flash",
    "gemini-2.0-flash-001",
}

_GEMINI_KEY_RE = re.compile(r"^AIza[0-9A-Za-z_-]{30,}$")


def normalize_api_key(raw: str) -> str:
    """Strip whitespace/quotes; Google keys must not contain spaces."""
    k = str(raw or "").strip().strip('"').strip("'")
    return "".join(k.split())


def validate_api_key_format(key: str) -> None:
    if not key or key == "***":
        raise ValueError(
            "Gemini API key is missing. Open Settings and paste a key from "
            "https://aistudio.google.com/apikey then click Save."
        )
    if not _GEMINI_KEY_RE.match(key):
        raise ValueError(
            "API key format looks wrong. Create a new key at "
            "https://aistudio.google.com/apikey — it should start with AIza and "
            "have no spaces. Paste the full key, then Save."
        )


def resolve_gemini_api_key(cfg: dict[str, Any]) -> str:
    """Config file first, then GEMINI_API_KEY environment variable."""
    key = normalize_api_key(str(cfg.get("gemini_api_key", "")))
    if not key:
        key = normalize_api_key(os.environ.get("GEMINI_API_KEY", ""))
    return key


def load_config(path: Path | None = None) -> dict[str, Any]:
    p = path or config_path()
    if not p.is_file():
        return dict(DEFAULT_CONFIG)
    with p.open(encoding="utf-8") as f:
        data = json.load(f)
    out = dict(DEFAULT_CONFIG)
    out.update({k: data.get(k, out[k]) for k in DEFAULT_CONFIG})
    if out.get("gemini_model") in _LEGACY_MODELS:
        out["gemini_model"] = DEFAULT_CONFIG["gemini_model"]
    if out.get("gemini_api_key"):
        out["gemini_api_key"] = normalize_api_key(str(out["gemini_api_key"]))
    return out


def save_config(data: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    p = path or config_path()
    current = load_config(p)
    for key in DEFAULT_CONFIG:
        if key in data:
            val = data[key]
            if key == "gemini_api_key":
                val = normalize_api_key(str(val))
            current[key] = val
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(current, f, indent=2, ensure_ascii=False)
    tmp.replace(p)
    return current


def config_for_api(path: Path | None = None) -> dict[str, Any]:
    """Mask secrets for GET responses."""
    return config_for_api_from(load_config(path))


def config_for_api_from(cfg: dict[str, Any]) -> dict[str, Any]:
    """Mask secrets from an in-memory config dict (avoids extra disk read)."""
    return {
        "username": cfg.get("username", ""),
        "password": "***" if cfg.get("password") else "",
        "has_password": bool(cfg.get("password")),
        "gemini_api_key": "***" if cfg.get("gemini_api_key") else "",
        "has_gemini_api_key": bool(cfg.get("gemini_api_key")),
        "gemini_model": cfg.get("gemini_model", DEFAULT_CONFIG["gemini_model"]),
        "default_internship": cfg.get("default_internship", ""),
        "default_hours": cfg.get("default_hours", 6),
        "default_description_words": cfg.get("default_description_words", 80),
        "hours_mode": cfg.get("hours_mode", "constant"),
        "hours_constant": cfg.get("hours_constant", cfg.get("default_hours", 6)),
        "hours_min": cfg.get("hours_min", 5),
        "hours_max": cfg.get("hours_max", 8),
    }


def config_with_secrets(path: Path | None = None) -> dict[str, Any]:
    return load_config(path)
