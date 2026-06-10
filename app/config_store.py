"""Load/save student_config.json (credentials and Gemini settings)."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.paths import config_path

_REQUIRED_SETUP_KEYS = ("username", "password", "gemini_api_key")
_OPTIONAL_CONFIG_KEYS = ("setup_completed_at",)

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
    "internship_start_date": "",
    "internship_end_date": "",
    "internship_total_days": 0,
}

_LEGACY_MODELS = frozenset(
    {
        "gemini-1.0-pro",
        "gemini-1.5-flash",
        "gemini-1.5-flash-8b",
        "gemini-1.5-pro",
        "gemini-2.0-flash",
        "gemini-2.0-flash-001",
        "gemini-2.0-flash-lite",
        "gemini-2.0-flash-lite-001",
    }
)

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
        from app.gemini_service import normalize_model_name

        out["gemini_model"] = normalize_model_name(str(out["gemini_model"]))
    if out.get("gemini_api_key"):
        out["gemini_api_key"] = normalize_api_key(str(out["gemini_api_key"]))

    import keyring
    import logging

    try:
        kr_password = keyring.get_password("vtu-aids", "password")
        if kr_password is not None:
            out["password"] = kr_password
        kr_gemini_key = keyring.get_password("vtu-aids", "gemini_api_key")
        if kr_gemini_key is not None:
            out["gemini_api_key"] = kr_gemini_key
    except Exception as e:
        logging.getLogger(__name__).warning("Keyring read failed: %s", e)

    needs_migration = False
    if data.get("password"):
        try:
            keyring.set_password("vtu-aids", "password", str(data["password"]))
            out["password"] = str(data["password"])
            needs_migration = True
        except Exception as e:
            logging.getLogger(__name__).warning("Keyring write failed for password: %s", e)
    if data.get("gemini_api_key"):
        try:
            clean_key = normalize_api_key(str(data["gemini_api_key"]))
            keyring.set_password("vtu-aids", "gemini_api_key", clean_key)
            out["gemini_api_key"] = clean_key
            needs_migration = True
        except Exception as e:
            logging.getLogger(__name__).warning("Keyring write failed for gemini_api_key: %s", e)

    for key in _OPTIONAL_CONFIG_KEYS:
        if key in data:
            out[key] = data[key]

    if needs_migration:
        try:
            _save_config_json(out, p)
        except Exception:
            pass

    return out


def _save_config_json(current: dict[str, Any], p: Path) -> None:
    data_to_save = dict(current)
    data_to_save.pop("password", None)
    data_to_save.pop("gemini_api_key", None)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data_to_save, f, indent=2, ensure_ascii=False)
    tmp.replace(p)


def missing_setup_fields(cfg: dict[str, Any]) -> list[str]:
    """Field names still required for first-run setup."""
    missing: list[str] = []
    if not str(cfg.get("username", "")).strip():
        missing.append("username")
    if not str(cfg.get("password", "")).strip():
        missing.append("password")
    key = normalize_api_key(str(cfg.get("gemini_api_key", "")))
    if not key:
        key = normalize_api_key(os.environ.get("GEMINI_API_KEY", ""))
    if not key:
        missing.append("gemini_api_key")
    return missing


def config_setup_status(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg if cfg is not None else load_config()
    missing = missing_setup_fields(cfg)
    p = config_path()
    return {
        "setup_required": bool(missing),
        "setup_complete": not missing,
        "missing": missing,
        "has_config_file": p.is_file(),
    }


def is_setup_required() -> bool:
    return config_setup_status()["setup_required"]


def save_config(data: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    p = path or config_path()
    current = load_config(p)
    for key in DEFAULT_CONFIG:
        if key in data:
            val = data[key]
            if key == "gemini_api_key":
                val = normalize_api_key(str(val))
            current[key] = val
    for key in _OPTIONAL_CONFIG_KEYS:
        if key in data:
            current[key] = data[key]

    import keyring
    import logging

    if "password" in data:
        try:
            keyring.set_password("vtu-aids", "password", str(data["password"]))
        except Exception as e:
            logging.getLogger(__name__).warning("Keyring write failed for password: %s", e)
    if "gemini_api_key" in data:
        try:
            keyring.set_password("vtu-aids", "gemini_api_key", normalize_api_key(str(data["gemini_api_key"])))
        except Exception as e:
            logging.getLogger(__name__).warning("Keyring write failed for gemini_api_key: %s", e)

    _save_config_json(current, p)
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
        "internship_start_date": cfg.get("internship_start_date", ""),
        "internship_end_date": cfg.get("internship_end_date", ""),
        "internship_total_days": cfg.get("internship_total_days", 0),
    }


def config_with_secrets(path: Path | None = None) -> dict[str, Any]:
    return load_config(path)


def complete_setup(
    *,
    username: str,
    password: str,
    gemini_api_key: str,
    gemini_model: str,
    default_internship: str = "",
    default_description_words: int = 80,
    internship_start_date: str = "",
    internship_end_date: str = "",
    internship_total_days: int = 0,
) -> dict[str, Any]:
    """Validate and save required credentials after first-run wizard."""
    username = username.strip()
    password = password.strip()
    key = normalize_api_key(gemini_api_key)
    if not username:
        raise ValueError("Enter your VTU Internyet username or email.")
    if not password:
        raise ValueError("Enter your VTU Internyet password.")
    validate_api_key_format(key)
    saved = save_config(
        {
            "username": username,
            "password": password,
            "gemini_api_key": key,
            "gemini_model": gemini_model.strip() or DEFAULT_CONFIG["gemini_model"],
            "default_internship": default_internship.strip(),
            "default_description_words": default_description_words,
            "internship_start_date": internship_start_date.strip(),
            "internship_end_date": internship_end_date.strip(),
            "internship_total_days": max(0, int(internship_total_days or 0)),
            "setup_completed_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    return saved
