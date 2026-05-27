"""
VTU AIDS - bulk upload internship diary entries to the VTU Internyet portal (JSON or Excel).

JSON (generated/entries.json): wrapper {"entries": [...]} or top-level array.
Friendly keys: date, internship, description, hoursWorked, learningOutcomes, skillsUsed.
Excel sheet "Entries": Date, Internship, WorkSummary, HoursWorked, LearningOutcomes, SkillsUsed.
Optional: referenceLinks / ReferenceLinks, blockersRisks / BlockersRisks.
"""

from __future__ import annotations

import argparse
import getpass
import datetime
import json
import logging
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import pandas as pd
from playwright.sync_api import Browser, BrowserContext, Error as PlaywrightError
from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

LOGIN_URL = "https://vtu.internyet.in/sign-in"
DIARY_ENTRIES_URL = "https://vtu.internyet.in/dashboard/student/diary-entries"

REQUIRED_COLUMNS = (
    "Date",
    "Internship",
    "WorkSummary",
    "HoursWorked",
    "LearningOutcomes",
    "SkillsUsed",
)
OPTIONAL_COLUMNS = ("ReferenceLinks", "BlockersRisks")

# Friendly JSON keys -> internal column names (first match wins per field).
JSON_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "Date": ("date", "Date"),
    "Internship": ("internship", "Internship"),
    "WorkSummary": ("description", "workSummary", "WorkSummary"),
    "HoursWorked": ("hoursWorked", "HoursWorked"),
    "LearningOutcomes": ("learningOutcomes", "LearningOutcomes"),
    "SkillsUsed": ("skillsUsed", "SkillsUsed", "skillUsed", "SkillUsed"),
    "ReferenceLinks": ("referenceLinks", "ReferenceLinks"),
    "BlockersRisks": ("blockersRisks", "BlockersRisks"),
}

LOGGER = logging.getLogger("vtu_aids")
MONTH_NAMES = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]
DEFAULT_DATE_TIMEOUT_MS = 20000
DEFAULT_CONTINUE_TIMEOUT_MS = 15000


