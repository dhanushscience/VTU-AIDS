"""FastAPI web launcher for VTU AIDS (Automated Internship Diary System)."""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from pydantic import BaseModel, Field

from app.deps import dependency_status, genai_import_error
from app.config_store import (
    config_for_api,
    config_with_secrets,
    normalize_api_key,
    resolve_gemini_api_key,
    config_for_api_from,
    save_config,
    validate_api_key_format,
)
from app.date_resolver import resolve_dates
from app.document_extract import IMAGE_EXTENSIONS, extract_text_from_upload
from app.entries_store import delete_entry_by_date, load_entries, save_entries
from app.excel_export import write_entries_excel
from app.gemini_service import (
    DEFAULT_GEMINI_MODEL,
    RECOMMENDED_MODELS,
    generate_entries,
    generate_single_entry,
)
from app.bot_runner import get_status as get_bot_status
from app.bot_runner import start_bot
from app.paths import (
    config_path,
    entries_excel_path,
    entries_json_path,
    ensure_ssl_certificates,
    static_dir,
    writable_root,
)

ensure_ssl_certificates()

PROJECT_ROOT = writable_root()
STATIC_DIR = static_dir()

APP_VERSION = "1.0.3"
_NO_CACHE = {"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"}


class _NoCacheUiMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        path = request.url.path
        if path == "/" or path.startswith("/static/"):
            for key, value in _NO_CACHE.items():
                response.headers[key] = value
        return response


app = FastAPI(title="VTU AIDS", description="Automated Internship Diary System")
app.add_middleware(_NoCacheUiMiddleware)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


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

@app.post("/api/shutdown")
def api_shutdown() -> dict[str, str]:
    import threading
    import os
    # Wait briefly so the response goes through, then kill process
    threading.Timer(0.5, lambda: os._exit(0)).start()
    return {"status": "shutting_down"}



@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html", headers=_NO_CACHE)


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> FileResponse:
    for name, media in (
        ("favicon.png", "image/png"),
        ("logo.png", "image/png"),
        ("app.ico", "image/x-icon"),
    ):
        icon = STATIC_DIR / name
        if icon.is_file():
            return FileResponse(icon, media_type=media)
    raise HTTPException(status_code=404)


@app.get("/logo.png", include_in_schema=False)
def logo_png() -> FileResponse:
    logo = STATIC_DIR / "logo.png"
    if logo.is_file():
        return FileResponse(logo, media_type="image/png")
    raise HTTPException(status_code=404)


@app.get("/api/status")
def api_status() -> dict[str, Any]:
    deps = dependency_status()
    err = genai_import_error()
    return {"ok": deps["ready"], "dependencies": deps, "message": err}


@app.get("/api/config")
def get_config() -> dict[str, Any]:
    return config_for_api()


@app.get("/api/gemini-models")
def list_gemini_models() -> dict[str, Any]:
    return {
        "default": DEFAULT_GEMINI_MODEL,
        "recommended": list(RECOMMENDED_MODELS),
    }


@app.post("/api/config")
def post_config(body: ConfigUpdate) -> dict[str, Any]:
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
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename.")
    try:
        data = await file.read()
        api_key: str | None = None
        ext = Path(file.filename).suffix.lower()
        if ext in IMAGE_EXTENSIONS:
            cfg = config_with_secrets()
            api_key = resolve_gemini_api_key(cfg)
        result = extract_text_from_upload(file.filename, data, api_key=api_key)
        return {"ok": True, **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Could not read file: {e}",
        ) from e


@app.post("/api/generate")
def api_generate(body: GenerateRequest) -> dict[str, Any]:
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
        raise HTTPException(
            status_code=500,
            detail=(
                f"Generate failed due to missing file: {e}. "
                "Original error: HTTPS certificate file missing. "
                "Restart the app after running Install VTU AIDS.bat, or remove a broken "
                "SSL_CERT_FILE environment variable in Windows."
            ),
        ) from e
    except (ValueError, RuntimeError) as e:
        detail = str(e)
        status = 429 if "quota" in detail.lower() or "rate limit" in detail.lower() else 400
        raise HTTPException(status_code=status, detail=detail) from e
    except Exception as e:
        try:
            (writable_root() / "vtu_aids_error.log").write_text(
                traceback.format_exc(), encoding="utf-8"
            )
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Generate failed: {e}") from e


@app.post("/api/generate-day")
def api_generate_day(body: GenerateDayRequest) -> dict[str, Any]:
    """Generate AI content for a single calendar day."""
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
        detail = str(e)
        status = 429 if "quota" in detail.lower() or "rate limit" in detail.lower() else 400
        raise HTTPException(status_code=status, detail=detail) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generate failed: {e}") from e


@app.get("/api/entries/preview")
def preview_entries() -> dict[str, Any]:
    from app.entries_store import load_submitted_entries
    return {
        "entries": load_entries(),
        "submitted": load_submitted_entries()
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
def api_delete_entry_day(date: str) -> dict[str, Any]:
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
