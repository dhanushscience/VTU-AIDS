"""Diagnostic logging and bug-report helpers for VTU AIDS."""

from __future__ import annotations

import logging
import os
import platform
import sys
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

try:
    from app.paths import writable_root
except ModuleNotFoundError:
    from paths import writable_root

APP_VERSION = "2.1.1"
_RUN_ID_ENV = "VTU_AIDS_RUN_ID"
_CONFIGURED = False


class _RunIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = get_run_id()
        return True


def get_run_id() -> str:
    run_id = os.environ.get(_RUN_ID_ENV, "").strip()
    if run_id:
        return run_id
    run_id = uuid.uuid4().hex[:10]
    os.environ[_RUN_ID_ENV] = run_id
    return run_id


def configure_release_logging(component: str = "app") -> None:
    """Enable verbose release logging with run correlation IDs."""
    global _CONFIGURED
    root = logging.getLogger()
    if _CONFIGURED:
        logging.getLogger(__name__).debug("Logging already configured for component=%s", component)
        return
    writable_root().mkdir(parents=True, exist_ok=True)
    debug_log = writable_root() / "vtu_aids_debug.log"
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [run=%(run_id)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(debug_log, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(_RunIdFilter())

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.DEBUG)
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(_RunIdFilter())

    root.handlers.clear()
    root.setLevel(logging.DEBUG)
    root.addHandler(file_handler)
    root.addHandler(stream_handler)

    _CONFIGURED = True
    logging.getLogger(__name__).info(
        "Verbose logging enabled for %s (run_id=%s)", component, get_run_id()
    )


def log_files_for_bundle() -> list[Path]:
    base = writable_root()
    return [
        base / "vtu_aids_debug.log",
        base / "vtu_aids_error.log",
        base / "vtu_aids_startup.log",
        base / "bot_run.log",
        base / "bot_status.json",
    ]


def create_log_bundle() -> Path:
    """Zip core diagnostics files and return the bundle path."""
    base = writable_root()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    bundle = base / f"vtu_aids_logs_{stamp}.zip"
    with zipfile.ZipFile(bundle, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in log_files_for_bundle():
            if path.is_file():
                zf.write(path, arcname=path.name)
    return bundle


def issue_metadata() -> dict[str, str]:
    return {
        "app_version": APP_VERSION,
        "run_id": get_run_id(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
    }


def build_github_issue_url(*, title: str = "Bug report: ") -> str:
    meta = issue_metadata()
    body = (
        "## What happened\n"
        "<describe the issue>\n\n"
        "## Steps to reproduce\n"
        "1. \n2. \n3. \n\n"
        "## Expected behavior\n"
        "<what should happen>\n\n"
        "## Attach logs\n"
        "- In VTU AIDS Settings, click **Export logs**\n"
        "- Attach the generated `.zip` file to this issue\n\n"
        "## Diagnostics\n"
        f"- Version: {meta['app_version']}\n"
        f"- Run ID: {meta['run_id']}\n"
        f"- Platform: {meta['platform']}\n"
        f"- Python: {meta['python']}\n"
    )
    return (
        "https://github.com/dhanushscience/VTU-AIDS/issues/new"
        f"?title={quote_plus(title)}&body={quote_plus(body)}"
    )