def _normalize_date_iso(value: Any) -> str:
    """Return YYYY-MM-DD string for pandas Timestamp, datetime, or string."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        raise ValueError("empty date cell")
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    s = str(value).strip()
    if not s:
        raise ValueError("empty date string")

    # If it's already YYYY-MM-DD, parse exactly to avoid dayfirst=True swapping month/day
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s[:10]):
        try:
            return datetime.datetime.strptime(s[:10], "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            pass

    ts = pd.to_datetime(s, errors="coerce", dayfirst=True)
    if pd.isna(ts):
        raise ValueError(f"unparsable date: {s!r}")
    return ts.strftime("%Y-%m-%d")


def read_excel(path: Path, sheet: str = "Entries") -> list[dict[str, Any]]:
    try:
        df = pd.read_excel(path, sheet_name=sheet, dtype=object)
    except ValueError:
        LOGGER.warning("Sheet '%s' not found, falling back to the first available sheet.", sheet)
        df = pd.read_excel(path, sheet_name=0, dtype=object)
    
    # Normalize column names: remove spaces, fix singulars
    df.columns = [str(c).strip().replace(" ", "") for c in df.columns]
    if "SkillUsed" in df.columns and "SkillsUsed" not in df.columns:
        df.rename(columns={"SkillUsed": "SkillsUsed"}, inplace=True)
    if "LearningOutcomes" not in df.columns:
        LOGGER.warning("LearningOutcomes column missing, filling with default text.")
        df["LearningOutcomes"] = "Learned and applied relevant skills."
        
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns {missing}; found {list(df.columns)}")

    rows: list[dict[str, Any]] = []
    for idx, raw in df.iterrows():
        row_no = int(idx) + 2  # 1-based header + pandas 0-index
        if raw.isna().all():
            continue
        skip = True
        for c in REQUIRED_COLUMNS:
            if c in raw and not (raw[c] is None or (isinstance(raw[c], float) and pd.isna(raw[c]))):
                skip = False
                break
        if skip:
            continue
        row: dict[str, Any] = {}
        row["_row_no"] = row_no
        try:
            row["Date"] = _normalize_date_iso(raw["Date"])
        except ValueError as e:
            raise ValueError(f"Row {row_no}: {e}") from e
        for col in REQUIRED_COLUMNS[1:]:  # rest as strings stripped
            v = raw[col]
            if v is None or (isinstance(v, float) and pd.isna(v)):
                raise ValueError(f"Row {row_no}: missing {col}")
            row[col] = str(v).strip()
            if col != "SkillsUsed" and row[col] == "":
                raise ValueError(f"Row {row_no}: empty {col}")
        skills = str(raw["SkillsUsed"]).strip()
        if not skills or skills.lower() == "nan":
            raise ValueError(f"Row {row_no}: empty SkillsUsed")
        row["SkillsUsed"] = skills
        for col in OPTIONAL_COLUMNS:
            if col in df.columns:
                v = raw[col]
                row[col] = (
                    ""
                    if v is None or (isinstance(v, float) and pd.isna(v))
                    else str(v).strip()
                )
            else:
                row[col] = ""
        rows.append(row)
    if not rows:
        raise ValueError("No data rows found (after skipping empty rows).")
    return rows


def _pick_json_field(raw: dict[str, Any], internal: str) -> Any:
    for key in JSON_FIELD_ALIASES.get(internal, (internal,)):
        if key in raw:
            return raw[key]
    return None


def _normalize_json_row(raw: dict[str, Any], row_no: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"Entry {row_no}: expected object, got {type(raw).__name__}")
    row: dict[str, Any] = {"_row_no": row_no}
    try:
        date_val = _pick_json_field(raw, "Date")
        row["Date"] = _normalize_date_iso(date_val)
    except ValueError as e:
        raise ValueError(f"Entry {row_no}: {e}") from e
    for col in REQUIRED_COLUMNS[1:]:
        v = _pick_json_field(raw, col)
        if v is None:
            if col == "LearningOutcomes":
                row[col] = "Learned and applied relevant skills."
                continue
            raise ValueError(f"Entry {row_no}: missing {col}")
        row[col] = str(v).strip()
        if col != "SkillsUsed" and row[col] == "":
            raise ValueError(f"Entry {row_no}: empty {col}")
    skills = row["SkillsUsed"]
    if not skills or skills.lower() == "nan":
        raise ValueError(f"Entry {row_no}: empty SkillsUsed")
    for col in OPTIONAL_COLUMNS:
        v = _pick_json_field(raw, col)
        row[col] = "" if v is None else str(v).strip()
    return row


def read_json(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "entries" in data:
        items = data["entries"]
    elif isinstance(data, list):
        items = data
    else:
        raise ValueError('JSON must be {"entries": [...]} or a top-level array.')
    if not isinstance(items, list):
        raise ValueError('"entries" must be an array.')
    rows: list[dict[str, Any]] = []
    for idx, raw in enumerate(items):
        row_no = idx + 1
        if raw is None:
            continue
        if isinstance(raw, dict) and not any(
            _pick_json_field(raw, c) is not None for c in REQUIRED_COLUMNS
        ):
            continue
        rows.append(_normalize_json_row(raw, row_no))
    if not rows:
        raise ValueError("No data entries found in JSON.")
    return rows


def load_entries(path: Path, sheet: str = "Entries") -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return read_json(path)
    if suffix in (".xlsx", ".xls"):
        return read_excel(path, sheet=sheet)
    raise ValueError(f"Unsupported entries file type: {path}")


def load_config_credentials(config_path: Path) -> tuple[str, str]:
    with config_path.open(encoding="utf-8") as f:
        data = json.load(f)
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", "")).strip()
    if not username or not password:
        raise ValueError(f"Config {config_path} must include non-empty username and password.")
    return username, password


def fill_first_matching_textbox(page: Page, value: str) -> None:
    for name_pattern in (
        re.compile(r"email", re.I),
        re.compile(r"user\s*name|username|usn|student", re.I),
    ):
        try:
            loc = page.get_by_role("textbox", name=name_pattern)
            loc.first.fill(value, timeout=3000)
            return
        except PlaywrightTimeoutError:
            continue
    # Fallback: first visible textbox
    tb = page.locator('input:not([type="hidden"]):not([type="password"])').first
    tb.wait_for(state="visible", timeout=15000)
    tb.fill(value)


def fill_password_field(page: Page, password: str) -> None:
    try:
        page.get_by_label(re.compile(r"password", re.I)).first.fill(password, timeout=5000)
        return
    except PlaywrightTimeoutError:
        pass
    page.locator('input[type="password"]').first.wait_for(state="visible", timeout=15000)
    page.locator('input[type="password"]').first.fill(password)


def click_login_submit(page: Page) -> None:
    for pattern in (
        re.compile(r"^\s*log\s*in\s*$", re.I),
        re.compile(r"sign\s*in", re.I),
        re.compile(r"submit", re.I),
    ):
        try:
            b = page.get_by_role("button", name=pattern).first
            if b.count():
                b.click(timeout=3000)
                return
        except PlaywrightTimeoutError:
            continue
    page.locator('button[type="submit"]').first.click(timeout=15000)


def login(page: Page, username: str, password: str, timeout_ms: int) -> None:
    page.goto(LOGIN_URL, wait_until="domcontentloaded")
    fill_first_matching_textbox(page, username)
    fill_password_field(page, password)
    click_login_submit(page)
    deadline = time.time() + (timeout_ms / 1000)
    while time.time() < deadline:
        if "/dashboard" in page.url:
            LOGGER.info("Login appears successful (reached /dashboard).")
            return
        # SPA login can render dashboard without hard navigation.
        try:
            if create_entry_button(page).first.is_visible(timeout=500):
                LOGGER.info("Login appears successful (Create button visible).")
                return
        except PlaywrightError:
            pass
        page.wait_for_timeout(400)
    raise PlaywrightTimeoutError(f"Login did not reach dashboard within {timeout_ms} ms.")


def close_overlays(page: Page) -> None:
    """Dismiss cookie banners / modals if a generic accept exists."""
    for name in ("Accept", "Accept all", "I agree", "OK", "Close"):
        try:
            btn = page.get_by_role("button", name=re.compile("^" + re.escape(name) + "$", re.I))
            if btn.count():
                btn.first.click(timeout=2000)
        except PlaywrightError:
            pass


def create_entry_button(page: Page) -> Locator:
    return page.get_by_role("button", name=re.compile(r"^Create$", re.I)).or_(
        page.get_by_role("link", name=re.compile(r"^Create$", re.I))
    )


def goto_diary_entries(page: Page, timeout_ms: int) -> None:
    page.goto(DIARY_ENTRIES_URL, wait_until="domcontentloaded", timeout=timeout_ms)
    try:
        notice = page.get_by_text("Important Notice")
        if notice.is_visible(timeout=3000):
            page.get_by_role("button", name=re.compile(r"I Understand", re.I)).first.click()
    except Exception:
        pass
    create_entry_button(page).first.wait_for(state="visible", timeout=timeout_ms)
    close_overlays(page)


def goto_diary_entries_soft(page: Page, timeout_ms: int) -> None:
    """Navigate to the diary list without blocking on the Create button (post-save recovery)."""
    page.goto(DIARY_ENTRIES_URL, wait_until="domcontentloaded", timeout=timeout_ms)
    try:
        notice = page.get_by_text("Important Notice")
        if notice.is_visible(timeout=2000):
            page.get_by_role("button", name=re.compile(r"I Understand", re.I)).first.click()
    except Exception:
        pass
    close_overlays(page)


def click_named_button(page: Page, name: str, exact: bool = False, timeout_ms: int = 20000) -> None:
    page.get_by_role("button", name=name if exact else re.compile(name, re.I)).first.click(
        timeout=timeout_ms
    )


def append_ack_event(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def safe_scroll_into_view(locator: Locator, timeout_ms: int) -> None:
    """Scroll locator into view safely, swallowing errors like detached DOM elements."""
    try:
        locator.scroll_into_view_if_needed(timeout=timeout_ms)
    except Exception:
        pass


def _fill_locator_replace(locator: Locator, text: str, timeout_ms: int) -> None:
    safe_scroll_into_view(locator, min(timeout_ms, 3000))
    locator.click(timeout=min(timeout_ms, 4000))
    try:
        locator.press("Control+A", timeout=2000)
    except PlaywrightError:
        pass
    locator.fill(text, timeout=timeout_ms)


def _find_active_calendar(page: Page, timeout_ms: int) -> Locator:
    candidates = (
        page.locator("div[data-slot='popover-content'][role='dialog']:visible"),
        page.locator(".rdp-root:visible"),
        page.locator("div[data-slot='calendar']:visible"),
        page.locator("[role='dialog']:visible"),
        page.locator(".rdp:visible"),
        page.locator(".popover-content:visible"),
    )
    for candidate in candidates:
        if candidate.count() > 0:
            calendar = candidate.first
            calendar.wait_for(state="visible", timeout=min(timeout_ms, 5000))
            return calendar
    raise RuntimeError("Date picker opened, but active calendar container was not found.")


def _get_diary_date_trigger(page: Page) -> Locator:
    # Strongly prefer the field with explicit Diary Date label.
    label_based = page.get_by_label(re.compile(r"diary\s*date", re.I))
    if label_based.count() > 0:
        return label_based.first
    # Fallback to the visible date trigger text/icon in step 1 card.
    return (
        page.get_by_role("button").filter(has_text=re.compile(r"Pick a Date|Diary Date", re.I))
        .or_(page.locator("button:has(svg.lucide-calendar)"))
    ).first


def _read_month_year_from_text(text: str) -> tuple[int, int] | None:
    month_pattern = "|".join(MONTH_NAMES + [m[:3] for m in MONTH_NAMES])
    matches = list(re.finditer(rf"\b({month_pattern})\b[\s,\n]+(\d{{4}})", text, re.I))
    if not matches:
        return None
    # Use the last match: in this picker, header month/year appears after month list text.
    match = matches[-1]
    month_name = match.group(1)
    month_idx = None
    for i, full in enumerate(MONTH_NAMES, start=1):
        if month_name.lower() in (full.lower(), full[:3].lower()):
            month_idx = i
            break
    if month_idx is None:
        return None
    return month_idx, int(match.group(2))


def _try_direct_date_input(page: Page, iso_date: str, timeout_ms: int) -> bool:
    # Restrict direct-input optimization to fields clearly tied to "Diary Date"
    # so we don't accidentally mutate unrelated date controls.
    candidates = (
        page.get_by_label(re.compile(r"diary\s*date", re.I)),
        page.locator("input[name*='diary' i][name*='date' i]"),
        page.locator("input[id*='diary' i][id*='date' i]"),
    )
    for cand in candidates:
        if cand.count() == 0:
            continue
        inp = cand.first
        try:
            if not inp.is_visible():
                continue
            before = inp.input_value(timeout=500).strip()
            inp.fill(iso_date, timeout=min(timeout_ms, 1200))
            inp.press("Tab")
            after = inp.input_value(timeout=700).strip()
            if after and after != before and (iso_date in after or after == iso_date):
                return True
        except PlaywrightError:
            continue
    return False


def _parse_date_from_text(text: str, *, target_iso: str | None = None) -> str | None:
    """Parse a date string into YYYY-MM-DD.

    When *target_iso* is supplied (the date we expect), ambiguous numeric
    formats like ``05/11/2026`` are resolved by checking which interpretation
    (DD/MM vs MM/DD) matches the target, preventing month-day swaps.
    """
    if not text:
        return None
    cleaned = " ".join(text.strip().split())

    # 1. ISO is unambiguous - try first.
    if re.match(r"^\d{4}-\d{2}-\d{2}$", cleaned[:10]):
        try:
            return datetime.datetime.strptime(cleaned[:10], "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            pass

    # 2. Named-month formats are unambiguous - try before any numeric slash/dash format.
    for fmt in (
        "%b %d, %Y",
        "%B %d, %Y",
        "%d %b %Y",
        "%d %B %Y",
        "%B %d %Y",
        "%b %d %Y",
    ):
        try:
            dt = datetime.datetime.strptime(cleaned, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    # 3. Numeric slash/dash formats - ambiguous.  When a target is known,
    #    pick the interpretation that matches the target's month and day.
    numeric_fmts = (
        ("%d-%m-%Y", "%m-%d-%Y"),
        ("%d/%m/%Y", "%m/%d/%Y"),
    )
    for dmy, mdy in numeric_fmts:
        parsed_dmy: datetime.datetime | None = None
        parsed_mdy: datetime.datetime | None = None
        try:
            parsed_dmy = datetime.datetime.strptime(cleaned, dmy)
        except ValueError:
            pass
        try:
            parsed_mdy = datetime.datetime.strptime(cleaned, mdy)
        except ValueError:
            pass

        if target_iso and (parsed_dmy or parsed_mdy):
            try:
                target_dt = datetime.datetime.strptime(target_iso, "%Y-%m-%d")
            except ValueError:
                target_dt = None
            if target_dt:
                if parsed_dmy and parsed_dmy.date() == target_dt.date():
                    return parsed_dmy.strftime("%Y-%m-%d")
                if parsed_mdy and parsed_mdy.date() == target_dt.date():
                    return parsed_mdy.strftime("%Y-%m-%d")

        # No target or neither interpretation matched - pick whichever succeeded.
        # Prefer MM/DD (the portal's React date-fns default) over DD/MM.
        if parsed_mdy:
            return parsed_mdy.strftime("%Y-%m-%d")
        if parsed_dmy:
            return parsed_dmy.strftime("%Y-%m-%d")

    ts = pd.to_datetime(cleaned, errors="coerce", dayfirst=False)
    if pd.isna(ts):
        return None
    return ts.strftime("%Y-%m-%d")


def get_current_diary_date_value(page: Page, *, target_iso: str | None = None) -> str | None:
    """Read the diary-date value currently shown in the UI.

    *target_iso* is the date we expect; it helps resolve ambiguous
    numeric formats like ``05/11/2026`` (May 11 vs Nov 5).
    """
    # Prefer true input value, then fallback to trigger text if the control is button-backed.
    candidates = (
        page.get_by_label(re.compile(r"diary\s*date", re.I)),
        page.locator("input[name*='diary' i][name*='date' i]"),
        page.locator("input[id*='diary' i][id*='date' i]"),
    )
    for loc in candidates:
        if loc.count() == 0:
            continue
        inp = loc.first
        try:
            if inp.is_visible():
                value = inp.input_value(timeout=500).strip()
                parsed = _parse_date_from_text(value, target_iso=target_iso)
                if parsed:
                    return parsed
        except PlaywrightError:
            continue

    # Button text fallback for custom date pickers.
    trigger = _get_diary_date_trigger(page)
    try:
        if trigger.count() > 0 and trigger.is_visible():
            return _parse_date_from_text(trigger.inner_text(timeout=600), target_iso=target_iso)
    except PlaywrightError:
        pass
    return None


def _try_select_month_year_dropdowns(calendar: Locator, dt: datetime.datetime) -> bool:
    month_name = dt.strftime("%B")
    year_str = str(dt.year)
    month_selects = calendar.locator("select.rdp-months_dropdown")
    year_selects = calendar.locator("select.rdp-years_dropdown")
    selects = calendar.locator("select")

    # Prefer explicit month/year dropdown classes from react-day-picker.
    if month_selects.count() > 0 or year_selects.count() > 0:
        changed = False
        if month_selects.count() > 0:
            for month_value in (str(dt.month - 1), str(dt.month), month_name, dt.strftime("%b")):
                try:
                    month_selects.first.select_option(value=month_value)
                    changed = True
                    break
                except PlaywrightError:
                    try:
                        month_selects.first.select_option(label=month_value)
                        changed = True
                        break
                    except PlaywrightError:
                        continue
        if year_selects.count() > 0:
            try:
                year_selects.first.select_option(value=year_str)
                changed = True
            except PlaywrightError:
                try:
                    year_selects.first.select_option(label=year_str)
                    changed = True
                except PlaywrightError:
                    pass
        if changed:
            return True

    if selects.count() == 0:
        return False

    if selects.count() >= 2:
        changed = False
        month_sel = selects.first
        year_sel = selects.nth(1)
        try:
            month_sel.select_option(label=month_name)
            changed = True
        except PlaywrightError:
            pass
        try:
            year_sel.select_option(label=year_str)
            changed = True
        except PlaywrightError:
            pass
        return changed

    month_sel: Locator | None = None
    year_sel: Locator | None = None
    for i in range(selects.count()):
        sel = selects.nth(i)
        options_text = " ".join([t.strip() for t in sel.locator("option").all_inner_texts()])
        if month_sel is None and any(m in options_text for m in MONTH_NAMES):
            month_sel = sel
        if year_sel is None and re.search(r"\b20\d{2}\b", options_text):
            year_sel = sel

    changed = False
    if month_sel is not None:
        try:
            month_sel.select_option(label=month_name)
            changed = True
        except PlaywrightError:
            pass
    if year_sel is not None:
        try:
            year_sel.select_option(label=year_str)
            changed = True
        except PlaywrightError:
            pass
    return changed


def _try_select_month_year_buttons(page: Page, calendar: Locator, dt: datetime.datetime, timeout_ms: int) -> bool:
    month_name = dt.strftime("%B")
    month_short = dt.strftime("%b")
    year_str = str(dt.year)
    month_regex = re.compile(
        r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|January|February|March|April|May|June|July|August|September|October|November|December)$",
        re.I,
    )
    year_regex = re.compile(r"^20\d{2}$")

    month_btn: Locator | None = None
    year_btn: Locator | None = None
    buttons = calendar.locator("button")
    for i in range(buttons.count()):
        btn = buttons.nth(i)
        try:
            if not btn.is_visible():
                continue
            txt = btn.inner_text(timeout=500).strip()
            if month_btn is None and month_regex.match(txt):
                month_btn = btn
            if year_btn is None and year_regex.match(txt):
                year_btn = btn
        except PlaywrightError:
            continue

    changed = False
    if month_btn is not None:
        try:
            month_btn.click(timeout=min(timeout_ms, 2000))
            month_opt = page_or_calendar_option(page, calendar, month_name, month_short)
            if month_opt is not None:
                month_opt.click(timeout=min(timeout_ms, 2000))
                changed = True
        except PlaywrightError:
            pass

    if year_btn is not None:
        try:
            year_btn.click(timeout=min(timeout_ms, 2000))
            year_opt = page_or_calendar_option(page, calendar, year_str, year_str)
            if year_opt is not None:
                year_opt.click(timeout=min(timeout_ms, 2000))
                changed = True
        except PlaywrightError:
            pass
    return changed


def page_or_calendar_option(page: Page, calendar: Locator, primary: str, fallback: str) -> Locator | None:
    for scope in (page, calendar):
        try:
            opt = scope.get_by_role("option", name=re.compile(rf"^{re.escape(primary)}$", re.I)).first
            if opt.count() > 0 and opt.is_visible():
                return opt
            opt = scope.get_by_role("option", name=re.compile(rf"^{re.escape(fallback)}$", re.I)).first
            if opt.count() > 0 and opt.is_visible():
                return opt
            txt = scope.get_by_text(re.compile(rf"^{re.escape(primary)}$", re.I)).first
            if txt.count() > 0 and txt.is_visible():
                return txt
            txt = scope.get_by_text(re.compile(rf"^{re.escape(fallback)}$", re.I)).first
            if txt.count() > 0 and txt.is_visible():
                return txt
        except PlaywrightError:
            continue
    return None


def _calendar_header_matches(calendar: Locator, month_name: str, year_str: str) -> bool:
    try:
        text = calendar.inner_text(timeout=1200)
    except PlaywrightError:
        return False
    return re.search(rf"\b{re.escape(month_name)}\s+{re.escape(year_str)}\b", text, re.I) is not None


def _trigger_shows_pick_a_date(page: Page) -> bool:
    try:
        text = _get_diary_date_trigger(page).inner_text(timeout=800)
        return bool(re.search(r"pick\s*a\s*date", text, re.I))
    except PlaywrightError:
        return True


def _wait_for_diary_date_committed(page: Page, iso_date: str, timeout_ms: int) -> bool:
    """Wait until shadcn trigger leaves placeholder and shows a real date."""
    deadline = time.perf_counter() + (timeout_ms / 1000.0)
    while time.perf_counter() < deadline:
        if not _trigger_shows_pick_a_date(page):
            observed = get_current_diary_date_value(page, target_iso=iso_date)
            if observed == iso_date:
                return True
            # Accept parseable date containing target day/month/year even if format differs.
            if observed:
                try:
                    obs_dt = datetime.datetime.strptime(observed, "%Y-%m-%d")
                    tgt_dt = datetime.datetime.strptime(iso_date, "%Y-%m-%d")
                    if obs_dt.date() == tgt_dt.date():
                        return True
                except ValueError:
                    pass
        page.wait_for_timeout(150)
    return False


def _navigate_calendar_to_month(
    page: Page, calendar: Locator, dt: datetime.datetime, date_timeout_ms: int
) -> None:
    month_name = dt.strftime("%B")
    year_str = str(dt.year)

    if _try_select_month_year_dropdowns(calendar, dt):
        page.wait_for_timeout(200)
    if not _try_select_month_year_buttons(page, calendar, dt, date_timeout_ms):
        pass
    page.wait_for_timeout(200)

    if _calendar_header_matches(calendar, month_name, year_str):
        return

    current = _read_month_year_from_text(calendar.inner_text())
    if not current:
        return

    cur_month, cur_year = current
    target_delta = (dt.year - cur_year) * 12 + (dt.month - cur_month)
    if target_delta == 0:
        return

    if target_delta > 0:
        nav = calendar.get_by_role("button", name=re.compile(r"Go to the Next Month", re.I)).first
    else:
        nav = calendar.get_by_role("button", name=re.compile(r"Go to the Previous Month", re.I)).first

    steps = min(abs(target_delta), 24)
    for _ in range(steps):
        if _calendar_header_matches(calendar, month_name, year_str):
            return
        try:
            if not nav.is_enabled():
                break
            nav.click(timeout=min(date_timeout_ms, 2500))
            page.wait_for_timeout(120)
        except PlaywrightError:
            break

    if not _calendar_header_matches(calendar, month_name, year_str):
        raise RuntimeError(f"Calendar did not reach {month_name} {year_str}.")


def _find_day_button(calendar: Locator, dt: datetime.datetime, iso_date: str) -> Locator:
    month_name = dt.strftime("%B")
    year_str = str(dt.year)
    day_str = str(dt.day)
    # react-day-picker data-day is locale-dependent:
    #   US (M/D/YYYY): 5/11/2026 for May 11
    #   Non-US (D/M/YYYY): 11/5/2026 for May 11
    data_day_mdy = f"{dt.month}/{dt.day}/{dt.year}"   # M/D/YYYY
    data_day_dmy = f"{dt.day}/{dt.month}/{dt.year}"   # D/M/YYYY

    candidates = (
        # Prefer td[data-day] with ISO format (react-day-picker v9 uses YYYY-MM-DD here).
        calendar.locator(f"td[data-day='{iso_date}']:not([data-outside='true']) button.rdp-day_button"),
        # data-day on the button itself - try both locale variants.
        calendar.locator(f"button.rdp-day_button[data-day='{data_day_mdy}']:not([disabled])"),
        calendar.locator(f"button.rdp-day_button[data-day='{data_day_dmy}']:not([disabled])"),
        # aria-label with month name + day is unambiguous.
        calendar.locator(
            f"button.rdp-day_button[aria-label*='{month_name}'][aria-label*='{day_str}']:not([disabled])"
        ),
        # Text-based: find the visible day number inside a non-outside td.
        calendar.locator("td:not([data-outside='true']) button.rdp-day_button:not([disabled])").filter(
            has_text=re.compile(rf"^{day_str}$")
        ),
        # Full accessible name.
        calendar.get_by_role(
            "button",
            name=re.compile(
                rf"{month_name}.*{day_str}(?:st|nd|rd|th)?.*{year_str}|{day_str}.*{month_name}.*{year_str}",
                re.I,
            ),
        ),
    )
    for cand in candidates:
        if cand.count() > 0:
            btn = cand.first
            try:
                if btn.is_visible():
                    return btn
            except PlaywrightError:
                continue
    raise RuntimeError(f"No selectable day button for {iso_date}.")


def _click_day_and_commit(
    page: Page, calendar: Locator, trig: Locator, dt: datetime.datetime, iso_date: str, date_timeout_ms: int
) -> None:
    day_btn = _find_day_button(calendar, dt, iso_date)
    # Normal click (no force) so react-day-picker onSelect runs and updates the trigger.
    safe_scroll_into_view(day_btn, min(date_timeout_ms, 3000))
    day_btn.click(timeout=date_timeout_ms)

    if _wait_for_diary_date_committed(page, iso_date, min(date_timeout_ms, 5000)):
        return

    # shadcn popover often stays open until click-outside; close without Escape (can cancel).
    try:
        page.get_by_text("Select Internship", exact=False).first.click(timeout=2000)
    except PlaywrightError:
        pass
    if _wait_for_diary_date_committed(page, iso_date, min(date_timeout_ms, 3000)):
        return

    # Keyboard commit while day still focused.
    try:
        day_btn.focus()
        page.keyboard.press("Enter")
    except PlaywrightError:
        pass
    if _wait_for_diary_date_committed(page, iso_date, min(date_timeout_ms, 3000)):
        return

    # Re-open and retry once with explicit month navigation.
    try:
        trig.click(timeout=3000)
        calendar = _find_active_calendar(page, date_timeout_ms)
        _navigate_calendar_to_month(page, calendar, dt, date_timeout_ms)
        day_btn = _find_day_button(calendar, dt, iso_date)
        day_btn.click(timeout=date_timeout_ms)
        page.get_by_text("Select Internship", exact=False).first.click(timeout=2000)
    except PlaywrightError:
        pass

    if not _wait_for_diary_date_committed(page, iso_date, date_timeout_ms):
        observed = get_current_diary_date_value(page, target_iso=iso_date)
        raise RuntimeError(
            f"Diary date not committed to trigger: target={iso_date}, observed={observed or 'Pick a Date'}"
        )


def select_internship_option(page: Page, internship_display: str, timeout_ms: int) -> None:
    """Step 1: open internship picker and choose option text."""
    try:
        if page.get_by_text("Important Notice").is_visible():
            page.get_by_role("button", name=re.compile(r"I Understand", re.I)).first.click()
    except Exception:
        pass

    trig = (
        page.locator("button[role='combobox']").filter(has_text=re.compile("internship", re.I))
        .or_(page.get_by_role("combobox"))
        .or_(page.locator("#internship_id"))
    ).first
    trig.click(timeout=timeout_ms)
    page.wait_for_timeout(1000)
    
    no_options = page.locator("text=No options available")
    if no_options.count() > 0 and no_options.first.is_visible():
        LOGGER.warning("Internship dropdown says 'No options available'. Reloading page...")
        page.reload(wait_until="domcontentloaded", timeout=timeout_ms)
        page.wait_for_timeout(2000)
        
        if "sign-in" in page.url or "login" in page.url:
            raise RuntimeError("Reloading page redirected to sign-in. Session may have expired.")
        
        try:
            if page.get_by_text("Important Notice").is_visible(timeout=2000):
                page.get_by_role("button", name=re.compile(r"I Understand", re.I)).first.click()
        except Exception:
            pass
            
        trig = (
            page.locator("button[role='combobox']").filter(has_text=re.compile("internship", re.I))
            .or_(page.get_by_role("combobox"))
            .or_(page.locator("#internship_id"))
        ).first
        trig.click(timeout=timeout_ms)
        page.wait_for_timeout(1000)
    
    want = internship_display.strip()
    # Use keyboard to filter and select
    page.keyboard.type(want, delay=50)
    page.wait_for_timeout(500)
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    page.wait_for_timeout(300)


def set_diary_date_step1(page: Page, iso_date: str, timeout_ms: int, date_timeout_ms: int) -> None:
    """
    Set diary date for shadcn/react-day-picker UI.

    Strategy (from Playwright + react-day-picker docs):
    - Prefer native month/year dropdowns or caption navigation.
    - Click day via button.rdp-day_button / data-day (normal click, not force).
    - Wait until trigger text leaves 'Pick a Date' (proves onSelect committed).
    """
    if _try_direct_date_input(page, iso_date, timeout_ms):
        if _wait_for_diary_date_committed(page, iso_date, min(date_timeout_ms, 4000)):
            return

    dt = datetime.datetime.strptime(iso_date, "%Y-%m-%d")
    trig = _get_diary_date_trigger(page)
    trig.click(timeout=min(date_timeout_ms, 8000))
    calendar = _find_active_calendar(page, date_timeout_ms)

    _navigate_calendar_to_month(page, calendar, dt, date_timeout_ms)
    _click_day_and_commit(page, calendar, trig, dt, iso_date, date_timeout_ms)


def step1_continue(page: Page, timeout_ms: int, continue_timeout_ms: int) -> None:
    continue_btn = page.get_by_role("button", name=re.compile(r"^\s*Continue\s*$", re.I)).first
    continue_btn.wait_for(state="visible", timeout=continue_timeout_ms)
    safe_scroll_into_view(continue_btn, min(continue_timeout_ms, 5000))

    # Continue stays disabled until diary date is committed in React state.
    enabled_deadline = time.perf_counter() + (continue_timeout_ms / 1000.0)
    while time.perf_counter() < enabled_deadline:
        try:
            if continue_btn.is_enabled():
                break
        except PlaywrightError:
            pass
        page.wait_for_timeout(200)
    else:
        raise RuntimeError(
            "Continue button remained disabled. Diary date may not be committed (trigger still 'Pick a Date')."
        )

    before_url = page.url
    for attempt in range(1, 4):
        try:
            continue_btn.click(timeout=min(continue_timeout_ms, 8000), force=attempt > 1)
        except PlaywrightError:
            # Keyboard fallback
            if attempt >= 2:
                try:
                    continue_btn.focus()
                    page.keyboard.press("Enter")
                except PlaywrightError:
                    pass
            if attempt == 3:
                raise
        page.wait_for_timeout(250)
        step2_fields = (
            page.get_by_label(re.compile(r"work\s*summary", re.I)).first,
            page.get_by_label(re.compile(r"hours\s*worked", re.I)).first,
            page.get_by_role("button", name=re.compile(r"^\s*save\s*$", re.I)).first,
        )
        transitioned = page.url != before_url
        for field in step2_fields:
            try:
                if field.is_visible(timeout=min(continue_timeout_ms, 1000)):
                    transitioned = True
                    break
            except PlaywrightError:
                continue
        if transitioned:
            return
    raise RuntimeError("Continue click did not transition to step 2.")


def _wait_for_step2_form(page: Page, timeout_ms: int) -> None:
    """Wait until internship entry form (step 2) is rendered after Continue."""
    candidates = (
        page.get_by_placeholder(re.compile(r"Briefly describe", re.I)),
        page.get_by_label(re.compile(r"work\s*summary", re.I)),
        page.get_by_label(re.compile(r"hours\s*worked", re.I)),
    )
    deadline = time.perf_counter() + (timeout_ms / 1000.0)
    while time.perf_counter() < deadline:
        for loc in candidates:
            try:
                if loc.count() > 0 and loc.first.is_visible():
                    return
            except PlaywrightError:
                continue
        page.wait_for_timeout(200)
    raise RuntimeError("Step 2 form did not appear after Continue.")


def fill_textarea_by_placeholders(
    page: Page,
    placeholder_regexes: list[str],
    label_regexes: list[str],
    text: str,
    timeout_ms: int,
    *,
    replace_existing: bool = False,
) -> None:
    locators: list[Locator] = []
    for pr in placeholder_regexes:
        locators.append(page.get_by_placeholder(re.compile(pr, re.I)))
    for lr in label_regexes:
        locators.append(page.get_by_label(re.compile(lr, re.I)))

    if not locators:
        raise PlaywrightError("No locators provided")

    last_error: Exception | None = None
    for _ in range(2):
        for loc in locators:
            try:
                if loc.count() == 0:
                    continue
                target = loc.first
                target.wait_for(state="visible", timeout=min(timeout_ms, 3000))
                if replace_existing:
                    _fill_locator_replace(target, text, timeout_ms)
                else:
                    safe_scroll_into_view(target, min(timeout_ms, 3000))
                    target.fill(text, timeout=timeout_ms)
                return
            except Exception as e:
                last_error = e
                continue
    raise PlaywrightError(
        f"Could not find/fill textarea (placeholders={placeholder_regexes!r} labels={label_regexes!r}). Error: {last_error}"
    )


def fill_hours_worked(page: Page, hours_str: str, timeout_ms: int, *, replace_existing: bool = False) -> None:
    loc = page.get_by_label(re.compile(r"hours\s*worked", re.I)).or_(
        page.get_by_placeholder(re.compile(r"6\.5|hours", re.I))
    )
    inp = loc.first
    safe_scroll_into_view(inp, timeout_ms)
    
    # Clean the input to only contain digits and a decimal point (e.g. "8 hrs" -> "8")
    cleaned_hours = re.sub(r"[^\d.]", "", str(hours_str))
    if not cleaned_hours:
        cleaned_hours = "8" # Safe fallback
        
    if replace_existing:
        _fill_locator_replace(inp, cleaned_hours, timeout_ms)
    else:
        inp.fill(cleaned_hours, timeout=timeout_ms)


def clear_skill_tags(page: Page, timeout_ms: int) -> None:
    # Attempt 1: Click the 'Clear all' button if present in React Select
    try:
        clear_btn = page.locator(".css-1xc3v61-indicatorContainer, .clear-indicator, button[aria-label*='Clear']").first
        if clear_btn.is_visible(timeout=500):
            clear_btn.click(timeout=1000)
            page.wait_for_timeout(200)
    except PlaywrightError:
        pass

    # Attempt 2: Repeatedly press Backspace in the input field to delete tags one by one
    try:
        trig = (
            page.get_by_placeholder(re.compile(r"add skills|select", re.I))
            .or_(page.get_by_label(re.compile(r"skills\s*used", re.I)))
            .or_(page.locator("input[id*='react-select']"))
            .or_(page.get_by_role("combobox", name=re.compile(r"skills", re.I)))
        ).first
        
        if trig.is_visible(timeout=1000):
            trig.focus()
            for _ in range(15):
                page.keyboard.press("Backspace")
                page.wait_for_timeout(50)
    except PlaywrightError:
        pass

    # Attempt 3: Click individual remove buttons (fallback)
    for _ in range(10):
        removed = False
        for sel in (
            "button[aria-label*='Remove']",
            "button[aria-label*='remove']",
            "[data-slot='badge'] button",
            "button:has(svg.lucide-x)",
            ".css-xb97g8-multiValueRemove",
        ):
            try:
                loc = page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible(timeout=200):
                    loc.first.click(timeout=1000)
                    page.wait_for_timeout(100)
                    removed = True
                    break
            except PlaywrightError:
                continue
        if not removed:
            break


def add_skills(page: Page, skills_csv: str, timeout_ms: int, *, replace_existing: bool = False) -> None:
    raw = [s.strip() for s in re.split(r"[,;/]", skills_csv) if s.strip()]
    if not raw:
        raise ValueError("No skills parsed from SkillsUsed")

    # Define a helper function to get the latest trigger locator from the DOM
    def get_skills_trigger() -> Locator:
        return (
            page.get_by_placeholder(re.compile(r"add skills|select", re.I))
            .or_(page.get_by_label(re.compile(r"skills\s*used", re.I)))
            .or_(page.locator("input[id*='react-select']"))
            .or_(page.get_by_role("combobox", name=re.compile(r"skills", re.I)))
        ).first

    get_skills_trigger().wait_for(state="visible", timeout=timeout_ms)
    if replace_existing:
        clear_skill_tags(page, timeout_ms)

    for skill in raw:
        # Dynamic re-query ensures we never use a detached DOM element after a React re-render
        trig = get_skills_trigger()
        safe_scroll_into_view(trig, timeout_ms)
        trig.click(timeout=timeout_ms)
        trig.fill(skill)
        page.wait_for_timeout(300)
        # Prefer picking first suggestion
        sug = page.get_by_role("option", name=re.compile(re.escape(skill), re.I)).first
        try:
            sug.wait_for(state="visible", timeout=2000)
            sug.click(timeout=timeout_ms)
        except PlaywrightTimeoutError:
            page.keyboard.press("Enter")
        page.keyboard.press("Escape")
        page.wait_for_timeout(100)


def _row_text_matches_date(text: str, iso_date: str) -> bool:
    if not text:
        return False
    if iso_date in text:
        return True
    try:
        tgt = datetime.datetime.strptime(iso_date, "%Y-%m-%d")
    except ValueError:
        return False
        
    compact = text.replace(",", " ").replace("\n", " ").replace("/", " ").replace("-", " ")
    if str(tgt.year) not in compact:
        return False
        
    month_full = MONTH_NAMES[tgt.month - 1]
    month_short = month_full[:3]
    
    # Check if month is present either as a name or a zero-padded/unpadded number
    month_patterns = [
        rf"\b{re.escape(month_full)}\b",
        rf"\b{re.escape(month_short)}\b",
        rf"\b{tgt.month:02d}\b",
        rf"\b{tgt.month}\b",
    ]
    
    if not any(re.search(p, compact, re.I) for p in month_patterns):
        return False
        
    day_patterns = [
        rf"\b{tgt.day:02d}\b",
        rf"\b{tgt.day}\b",
    ]
    
    return any(re.search(p, compact, re.I) for p in day_patterns)


def _wait_for_diary_list(page: Page, timeout_ms: int) -> None:
    deadline = time.perf_counter() + (timeout_ms / 1000.0)
    while time.perf_counter() < deadline:
        try:
            if create_entry_button(page).first.is_visible(timeout=800):
                return
        except PlaywrightError:
            pass
        try:
            rows = page.locator("table tbody tr")
            if rows.count() > 0 and rows.first.is_visible(timeout=500):
                return
        except PlaywrightError:
            pass
        page.wait_for_timeout(200)
    raise RuntimeError("Diary entries list did not load.")


def _find_portal_entry_row(page: Page, iso_date: str, timeout_ms: int) -> Locator | None:
    """Find a table/list row on the diary page that matches the target date."""
    _wait_for_diary_list(page, timeout_ms)
    candidates: list[Locator] = [
        page.locator("table tbody tr"),
        page.get_by_role("row"),
        page.locator("[data-slot='table-row']"),
    ]
    for rows in candidates:
        try:
            count = rows.count()
        except PlaywrightError:
            continue
        for i in range(count):
            row = rows.nth(i)
            try:
                if not row.is_visible(timeout=400):
                    continue
                text = row.inner_text(timeout=1200)
            except PlaywrightError:
                continue
            if _row_text_matches_date(text, iso_date):
                return row
    return None


def _click_edit_on_row(row: Locator, timeout_ms: int) -> None:
    edit = row.get_by_role("button", name=re.compile(r"^\s*edit\s*$", re.I))
    if edit.count() == 0:
        edit = row.get_by_role("link", name=re.compile(r"edit", re.I))
    if edit.count() == 0:
        edit = row.locator(
            "button:has(svg.lucide-pencil), button:has(svg.lucide-square-pen), a:has(svg.lucide-pencil)"
        )
    if edit.count() == 0:
        buttons = row.locator("button")
        if buttons.count() > 0:
            edit = buttons.last
    if edit.count() == 0:
        raise RuntimeError("Entry row found but no Edit control.")
    safe_scroll_into_view(edit.first, timeout_ms)
    edit.first.click(timeout=timeout_ms)


def _dismiss_blocking_dialogs(page: Page, timeout_ms: int) -> None:
    for name in (
        r"^\s*close\s*$",
        r"^\s*cancel\s*$",
        r"^\s*back\s*$",
        r"^\s*done\s*$",
    ):
        try:
            btn = page.get_by_role("button", name=re.compile(name, re.I))
            if btn.count() > 0 and btn.first.is_visible(timeout=600):
                btn.first.click(timeout=min(timeout_ms, 3000))
                page.wait_for_timeout(250)
        except PlaywrightError:
            continue


def _step2_form_visible(page: Page) -> bool:
    for loc in (
        page.get_by_label(re.compile(r"work\s*summary", re.I)).first,
        page.get_by_placeholder(re.compile(r"Briefly describe", re.I)).first,
        page.get_by_label(re.compile(r"hours\s*worked", re.I)).first,
    ):
        try:
            if loc.is_visible(timeout=300):
                return True
        except PlaywrightError:
            continue
    return False


def _diary_list_visible(page: Page) -> bool:
    if _step2_form_visible(page):
        return False
    try:
        if create_entry_button(page).first.is_visible(timeout=500):
            return True
    except PlaywrightError:
        pass
    try:
        return page.locator("table tbody tr").first.is_visible(timeout=500)
    except PlaywrightError:
        return False


def _try_close_edit_panel_once(page: Page, timeout_ms: int) -> bool:
    closers = [
        page.locator("button[data-slot='dialog-close']"),
        page.get_by_role("button", name=re.compile(r"^\s*close\s*$", re.I)),
        page.get_by_role("button", name=re.compile(r"^\s*done\s*$", re.I)),
        page.locator("[role='dialog'] button:has(svg.lucide-x)"),
        page.locator("[data-slot='sheet-content'] button:has(svg.lucide-x)"),
        page.locator("button:has(svg.lucide-x)"),
    ]
    for loc in closers:
        try:
            for i in range(min(loc.count(), 10)):
                btn = loc.nth(i)
                if not btn.is_visible(timeout=300):
                    continue
                safe_scroll_into_view(btn, min(timeout_ms, 2000))
                btn.click(timeout=min(timeout_ms, 3000))
                page.wait_for_timeout(350)
                return True
        except PlaywrightError:
            continue
    return False


def _dismiss_post_save_feedback(page: Page, timeout_ms: int) -> None:
    """Dismiss success toast or overlay after save/update."""
    for _ in range(3):
        try:
            hint = page.get_by_text(
                re.compile(r"saved|success|updated|submitted", re.I)
            ).first
            if hint.is_visible(timeout=600):
                try:
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(200)
                except PlaywrightError:
                    pass
        except PlaywrightError:
            pass
        _dismiss_blocking_dialogs(page, timeout_ms)
        page.wait_for_timeout(150)


def return_to_diary_list(page: Page, timeout_ms: int) -> None:
    """Close edit modal/sheet after save and return to the entries table."""
    _dismiss_post_save_feedback(page, min(timeout_ms, 3000))

    if _diary_list_visible(page):
        return

    LOGGER.info("Closing entry panel and returning to diary list...")
    deadline = time.perf_counter() + (min(timeout_ms, 8000) / 1000.0)
    while time.perf_counter() < deadline:
        if _diary_list_visible(page):
            LOGGER.info("Diary list is visible again.")
            return
        if _try_close_edit_panel_once(page, timeout_ms):
            page.wait_for_timeout(250)
            continue
        try:
            page.keyboard.press("Escape")
        except PlaywrightError:
            pass
        _dismiss_blocking_dialogs(page, timeout_ms)
        page.wait_for_timeout(200)

    LOGGER.info("Reloading diary list page to continue.")
    goto_diary_entries_soft(page, min(timeout_ms, 12000))
    try:
        _wait_for_diary_list(page, min(timeout_ms, 8000))
    except RuntimeError:
        pass


def _cleanup_playwright_chromium_windows() -> None:
    """Stop headed Chromium orphans left by Playwright on Windows (ms-playwright only)."""
    try:
        from app.process_cleanup import cleanup_playwright_chromium
    except ModuleNotFoundError:
        # Direct script mode: app package may not be importable from cwd.
        from process_cleanup import cleanup_playwright_chromium

    cleanup_playwright_chromium()


def _setup_headed_browser(browser: Browser, context: BrowserContext, page: Page) -> None:
    try:
        from app.browser_display import configure_headed_automation_browser
    except ModuleNotFoundError:
        # Direct script mode: app package may not be importable from cwd.
        from browser_display import configure_headed_automation_browser

    configure_headed_automation_browser(browser, context, page)


def _close_browser_session(
    page: Page | None,
    context: BrowserContext | None,
    browser: Browser | None,
    *,
    headed: bool = False,
) -> None:
    """Close Playwright page, context, and browser (headed windows on Windows)."""
    if headed and browser is not None:
        try:
            try:
                from app.browser_display import release_headed_automation_browser
            except ModuleNotFoundError:
                # Direct script mode: app package may not be importable from cwd.
                from browser_display import release_headed_automation_browser

            release_headed_automation_browser(browser)
        except Exception as e:
            LOGGER.debug("Release headed browser UI: %s", e)
    for label, resource in (("page", page), ("context", context), ("browser", browser)):
        if resource is None:
            continue
        try:
            resource.close()
            LOGGER.info("Closed %s.", label)
        except PlaywrightError as e:
            LOGGER.warning("Could not close %s: %s", label, e)
        except Exception as e:
            LOGGER.warning("Could not close %s: %s", label, e)

    if browser is not None:
        try:
            if hasattr(browser, "is_connected") and browser.is_connected():
                browser.close()
                LOGGER.info("Closed browser (second pass).")
        except PlaywrightError as e:
            LOGGER.warning("Second browser close failed: %s", e)

    if headed:
        time.sleep(0.25)
        _cleanup_playwright_chromium_windows()


def try_open_existing_entry_edit(page: Page, iso_date: str, timeout_ms: int) -> bool:
    """If the portal already has this date, open Edit instead of Create."""
    row = _find_portal_entry_row(page, iso_date, timeout_ms)
    if row is None:
        return False
    LOGGER.info("Portal already has entry for %s - using Edit flow.", iso_date)
    _click_edit_on_row(row, timeout_ms)
    page.wait_for_timeout(400)
    _dismiss_blocking_dialogs(page, timeout_ms)
    return True


def fill_step2_fields(page: Page, row: dict[str, Any], timeout_ms: int, *, replace_existing: bool) -> None:
    _wait_for_step2_form(page, timeout_ms)
    fill_textarea_by_placeholders(
        page,
        placeholder_regexes=[r"Briefly describe", r"work you did today"],
        label_regexes=[r"work\s*summary"],
        text=row["WorkSummary"],
        timeout_ms=timeout_ms,
        replace_existing=replace_existing,
    )
    fill_hours_worked(page, row["HoursWorked"], timeout_ms, replace_existing=replace_existing)
    links = row.get("ReferenceLinks", "")
    blockers = row.get("BlockersRisks", "")
    if links:
        fill_textarea_by_placeholders(
            page,
            placeholder_regexes=[r"Paste one or more", r"relevant links"],
            label_regexes=[r"reference\s*links"],
            text=links,
            timeout_ms=timeout_ms,
            replace_existing=replace_existing,
        )
    fill_textarea_by_placeholders(
        page,
        placeholder_regexes=[r"What did you learn", r"ship today"],
        label_regexes=[r"learnings?\s*/\s*outcomes?"],
        text=row["LearningOutcomes"],
        timeout_ms=timeout_ms,
        replace_existing=replace_existing,
    )
    if blockers:
        fill_textarea_by_placeholders(
            page,
            placeholder_regexes=[r"Anything that slowed", r"slowed you down"],
            label_regexes=[r"blockers?\s*/\s*risks?"],
            text=blockers,
            timeout_ms=timeout_ms,
            replace_existing=replace_existing,
        )
    add_skills(page, row["SkillsUsed"], timeout_ms, replace_existing=replace_existing)


def save_diary_entry_form(
    page: Page,
    row: dict[str, Any],
    timeout_ms: int,
    attempt: int,
    emit_ack,
    row_started: float,
    *,
    from_edit: bool = False,
    is_last_row: bool = False,
) -> None:
    sav = (
        page.get_by_role("button", name=re.compile(r"^\s*save\s*(?:entry|diary)?\s*$", re.I))
        .or_(page.get_by_role("button", name=re.compile(r"^\s*save\s*$", re.I)))
        .or_(page.get_by_role("button", name=re.compile(r"submit", re.I)))
        .or_(page.locator("button[type='submit']"))
        .or_(page.locator("button:has-text('Save')"))
    ).first
    safe_scroll_into_view(sav, timeout_ms)
    emit_ack(row, attempt, "save_clicked", "ok")

    def _finish_row_success(*, reason: str = "") -> None:
        emit_ack(row, attempt, "panel_closed", "ok", reason=reason or None)
        emit_ack(
            row,
            attempt,
            "row_success",
            "ok",
            duration_ms=int((time.perf_counter() - row_started) * 1000),
        )
        LOGGER.info("Row %s: saved successfully.", row["_row_no"])

    if from_edit:
        sav.click(timeout=timeout_ms)
        page.wait_for_timeout(600)
        _dismiss_post_save_feedback(page, min(timeout_ms, 2000))
        if is_last_row:
            LOGGER.info(
                "Last entry saved via edit for %s - no further rows; closing browser.",
                row["Date"],
            )
            _try_close_edit_panel_once(page, min(timeout_ms, 3000))
            _finish_row_success(reason="last_row_edit_exit")
            return
        return_to_diary_list(page, min(timeout_ms, 12000))
    else:
        try:
            with page.expect_navigation(timeout=min(timeout_ms, 15000)):
                sav.click(timeout=timeout_ms)
        except PlaywrightTimeoutError:
            sav.click(timeout=timeout_ms)
        page.wait_for_timeout(500)
        _dismiss_post_save_feedback(page, min(timeout_ms, 2000))
        if is_last_row:
            LOGGER.info(
                "Last entry saved for %s - no further rows; closing browser.",
                row["Date"],
            )
            _finish_row_success(reason="last_row_create_exit")
            return
        return_to_diary_list(page, min(timeout_ms, 12000))

    if not _diary_list_visible(page):
        goto_diary_entries(page, min(timeout_ms, 15000))
        try:
            _wait_for_diary_list(page, min(timeout_ms, 10000))
        except RuntimeError:
            LOGGER.warning("Diary list not confirmed after save; continuing anyway.")

    _finish_row_success()


def run_create_new_entry_flow(
    page: Page,
    row: dict[str, Any],
    timeout_ms: int,
    date_timeout_ms: int,
    continue_timeout_ms: int,
    attempt: int,
    emit_ack,
    row_started: float,
    *,
    is_last_row: bool = False,
) -> None:
    create_entry_button(page).first.click(timeout=timeout_ms)
    select_internship_option(page, row["Internship"], timeout_ms)

    t0 = row_started
    try:
        set_diary_date_step1(page, row["Date"], timeout_ms, date_timeout_ms)
    except Exception:
        _dismiss_blocking_dialogs(page, timeout_ms)
        goto_diary_entries(page, timeout_ms)
        if try_open_existing_entry_edit(page, row["Date"], timeout_ms):
            emit_ack(row, attempt, "mode", "ok", reason="edit_after_create_date_fail")
            fill_step2_fields(page, row, timeout_ms, replace_existing=True)
            save_diary_entry_form(
                page,
                row,
                timeout_ms,
                attempt,
                emit_ack,
                t0,
                from_edit=True,
                is_last_row=is_last_row,
            )
            return
        raise

    emit_ack(row, attempt, "date_selected", "ok", duration_ms=int((time.perf_counter() - t0) * 1000))
    observed = get_current_diary_date_value(page, target_iso=row["Date"])
    if observed != row["Date"] and _trigger_shows_pick_a_date(page):
        _dismiss_blocking_dialogs(page, timeout_ms)
        goto_diary_entries(page, timeout_ms)
        if try_open_existing_entry_edit(page, row["Date"], timeout_ms):
            emit_ack(row, attempt, "mode", "ok", reason="edit_existing_date_blocked")
            fill_step2_fields(page, row, timeout_ms, replace_existing=True)
            save_diary_entry_form(
                page,
                row,
                timeout_ms,
                attempt,
                emit_ack,
                t0,
                from_edit=True,
                is_last_row=is_last_row,
            )
            return
        raise RuntimeError(
            f"Diary date mismatch before Continue: target={row['Date']} observed={observed}"
        )
    emit_ack(row, attempt, "date_verified", "ok", reason=f"observed={observed or 'trigger_updated'}")

    before_continue_url = page.url
    try:
        step1_continue(page, timeout_ms, continue_timeout_ms)
    except RuntimeError:
        _dismiss_blocking_dialogs(page, timeout_ms)
        goto_diary_entries(page, timeout_ms)
        if try_open_existing_entry_edit(page, row["Date"], timeout_ms):
            emit_ack(row, attempt, "mode", "ok", reason="edit_after_continue_fail")
            fill_step2_fields(page, row, timeout_ms, replace_existing=True)
            save_diary_entry_form(
                page,
                row,
                timeout_ms,
                attempt,
                emit_ack,
                t0,
                from_edit=True,
                is_last_row=is_last_row,
            )
            return
        raise

    emit_ack(row, attempt, "continue_clicked", "ok")
    page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
    fill_step2_fields(page, row, timeout_ms, replace_existing=False)
    save_diary_entry_form(
        page,
        row,
        timeout_ms,
        attempt,
        emit_ack,
        t0,
        from_edit=False,
        is_last_row=is_last_row,
    )


def create_one_entry(
    page: Page,
    row: dict[str, Any],
    timeout_ms: int,
    date_timeout_ms: int,
    continue_timeout_ms: int,
    attempt: int,
    emit_ack,
    *,
    is_last_row: bool = False,
) -> None:
    row_no = row["_row_no"]
    row_started = time.perf_counter()
    LOGGER.info("Row %s: starting entry for %s", row_no, row["Date"])
    emit_ack(row, attempt, "row_start", "ok")

    goto_diary_entries(page, timeout_ms)

    if try_open_existing_entry_edit(page, row["Date"], timeout_ms):
        emit_ack(row, attempt, "mode", "ok", reason="edit_existing_portal_entry")
        fill_step2_fields(page, row, timeout_ms, replace_existing=True)
        save_diary_entry_form(
            page,
            row,
            timeout_ms,
            attempt,
            emit_ack,
            row_started,
            from_edit=True,
            is_last_row=is_last_row,
        )
        return

    run_create_new_entry_flow(
        page,
        row,
        timeout_ms,
        date_timeout_ms,
        continue_timeout_ms,
        attempt,
        emit_ack,
        row_started,
        is_last_row=is_last_row,
    )


def _remove_successful_entry_from_disk(entries_path: Path, date_str: str) -> None:
    if not entries_path or not entries_path.is_file():
        return
    if entries_path.suffix.lower() == ".json":
        try:
            import json
            with entries_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "entries" in data:
                # Find the successful entry
                successful_entry = None
                remaining = []
                for e in data["entries"]:
                    if (e.get("Date") or e.get("date", "")).startswith(date_str[:10]):
                        successful_entry = e
                    else:
                        remaining.append(e)
                
                if successful_entry:
                    data["entries"] = remaining
                    with entries_path.open("w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    
                    # Archive to submitted_entries.json
                    try:
                        from app.entries_store import load_submitted_entries, save_submitted_entries
                        submitted = load_submitted_entries()
                        # Avoid duplicates in archive
                        if not any((x.get("Date") or x.get("date", "")).startswith(date_str[:10]) for x in submitted):
                            submitted.append(successful_entry)
                            save_submitted_entries(submitted)
                    except Exception as e:
                        LOGGER.warning("Failed to archive successful entry: %s", e)
        except Exception as e:
            LOGGER.warning("Failed to process successful entry from JSON: %s", e)

def _process_all_rows(
    page: Page,
    rows: list[dict[str, Any]],
    *,
    username: str,
    password: str,
    timeout_ms: int,
    date_timeout_ms: int,
    continue_timeout_ms: int,
    skip_on_error: bool,
    screenshot_on_error_dir: Path | None,
    ack_jsonl_path: Path,
    run_id: str,
    entries_path: Path | None = None,
) -> int:
    failed = 0
    login(page, username, password, timeout_ms)
    for idx, row in enumerate(rows):
        is_last_row = idx == len(rows) - 1
        max_retries = 3
        for attempt in range(1, max_retries + 1):

            def emit_ack(
                row_data: dict[str, Any],
                current_attempt: int,
                step: str,
                status: str,
                reason: str = "",
                duration_ms: int | None = None,
                row_missed: bool | None = None,
            ) -> None:
                payload = {
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "run_id": run_id,
                    "row_no": row_data.get("_row_no"),
                    "date": row_data.get("Date"),
                    "internship": row_data.get("Internship"),
                    "attempt": current_attempt,
                    "step": step,
                    "status": status,
                    "duration_ms": duration_ms,
                    "reason": reason,
                    "row_missed": row_missed,
                }
                append_ack_event(ack_jsonl_path, payload)

            try:
                create_one_entry(
                    page,
                    row,
                    timeout_ms,
                    date_timeout_ms,
                    continue_timeout_ms,
                    attempt,
                    emit_ack,
                    is_last_row=is_last_row,
                )
                if entries_path:
                    _remove_successful_entry_from_disk(entries_path, row["Date"])
                break
            except Exception as e:
                import traceback

                traceback.print_exc()
                LOGGER.error(
                    "Row %s failed (Attempt %d/%d): %s",
                    row["_row_no"],
                    attempt,
                    max_retries,
                    e,
                )
                emit_ack(
                    row,
                    attempt,
                    "row_failed",
                    "error",
                    reason=str(e),
                    row_missed=True,
                )
                emit_ack(
                    row,
                    attempt,
                    "row_missed",
                    "error",
                    reason="save_failed_or_no_success_signal",
                    row_missed=True,
                )

                if screenshot_on_error_dir:
                    path = (
                        screenshot_on_error_dir
                        / f"error_row_{row['_row_no']}_attempt_{attempt}.png"
                    )
                    try:
                        page.screenshot(path=str(path), full_page=True)
                    except PlaywrightError:
                        LOGGER.warning(
                            "Could not capture screenshot for row %s attempt %s (page closed).",
                            row["_row_no"],
                            attempt,
                        )

                if attempt == max_retries:
                    failed += 1
                    if not skip_on_error:
                        raise
                else:
                    LOGGER.info("Attempting to recover session and retry...")
                    try:
                        if "sign-in" in page.url or "login" in page.url:
                            login(page, username, password, timeout_ms)
                        else:
                            page.goto(
                                DIARY_ENTRIES_URL,
                                wait_until="domcontentloaded",
                                timeout=timeout_ms,
                            )
                        page.wait_for_timeout(2000)
                    except Exception as recovery_error:
                        LOGGER.error("Recovery failed: %s", recovery_error)
    return failed


def run(
    entries_path: Path,
    *,
    username: str,
    password: str,
    sheet: str,
    headed: bool,
    slow_mo_ms: float,
    skip_on_error: bool,
    keep_browser_open: bool,
    timeout_ms: int,
    date_timeout_ms: int,
    continue_timeout_ms: int,
    dry_run: bool,
    screenshot_on_error_dir: Path | None,
    ack_jsonl_path: Path,
) -> int:
    rows = load_entries(entries_path, sheet)
    LOGGER.info("Loaded %d row(s) from %s.", len(rows), entries_path)
    run_id = uuid.uuid4().hex
    if dry_run:
        for r in rows:
            LOGGER.info("DRY RUN row %s: %s - %s", r["_row_no"], r["Date"], r["Internship"][:60])
        return 0

    launch_kwargs: dict[str, Any] = {"headless": not headed, "slow_mo": slow_mo_ms}
    viewport = {"width": 1280, "height": 900}
    failed = 0

    with sync_playwright() as pw:
        if keep_browser_open and headed:
            browser = pw.chromium.launch(**launch_kwargs)
            context = browser.new_context(viewport=viewport)
            page = context.new_page()
            _setup_headed_browser(browser, context, page)
            try:
                failed = _process_all_rows(
                    page,
                    rows,
                    username=username,
                    password=password,
                    timeout_ms=timeout_ms,
                    date_timeout_ms=date_timeout_ms,
                    continue_timeout_ms=continue_timeout_ms,
                    skip_on_error=skip_on_error,
                    screenshot_on_error_dir=screenshot_on_error_dir,
                    ack_jsonl_path=ack_jsonl_path,
                    run_id=run_id,
                    entries_path=entries_path,
                )
            except Exception:
                LOGGER.info("Run failed - closing browser.")
                _close_browser_session(page, context, browser, headed=headed)
                raise
            LOGGER.info(
                "Keeping browser open (--keep-browser-open). Close the Chromium window manually."
            )
        else:
            browser = pw.chromium.launch(**launch_kwargs)
            context = None
            page = None
            try:
                context = browser.new_context(viewport=viewport)
                page = context.new_page()
                LOGGER.info("Browser started (headed=%s).", headed)
                if headed:
                    _setup_headed_browser(browser, context, page)
                failed = _process_all_rows(
                    page,
                    rows,
                    username=username,
                    password=password,
                    timeout_ms=timeout_ms,
                    date_timeout_ms=date_timeout_ms,
                    continue_timeout_ms=continue_timeout_ms,
                    skip_on_error=skip_on_error,
                    screenshot_on_error_dir=screenshot_on_error_dir,
                    ack_jsonl_path=ack_jsonl_path,
                    run_id=run_id,
                    entries_path=entries_path,
                )
            finally:
                LOGGER.info("Closing browser (no more entries to process).")
                _close_browser_session(page, context, browser, headed=headed)
    if failed:
        LOGGER.error("Finished with %d failed row(s).", failed)
        return 2
    LOGGER.info("All rows submitted.")
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="VTU AIDS - Automated Internship Diary System (VTU Internyet uploader)."
    )
    p.add_argument(
        "--json",
        type=Path,
        default=None,
        help="Path to entries .json (e.g. generated/entries.json).",
    )
    p.add_argument(
        "--excel",
        type=Path,
        default=None,
        help="Path to .xlsx (legacy; default internship_entries.xlsx if no --json).",
    )
    p.add_argument(
        "--config",
        type=Path,
        default=None,
        help="student_config.json for username/password when flags omitted.",
    )
    p.add_argument("--sheet", default="Entries", help='Worksheet name (default: "Entries").')
    p.add_argument("--headed", action="store_true", help="Run with visible Chromium.")
    p.add_argument(
        "--keep-browser-open",
        action="store_true",
        help="Do not close Chromium when finished (debug only).",
    )
    p.add_argument("--slow-mo", type=float, default=0, dest="slow_mo", help="Slow motion ms for Playwright.")
    p.add_argument(
        "--skip-on-error",
        action="store_true",
        help="Continue remaining rows after a failure.",
    )
    p.add_argument("--timeout-ms", type=int, default=120000, help="Navigation / action timeout.")
    p.add_argument(
        "--date-timeout-ms",
        type=int,
        default=DEFAULT_DATE_TIMEOUT_MS,
        help="Timeout for selecting and verifying date in step 1.",
    )
    p.add_argument(
        "--continue-timeout-ms",
        type=int,
        default=DEFAULT_CONTINUE_TIMEOUT_MS,
        help="Timeout for clicking and verifying Continue transition.",
    )
    p.add_argument("--dry-run", action="store_true", help="Only validate entries file; no browser.")
    p.add_argument(
        "--screenshot-on-error-dir",
        type=Path,
        default=None,
        help="Optional directory for full-page screenshots on row failure.",
    )
    p.add_argument(
        "--ack-jsonl-path",
        type=Path,
        default=Path("run_acknowledgements.jsonl"),
        help="Append-only JSONL path for per-step acknowledgements and missed-entry analysis.",
    )
    p.add_argument("--username", type=str, default=None, help="Username for login.")
    p.add_argument("--password", type=str, default=None, help="Password for login.")
    return p


def prompt_if_missing(prompt: str, secret: bool = False, default: str | None = None) -> str:
    if default:
        print(f"{prompt} [{default}]: ", end="", flush=True)
        line = sys.stdin.readline().rstrip("\n")
        if not line and default:
            return default
        if not line and not default:
            return prompt_if_missing(prompt, secret=secret)
        if secret:
            return getpass.getpass(f"{prompt}: ")
        return line
    if secret:
        return getpass.getpass(f"{prompt}: ")
    return input(f"{prompt}: ").strip()


def resolve_entries_path(args: argparse.Namespace) -> Path:
    if args.json is not None and args.excel is not None:
        LOGGER.warning("Both --json and --excel given; using --json.")
    if args.json is not None:
        return args.json.expanduser()
    if args.excel is not None:
        return args.excel.expanduser()
    default_json = Path("generated/entries.json")
    if default_json.is_file():
        return default_json
    return Path("internship_entries.xlsx")


def resolve_credentials(args: argparse.Namespace) -> tuple[str, str]:
    if args.username and args.password:
        return args.username, args.password
    if args.config and args.config.is_file():
        cfg_user, cfg_pass = load_config_credentials(args.config.expanduser())
        return args.username or cfg_user, args.password or cfg_pass
    username = args.username or prompt_if_missing("Username / email / USN")
    password = args.password or prompt_if_missing("Password", secret=True)
    return username, password


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = build_arg_parser().parse_args()
    entries_path = resolve_entries_path(args)
    if not entries_path.is_file():
        LOGGER.error("Entries file not found: %s", entries_path)
        return 1

    run_kwargs = dict(
        entries_path=entries_path,
        sheet=args.sheet,
        headed=args.headed,
        slow_mo_ms=args.slow_mo,
        skip_on_error=args.skip_on_error,
        keep_browser_open=args.keep_browser_open,
        timeout_ms=args.timeout_ms,
        date_timeout_ms=args.date_timeout_ms,
        continue_timeout_ms=args.continue_timeout_ms,
        screenshot_on_error_dir=args.screenshot_on_error_dir,
        ack_jsonl_path=args.ack_jsonl_path,
    )

    if args.dry_run:
        return run(username="", password="", dry_run=True, **run_kwargs)

    username, password = resolve_credentials(args)
    return run(username=username, password=password, dry_run=False, **run_kwargs)


if __name__ == "__main__":
    import atexit

    # Works for both package launch (app.run_diary_bot) and direct script launch.
    atexit.register(_cleanup_playwright_chromium_windows)
    raise SystemExit(main())

