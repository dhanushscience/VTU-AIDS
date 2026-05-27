"""User-facing error messages and debug logging."""

from __future__ import annotations

import re
import traceback
from datetime import datetime, timezone

from fastapi import HTTPException

from app.paths import writable_root

_LOG_NAME = "vtu_aids_error.log"

# Shown only in logs / docs — never appended to API responses shown in the UI.
_LOG_PATH_HINT = r"%LOCALAPPDATA%\VTU AIDS\vtu_aids_error.log"

_STRIP_PREFIXES = (
    "generate failed:",
    "ai generation failed:",
    "gemini api error",
)


def error_context_from_request_path(path: str) -> str:
    """Map a FastAPI route path to polish/fallback context keys."""
    lower = path.lower()
    if "/generate" in lower:
        return "generate"
    if "/document" in lower:
        return "document"
    if "/run-bot" in lower:
        return "automation"
    if "/setup" in lower:
        return "setup"
    return "api"


def _normalize_error_context(context: str) -> str:
    """Accept URL paths, log labels (``POST /api/...``), or plain context names."""
    if not context:
        return ""
    if context.startswith("/"):
        return error_context_from_request_path(context)
    for part in context.split():
        if part.startswith("/"):
            return error_context_from_request_path(part)
    return context


def error_log_path():
    return writable_root() / _LOG_NAME


def log_error(context: str, exc: BaseException | None = None) -> None:
    """Append a timestamped error entry with full traceback for debugging."""
    try:
        writable_root().mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        lines = [f"\n--- {stamp} — {context} ---\n"]
        if exc is not None:
            summary = simplify_exception_message(exc, context=context)
            if summary:
                lines.append(f"Summary: {summary}\n")
            lines.append("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
        else:
            lines.append(f"{context}\n")
        with error_log_path().open("a", encoding="utf-8") as f:
            f.writelines(lines)
    except Exception:
        pass


def _first_line(msg: str) -> str:
    text = msg.replace("\r", " ").replace("\n", " ").strip()
    return re.sub(r"\s+", " ", text)


def simplify_exception_message(exc: BaseException, *, context: str = "") -> str:
    """Plain-language error for the UI — no log paths or stack traces."""
    context = _normalize_error_context(context)
    if isinstance(exc, HTTPException):
        detail = exc.detail
        if isinstance(detail, str):
            return _polish_message(detail, context=context)
        if isinstance(detail, list):
            parts = []
            for item in detail:
                if isinstance(item, dict) and "msg" in item:
                    parts.append(str(item["msg"]))
                else:
                    parts.append(str(item))
            return _polish_message("; ".join(parts) if parts else "Request failed.", context=context)
        return _polish_message(str(detail) if detail else "Request failed.", context=context)

    raw = _first_line(str(exc).strip())
    return _polish_message(raw, context=context)


def _polish_message(raw: str, *, context: str) -> str:
    """Map technical text to short user-facing explanations."""
    context = _normalize_error_context(context)
    if not raw:
        return _fallback_for_context(context)

    msg = raw
    lower = msg.lower()

    for prefix in _STRIP_PREFIXES:
        if lower.startswith(prefix):
            msg = msg[len(prefix) :].lstrip(" :-")
            lower = msg.lower()
            break

    # Drop embedded file paths and noisy wrappers
    if len(msg) > 280:
        msg = msg[:277].rstrip() + "…"
    lower = msg.lower()

    if "complete the setup wizard" in lower or "setup wizard" in lower:
        return msg

    if "api key" in lower and ("missing" in lower or "open settings" in lower):
        return "Add your Gemini API key in Settings (or finish the setup wizard)."

    if "api key format" in lower or "starts with aiza" in lower:
        return "Gemini API key format looks wrong. Paste the full key from Google AI Studio."

    if (
        "invalid api key" in lower
        or "api key not valid" in lower
        or "api_key_invalid" in lower
        or "permission denied" in lower and "api" in lower
    ):
        return "Gemini API key is invalid or not allowed. Create a new key in Google AI Studio and save it in Settings."

    if "quota" in lower or "rate limit" in lower or "429" in lower or "resource_exhausted" in lower:
        return "Gemini API quota or rate limit reached. Wait a few minutes and try again."

    if (
        "busy" in lower
        or "overloaded" in lower
        or "unavailable" in lower
        or "try again" in lower
        or "all tried models" in lower
    ):
        return "Gemini servers are busy. The app will try another model automatically — wait a moment and retry."

    if ("404" in lower or "not found" in lower) and "model" in lower:
        return "That Gemini model is not available. Choose another model in Settings."

    if "certificate" in lower or "ssl_cert" in lower or "ssl" in lower and "cert" in lower:
        return "A secure connection could not be made. Restart VTU AIDS or reinstall the app."

    if "no dates selected" in lower:
        return "Select at least one date in Step 1."

    if "internship name is required" in lower or "internship" in lower and "required" in lower:
        return "Enter your internship label (exact text from the portal dropdown)."

    if "did not return valid json" in lower or "valid json" in lower:
        return "AI returned an unexpected response. Try again or switch to gemini-2.5-flash in Settings."

    if "expected" in lower and "entries" in lower and "got" in lower:
        return "AI returned the wrong number of diary entries. Try generating again."

    if context == "generate":
        if "gemini api error" in lower:
            # e.g. "Gemini API error (gemini-2.5-flash): 403 ..."
            return msg.split(":", 1)[-1].strip() if ":" in msg else msg
        if msg and not lower.startswith("ai generation failed"):
            return msg
        return _fallback_for_context(context)

    if context in ("automation", "run-bot") or "playwright" in lower or "internyet" in lower:
        if "username and password" in lower or "settings" in lower:
            return msg
        if msg and "portal automation" not in lower:
            return f"Portal automation failed: {msg}" if len(msg) < 120 else msg
        return _fallback_for_context("automation")

    if context == "document":
        if "could not read" in lower or "unsupported" in lower or "too large" in lower:
            return msg
        return "Could not read that file. Use a smaller file or a supported format."

    if msg:
        return msg

    return _fallback_for_context(context)


def _fallback_for_context(context: str) -> str:
    if context == "generate":
        return "AI generation failed. Check your Gemini API key, model name, and internet connection."
    if context in ("automation", "run-bot"):
        return "Portal automation failed. Check your VTU login in Settings and try again."
    if context == "document":
        return "Could not read that file. Try a smaller file or a supported format."
    if context == "setup":
        return "Complete the setup wizard (portal login and Gemini API key)."
    return "Something went wrong. Please try again."


def public_error_message(exc: BaseException, *, context: str = "") -> str:
    """Alias for API responses (no log file paths)."""
    return simplify_exception_message(exc, context=context)


def _is_quota_or_rate_limit(*texts: str) -> bool:
    """True if any text indicates Gemini quota, rate limit, or server busy."""
    markers = (
        "quota",
        "rate limit",
        "rate-limited",
        "resource_exhausted",
        "429",
        "busy",
        "overloaded",
        "unavailable",
        "all tried models",
    )
    for text in texts:
        if not text:
            continue
        lower = text.lower()
        if any(m in lower for m in markers):
            return True
    return False


def raise_http(
    status_code: int,
    exc: BaseException,
    *,
    context: str = "",
    log: bool = True,
) -> None:
    """Log full details to file; raise HTTPException with a simplified detail string."""
    ctx = context or "api"
    detail = simplify_exception_message(exc, context=ctx)
    if _is_quota_or_rate_limit(detail, str(exc)):
        status_code = 429

    if log:
        log_error(ctx, exc)

    raise HTTPException(status_code=status_code, detail=detail) from exc
