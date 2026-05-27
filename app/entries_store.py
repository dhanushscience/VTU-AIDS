"""Persist generated diary entries JSON."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.paths import entries_excel_path, entries_json_path, submitted_entries_json_path, writable_root

PROJECT_ROOT = writable_root


def load_entries() -> list[dict[str, Any]]:
    path = entries_json_path()
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig") as f:
        data = json.load(f)
    if isinstance(data, dict) and "entries" in data:
        items = data["entries"]
    elif isinstance(data, list):
        items = data
    else:
        return []
    return items if isinstance(items, list) else []


def save_entries(entries: list[dict[str, Any]]) -> None:
    path = entries_json_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"entries": entries}
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())


def load_submitted_entries() -> list[dict[str, Any]]:
    path = submitted_entries_json_path()
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig") as f:
        data = json.load(f)
    if isinstance(data, dict) and "entries" in data:
        items = data["entries"]
    elif isinstance(data, list):
        items = data
    else:
        return []
    return items if isinstance(items, list) else []


def save_submitted_entries(entries: list[dict[str, Any]]) -> None:
    path = submitted_entries_json_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"entries": entries}
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())



def normalize_entry_date(date_val: Any) -> str:
    return str(date_val or "").strip()[:10]


def delete_entry_by_date(date: str) -> list[dict[str, Any]]:
    """Remove one entry by date (YYYY-MM-DD). Returns remaining entries."""
    target = normalize_entry_date(date)
    if len(target) < 10:
        raise ValueError("Invalid date.")
    entries = load_entries()
    remaining = [e for e in entries if normalize_entry_date(e.get("date")) != target]
    if len(remaining) == len(entries):
        raise ValueError(f"No entry found for {target}.")
    return remaining


def remove_submitted_entry_by_date(date: str) -> None:
    """Remove a submitted entry by date, saving the remaining."""
    target = normalize_entry_date(date)
    if len(target) < 10:
        return
    entries = load_submitted_entries()
    remaining = [e for e in entries if normalize_entry_date(e.get("date") or e.get("Date")) != target]
    if len(remaining) != len(entries):
        save_submitted_entries(remaining)
