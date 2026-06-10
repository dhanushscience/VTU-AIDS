"""FastAPI web launcher for VTU AIDS (Automated Internship Diary System)."""

from __future__ import annotations

import json
import logging
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Request, UploadFile, Path as FPath
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from pydantic import BaseModel, Field

from app.deps import dependency_status, genai_import_error
from app.diagnostics import (
    APP_VERSION,
    build_github_issue_url,
    configure_release_logging,
    create_log_bundle,
    issue_metadata,
)
from app.config_store import (
    complete_setup,
    config_for_api,
    config_for_api_from,
    config_setup_status,
    config_with_secrets,
    is_setup_required,
    normalize_api_key,
    resolve_gemini_api_key,
    save_config,
    validate_api_key_format,
)
from app.errors import log_error, public_error_message, raise_http, error_context_from_request_path
from app.date_resolver import resolve_dates
from app.document_extract import IMAGE_EXTENSIONS, extract_text_from_upload
from app.entries_store import delete_entry_by_date, load_entries, save_entries
from app.excel_export import write_entries_excel
from app.gemini_service import (
    DEFAULT_GEMINI_MODEL,
    GEMINI_MODEL_OPTIONS,
    RECOMMENDED_MODELS,
    generate_entries,
    generate_single_entry,
)
from app.bot_runner import get_status as get_bot_status
from app.bot_runner import start_bot
from app.bot_runner import stop_bot
from app.process_cleanup import (
    install_shutdown_handlers,
    reconcile_stale_automation,
    shutdown_all,
)
from app.paths import (
    config_path,
    entries_excel_path,
    entries_json_path,
    ensure_ssl_certificates,
    static_dir,
    writable_root,
)

ensure_ssl_certificates()
configure_release_logging("api")
LOGGER = logging.getLogger(__name__)

PROJECT_ROOT = writable_root()
STATIC_DIR = static_dir()
GITHUB_RELEASES_LATEST_API = "https://api.github.com/repos/dhanushscience/VTU-AIDS/releases/latest"
GITHUB_RELEASES_PAGE = "https://github.com/dhanushscience/VTU-AIDS/releases/latest"

_NO_CACHE = {"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"}

import time
import threading

_RATE_LIMITS: dict[str, float] = {}
_RL_LOCK = threading.Lock()

def check_rate_limit(key: str, min_interval: float) -> None:
    with _RL_LOCK:
        now = time.time()
        last = _RATE_LIMITS.get(key, 0.0)
        if now - last < min_interval:
            raise HTTPException(status_code=429, detail="Too many requests. Please wait and try again.")
        _RATE_LIMITS[key] = now

class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method in ("POST", "PUT", "DELETE", "PATCH") and request.url.path.startswith("/api/"):
            origin = request.headers.get("origin") or request.headers.get("referer") or ""
            if origin:
                if not ("127.0.0.1" in origin or "localhost" in origin):
                    return JSONResponse(status_code=403, content={"detail": "Cross-Origin Request Blocked for Security"})
        return await call_next(request)


def _require_setup_complete() -> None:
    if is_setup_required():
        raise HTTPException(
            status_code=403,
            detail="Complete the setup wizard first (portal login and Gemini API key).",
        )


class _NoCacheUiMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        path = request.url.path
        if path == "/" or path.startswith("/static/"):
            for key, value in _NO_CACHE.items():
                response.headers[key] = value
        return response


app = FastAPI(title="VTU AIDS", description="Automated Internship Diary System")
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^http://(127\.0\.0\.1|localhost)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(CSRFMiddleware)
app.add_middleware(_NoCacheUiMiddleware)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

install_shutdown_handlers()


