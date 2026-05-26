"""Runtime dependency checks for VTU AIDS."""

from __future__ import annotations

import sys


def genai_import_error() -> str | None:
    try:
        from google import genai  # noqa: F401
        return None
    except ImportError:
        exe = sys.executable
        return (
            "Google Gemini SDK (google-genai) is not installed.\n\n"
            f"Fix: run Install VTU AIDS.bat (recommended install folder: "
            f"%LOCALAPPDATA%\\VTU AIDS — not OneDrive Desktop).\n\n"
            f"Or in a terminal:\n  \"{exe}\" -m pip install -r requirements.txt"
        )


def import_genai():
    """Return the google.genai module or raise RuntimeError with install steps."""
    err = genai_import_error()
    if err:
        raise RuntimeError(err)
    from google import genai

    return genai


def dependency_status() -> dict[str, bool]:
    ok_genai = genai_import_error() is None
    ok_playwright = True
    try:
        import playwright  # noqa: F401
    except ImportError:
        ok_playwright = False
    return {
        "google_genai": ok_genai,
        "playwright": ok_playwright,
        "ready": ok_genai,
    }