@app.on_event("startup")
def _startup_reconcile_automation() -> None:
    reconcile_stale_automation()


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Keep explicit HTTPException details; only polish structured/non-string payloads."""
    detail = exc.detail
    if isinstance(detail, str):
        return JSONResponse(status_code=exc.status_code, content={"detail": detail})

    ctx = error_context_from_request_path(request.url.path)
    detail = public_error_message(exc, context=ctx)
    return JSONResponse(status_code=exc.status_code, content={"detail": detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    ctx = error_context_from_request_path(request.url.path)
    log_error(f"{request.method} {request.url.path}", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": public_error_message(exc, context=ctx)},
    )


class ConfigUpdate(BaseModel):
    username: str = ""
    password: str = ""
    gemini_api_key: str = ""
    gemini_model: str = DEFAULT_GEMINI_MODEL
    default_internship: str = ""
    default_hours: float = 6
    default_description_words: int = 80
    hours_mode: str = "constant"
    hours_constant: float = 6
    hours_min: float = 5
    hours_max: float = 8
    internship_start_date: str = ""
    internship_end_date: str = ""
    internship_total_days: int = 0


class DatesResolveRequest(BaseModel):
    mode: str = "calendar"
    dates: list[str] = Field(default_factory=list)
    from_date: str | None = Field(default=None, alias="from")
    till: str | None = None
    skip_weekdays: list[str] = Field(default_factory=lambda: ["sat", "sun"])

    model_config = {"populate_by_name": True}

    def to_payload(self) -> dict[str, Any]:
        if self.mode == "range":
            return {
                "mode": "range",
                "from": self.from_date,
                "till": self.till,
                "skip_weekdays": self.skip_weekdays,
            }
        return {"mode": "calendar", "dates": self.dates}


class GenerateRequest(BaseModel):
    dates: list[str]
    work_description: str = ""
    reference_context: str = ""
    internship: str = ""
    default_hours: float | None = None
    description_words: int | None = None
    hours_mode: str = "constant"
    hours_constant: float | None = None
    hours_min: float | None = None
    hours_max: float | None = None


class GenerateDayRequest(BaseModel):
    date: str
    work_description: str = ""
    reference_context: str = ""
    internship: str = ""
    description_words: int | None = None
    hours_mode: str = "constant"
    hours_constant: float | None = None
    hours_min: float | None = None
    hours_max: float | None = None


class EntryRecord(BaseModel):
    date: str
    internship: str = ""
    description: str = ""
    hoursWorked: float | int | str = ""
    learningOutcomes: str = ""
    skillsUsed: str = ""
    referenceLinks: str = ""
    blockersRisks: str = ""
    modified: bool = False
    original: dict[str, Any] | None = None


class SaveEntriesRequest(BaseModel):
    entries: list[dict[str, Any]] = Field(default_factory=list)


def _write_all_entries(entries: list[dict[str, Any]]) -> None:
    if entries:
        save_entries(entries)
        write_entries_excel(entries, entries_excel_path())
    else:
        for path in (entries_json_path(), entries_excel_path()):
            if path.is_file():
                path.unlink()


class RunBotRequest(BaseModel):
    headed: bool = True
    skip_on_error: bool = True


class SetupCompleteRequest(BaseModel):
    username: str = ""
    password: str = ""
    gemini_api_key: str = ""
    gemini_model: str = DEFAULT_GEMINI_MODEL
    default_internship: str = ""
    default_description_words: int = 80
    internship_start_date: str = ""
    internship_end_date: str = ""
    internship_total_days: int = 0

@app.post("/api/shutdown")
def api_shutdown() -> dict[str, str]:
    import os
    import threading

    def _exit_cleanly() -> None:
        shutdown_all()
        os._exit(0)

    threading.Timer(0.4, _exit_cleanly).start()
    return {"status": "shutting_down"}



@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html", headers=_NO_CACHE)


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> FileResponse:
    for name, media in (
        ("AIDS_TASKBAR_FAVICON.png", "image/png"),
        ("favicon.png", "image/png"),
        ("AIDS_MAIN.png", "image/png"),
        ("logo.png", "image/png"),
        ("app.ico", "image/x-icon"),
    ):
        icon = STATIC_DIR / name
        if icon.is_file():
            return FileResponse(icon, media_type=media)
    raise HTTPException(status_code=404)


@app.get("/logo.png", include_in_schema=False)
def logo_png() -> FileResponse:
    for name in ("AIDS_MAIN.png", "logo.png"):
        logo = STATIC_DIR / name
        if logo.is_file():
            return FileResponse(logo, media_type="image/png")
    raise HTTPException(status_code=404)


@app.get("/api/status")
def api_status() -> dict[str, Any]:
    deps = dependency_status()
    err = genai_import_error()
    return {"ok": deps["ready"], "dependencies": deps, "message": err}


@app.get("/api/version")
def api_version() -> dict[str, Any]:
    return {"version": APP_VERSION}


def _normalize_version(version: str) -> tuple[int, ...]:
    raw = (version or "").strip().lower()
    if raw.startswith("v"):
        raw = raw[1:]
    core = raw.split("-", 1)[0]
    out: list[int] = []
    for chunk in core.split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        out.append(int(digits) if digits else 0)
    while out and out[-1] == 0:
        out.pop()
    return tuple(out or [0])


def _is_newer_version(latest: str, current: str) -> bool:
    l_parts = list(_normalize_version(latest))
    c_parts = list(_normalize_version(current))
    size = max(len(l_parts), len(c_parts))
    l_parts.extend([0] * (size - len(l_parts)))
    c_parts.extend([0] * (size - len(c_parts)))
    return tuple(l_parts) > tuple(c_parts)


@app.get("/api/update-check")
def api_update_check() -> dict[str, Any]:
    request = urllib.request.Request(
        GITHUB_RELEASES_LATEST_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"VTU-AIDS/{APP_VERSION}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=6) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        LOGGER.warning("Update check failed: %s", exc)
        return {
            "checked": False,
            "current_version": APP_VERSION,
            "latest_version": APP_VERSION,
            "update_available": False,
            "release_url": GITHUB_RELEASES_PAGE,
            "installer_url": GITHUB_RELEASES_PAGE,
            "error": "Unable to check updates right now.",
        }

    latest_tag = str(payload.get("tag_name") or "").strip() or APP_VERSION
    latest_version = latest_tag[1:] if latest_tag.lower().startswith("v") else latest_tag
    release_url = str(payload.get("html_url") or GITHUB_RELEASES_PAGE)
    installer_url = release_url
    for asset in payload.get("assets", []):
        name = str(asset.get("name") or "")
        if name.lower() == "vtu_aids_setup.exe":
            installer_url = str(asset.get("browser_download_url") or installer_url)
            break
    return {
        "checked": True,
        "current_version": APP_VERSION,
        "latest_version": latest_version,
        "update_available": _is_newer_version(latest_version, APP_VERSION),
        "release_url": release_url,
        "installer_url": installer_url,
    }


@app.get("/api/diagnostics/report-bug")
def api_report_bug() -> dict[str, Any]:
    meta = issue_metadata()
    return {
        "ok": True,
        "issue_url": build_github_issue_url(title=f"Bug report: VTU AIDS {APP_VERSION}"),
        "metadata": meta,
    }


@app.post("/api/diagnostics/export-logs")
def api_export_logs() -> dict[str, Any]:
    try:
        bundle = create_log_bundle()
        rel = str(bundle.relative_to(writable_root()))
        LOGGER.info("Diagnostics bundle exported: %s", bundle)
        return {"ok": True, "bundle": rel, "path": str(bundle)}
    except Exception as e:
        raise_http(500, e, context="api", log=True)


@app.get("/api/config")
def get_config() -> dict[str, Any]:
    return config_for_api()


@app.get("/api/setup/status")
def api_setup_status() -> dict[str, Any]:
    return config_setup_status()


@app.post("/api/setup/complete")
def api_setup_complete(body: SetupCompleteRequest) -> dict[str, Any]:
    try:
        saved = complete_setup(
            username=body.username,
            password=body.password,
            gemini_api_key=body.gemini_api_key,
            gemini_model=body.gemini_model,
            default_internship=body.default_internship,
            default_description_words=body.default_description_words,
            internship_start_date=body.internship_start_date,
            internship_end_date=body.internship_end_date,
            internship_total_days=body.internship_total_days,
        )
        return {
            "ok": True,
            "config": config_for_api_from(saved),
            "setup": config_setup_status(saved),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/api/gemini-models")
def list_gemini_models() -> dict[str, Any]:
    return {
        "default": DEFAULT_GEMINI_MODEL,
        "recommended": list(RECOMMENDED_MODELS),
        "options": [{"id": mid, "label": label} for mid, label in GEMINI_MODEL_OPTIONS],
        "auto_fallback": True,
    }


@app.post("/api/config")
def post_config(body: ConfigUpdate) -> dict[str, Any]:
    if not (20 <= int(body.default_description_words) <= 500):
        raise HTTPException(status_code=400, detail="default_description_words must be between 20 and 500.")
    if not (1 <= float(body.hours_constant) <= 24):
        raise HTTPException(status_code=400, detail="hours_constant must be between 1 and 24.")
    if not (1 <= float(body.hours_min) <= 24) or not (1 <= float(body.hours_max) <= 24):
        raise HTTPException(status_code=400, detail="hours_min and hours_max must be between 1 and 24.")
    if float(body.hours_min) > float(body.hours_max):
        raise HTTPException(status_code=400, detail="Min hours cannot be greater than max hours.")
    data: dict[str, Any] = {
        "username": body.username.strip(),
        "gemini_model": body.gemini_model.strip() or DEFAULT_GEMINI_MODEL,
        "default_internship": body.default_internship.strip(),
        "default_hours": body.default_hours,
        "default_description_words": body.default_description_words,
        "hours_mode": body.hours_mode.strip().lower() or "constant",
        "hours_constant": body.hours_constant,
        "hours_min": body.hours_min,
        "hours_max": body.hours_max,
        "internship_start_date": body.internship_start_date.strip(),
        "internship_end_date": body.internship_end_date.strip(),
        "internship_total_days": max(0, int(body.internship_total_days or 0)),
    }
    if body.password and body.password != "***":
        data["password"] = body.password
    if body.gemini_api_key and body.gemini_api_key != "***":
        key = normalize_api_key(body.gemini_api_key)
        validate_api_key_format(key)
        data["gemini_api_key"] = key
    saved = save_config(data)
    return config_for_api_from(saved)


@app.post("/api/dates/resolve")
def api_dates_resolve(body: DatesResolveRequest) -> dict[str, Any]:
    _require_setup_complete()
    try:
        if body.mode == "range" and (not body.from_date or not body.till):
            raise ValueError("Range mode requires 'from' and 'till'.")
        dates = resolve_dates(body.to_payload())
        return {"dates": dates, "count": len(dates)}
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/api/documents/extract")
async def api_extract_document(file: UploadFile = File(...)) -> dict[str, Any]:
    """Extract text from documents, images (Gemini vision), or code files."""
    _require_setup_complete()
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename.")
    try:
        data = await file.read()
        api_key: str | None = None
        ext = Path(file.filename).suffix.lower()
        if ext in IMAGE_EXTENSIONS or ext == ".pdf":
            cfg = config_with_secrets()
            api_key = resolve_gemini_api_key(cfg)
        result = extract_text_from_upload(file.filename, data, api_key=api_key)
        return {"ok": True, **result}
    except Exception as e:
        raise_http(400, e, context="document", log=True)


@app.post("/api/generate")
def api_generate(body: GenerateRequest) -> dict[str, Any]:
    _require_setup_complete()
    check_rate_limit("generate", 2.0)
    cfg = config_with_secrets()
    internship = body.internship.strip() or str(cfg.get("default_internship", "")).strip()
    hours = body.default_hours if body.default_hours is not None else cfg.get("default_hours", 6)
    hours_mode = (body.hours_mode or cfg.get("hours_mode", "constant")).strip().lower()
    if hours_mode not in ("constant", "range"):
        raise HTTPException(status_code=400, detail="hours_mode must be 'constant' or 'range'.")
    hours_constant = (
        body.hours_constant
        if body.hours_constant is not None
        else cfg.get("hours_constant", cfg.get("default_hours", 6))
    )
    hours_min = body.hours_min if body.hours_min is not None else cfg.get("hours_min", 5)
    hours_max = body.hours_max if body.hours_max is not None else cfg.get("hours_max", 8)
    if hours_mode == "range" and float(hours_min) > float(hours_max):
        raise HTTPException(status_code=400, detail="Min hours cannot be greater than max hours.")
    if not (1 <= float(hours_constant) <= 24):
        raise HTTPException(status_code=400, detail="hours_constant must be between 1 and 24.")
    if not (1 <= float(hours_min) <= 24) or not (1 <= float(hours_max) <= 24):
        raise HTTPException(status_code=400, detail="hours_min and hours_max must be between 1 and 24.")

    words = body.description_words if body.description_words is not None else cfg.get(
        "default_description_words", 80
    )
    words = max(20, min(500, int(words)))
    try:
        api_key = resolve_gemini_api_key(cfg)
        validate_api_key_format(api_key)
        payload = generate_entries(
            api_key=api_key,
            model=str(cfg.get("gemini_model", DEFAULT_GEMINI_MODEL)),
            dates=body.dates,
            work_description=body.work_description,
            reference_context=body.reference_context,
            internship=internship,
            default_hours=hours,
            description_words=words,
            hours_mode=hours_mode,
            hours_constant=hours_constant,
            hours_min=hours_min,
            hours_max=hours_max,
        )
        save_config(
            {
                "hours_mode": hours_mode,
                "hours_constant": hours_constant,
                "hours_min": hours_min,
                "hours_max": hours_max,
                "default_hours": hours_constant,
            }
        )
        return {
            "ok": True,
            "path": str(entries_json_path().relative_to(writable_root())),
            "entries": payload["entries"],
            "model_used": payload.get("model_used"),
        }
    except FileNotFoundError as e:
        raise_http(500, e, context="generate", log=True)
    except (ValueError, RuntimeError) as e:
        raise_http(400, e, context="generate", log=False)
    except Exception as e:
        raise_http(500, e, context="generate", log=True)


@app.post("/api/generate-day")
def api_generate_day(body: GenerateDayRequest) -> dict[str, Any]:
    """Generate AI content for a single calendar day."""
    _require_setup_complete()
    check_rate_limit("generate", 1.0)
    cfg = config_with_secrets()
    internship = body.internship.strip() or str(cfg.get("default_internship", "")).strip()
    hours_mode = (body.hours_mode or cfg.get("hours_mode", "constant")).strip().lower()
    if hours_mode not in ("constant", "range"):
        raise HTTPException(status_code=400, detail="hours_mode must be 'constant' or 'range'.")
    hours_constant = (
        body.hours_constant
        if body.hours_constant is not None
        else cfg.get("hours_constant", cfg.get("default_hours", 6))
    )
    hours_min = body.hours_min if body.hours_min is not None else cfg.get("hours_min", 5)
    hours_max = body.hours_max if body.hours_max is not None else cfg.get("hours_max", 8)
    if hours_mode == "range" and float(hours_min) > float(hours_max):
        raise HTTPException(status_code=400, detail="Min hours cannot be greater than max hours.")
    if not (1 <= float(hours_constant) <= 24):
        raise HTTPException(status_code=400, detail="hours_constant must be between 1 and 24.")
    if not (1 <= float(hours_min) <= 24) or not (1 <= float(hours_max) <= 24):
        raise HTTPException(status_code=400, detail="hours_min and hours_max must be between 1 and 24.")
    words = body.description_words if body.description_words is not None else cfg.get(
        "default_description_words", 80
    )
    words = max(20, min(500, int(words)))
    try:
        api_key = resolve_gemini_api_key(cfg)
        validate_api_key_format(api_key)
        return generate_single_entry(
            api_key=api_key,
            model=str(cfg.get("gemini_model", DEFAULT_GEMINI_MODEL)),
            date=body.date,
            work_description=body.work_description,
            reference_context=body.reference_context,
            internship=internship,
            default_hours=cfg.get("default_hours", 6),
            description_words=words,
            hours_mode=hours_mode,
            hours_constant=hours_constant,
            hours_min=hours_min,
            hours_max=hours_max,
        )
    except (ValueError, RuntimeError) as e:
        raise_http(400, e, context="generate", log=False)
    except Exception as e:
        raise_http(500, e, context="generate", log=True)


@app.get("/api/entries/preview")
def preview_entries() -> dict[str, Any]:
    from app.entries_store import load_submitted_entries
    submitted = []
    for entry in load_submitted_entries():
        if not isinstance(entry, dict):
            continue
        date_val = str(entry.get("date") or entry.get("Date") or "").strip()[:10]
        if not date_val:
            continue
        submitted.append({**entry, "date": date_val})
    return {
        "entries": load_entries(),
        "submitted": submitted,
    }


@app.delete("/api/entries")
def clear_entries() -> dict[str, Any]:
    """Remove saved entries so a new browser session starts with an empty AI section."""
    for path in (entries_json_path(), entries_excel_path()):
        if path.is_file():
            path.unlink()
    return {"ok": True}


@app.put("/api/entries")
def api_save_entries(body: SaveEntriesRequest) -> dict[str, Any]:
    entries = list(body.entries)
    _write_all_entries(entries)
    
    # If the user edited an entry that was in the submitted archive, un-archive it
    from app.entries_store import remove_submitted_entry_by_date
    for e in entries:
        remove_submitted_entry_by_date(e.get("date") or e.get("Date") or "")

    modified_count = sum(1 for e in entries if e.get("modified"))
    return {"ok": True, "count": len(entries), "modified_count": modified_count, "entries": entries}


@app.delete("/api/entries/day/{date}")
def api_delete_entry_day(date: str = FPath(..., pattern=r"^\d{4}-\d{2}-\d{2}$")) -> dict[str, Any]:
    try:
        remaining = delete_entry_by_date(date)
        _write_all_entries(remaining)
        return {"ok": True, "count": len(remaining), "entries": remaining}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.get("/api/entries/download-excel")
def download_entries_excel() -> FileResponse:
    entries = load_entries()
    if not entries:
        raise HTTPException(status_code=404, detail="Generate entries first.")
    xlsx = entries_excel_path()
    write_entries_excel(entries, xlsx)
    return FileResponse(
        xlsx,
        filename="internship_entries.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.get("/api/run-bot/status")
def api_run_bot_status() -> dict[str, Any]:
    return get_bot_status()


@app.post("/api/run-bot")
def api_run_bot(body: RunBotRequest) -> dict[str, Any]:
    _require_setup_complete()
    check_rate_limit("run_bot", 5.0)
    entries = load_entries()
    if not entries:
        raise HTTPException(status_code=400, detail="Generate entries with AI first.")
    _write_all_entries(entries)
    cfg = config_with_secrets()
    if not str(cfg.get("username", "")).strip() or not str(cfg.get("password", "")).strip():
        raise HTTPException(status_code=400, detail="Set username and password in Settings.")

    st = get_bot_status()
    if st.get("running"):
        return {
            "ok": True,
            "started": False,
            "already_running": True,
            "message": "Automation is already running.",
        }

    result = start_bot(headed=body.headed, skip_on_error=body.skip_on_error)
    if not result.get("started"):
        raise HTTPException(status_code=409, detail=result.get("detail", "Could not start automation."))
    return result


@app.post("/api/run-bot/stop")
def api_stop_bot() -> dict[str, Any]:
    _require_setup_complete()
    return stop_bot()
