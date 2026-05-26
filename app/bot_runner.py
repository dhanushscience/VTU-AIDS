"""Run Playwright automation in a background thread (survives HTTP client timeouts)."""

from __future__ import annotations

import json
import os
import subprocess
import threading
import traceback
from datetime import datetime, timezone
from typing import Any

from app.paths import (
    bot_command,
    bot_working_directory,
    configure_playwright_for_frozen,
    config_path,
    entries_json_path,
    writable_root,
)

_lock = threading.Lock()


def _status_file() -> str:
    return str(writable_root() / "bot_status.json")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_status(data: dict[str, Any]) -> None:
    path = writable_root() / "bot_status.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_status() -> dict[str, Any]:
    path = writable_root() / "bot_status.json"
    if path.is_file():
        try:
            with path.open(encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"running": False, "ok": None, "exit_code": None, "stdout": "", "stderr": "", "error": None}


def _bot_env() -> dict[str, str]:
    configure_playwright_for_frozen()
    env = os.environ.copy()
    install_root = bot_working_directory()
    bundled = install_root / "ms-playwright"
    if bundled.is_dir():
        env["PLAYWRIGHT_BROWSERS_PATH"] = str(bundled)
    return env


def _run_subprocess(headed: bool, skip_on_error: bool) -> None:
    cmd = bot_command(
        [
            "--json",
            str(entries_json_path()),
            "--config",
            str(config_path()),
        ]
    )
    if headed:
        cmd.append("--headed")
    if skip_on_error:
        cmd.append("--skip-on-error")

    log_path = writable_root() / "bot_run.log"
    _write_status(
        {
            "running": True,
            "started_at": _now(),
            "finished_at": None,
            "ok": None,
            "exit_code": None,
            "stdout": "",
            "stderr": "",
            "error": None,
            "cmd": " ".join(cmd),
        }
    )
    try:
        with log_path.open("a", encoding="utf-8") as log:
            log.write(f"\n--- {_now()} ---\n")
            log.write(f"cmd: {' '.join(cmd)}\n")
            log.flush()
            proc = subprocess.run(
                cmd,
                cwd=str(bot_working_directory()),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=_bot_env(),
            )
            if proc.stdout:
                log.write(proc.stdout)
            if proc.stderr:
                log.write(proc.stderr)
            log.write(f"\nexit_code={proc.returncode}\n")
        _write_status(
            {
                "running": False,
                "started_at": get_status().get("started_at"),
                "finished_at": _now(),
                "ok": proc.returncode == 0,
                "exit_code": proc.returncode,
                "stdout": (proc.stdout or "")[-8000:],
                "stderr": (proc.stderr or "")[-8000:],
                "error": None,
            }
        )
    except Exception as e:
        tb = traceback.format_exc()
        try:
            with log_path.open("a", encoding="utf-8") as log:
                log.write(tb)
        except Exception:
            pass
        _write_status(
            {
                "running": False,
                "started_at": get_status().get("started_at"),
                "finished_at": _now(),
                "ok": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": tb[-8000:],
                "error": str(e),
            }
        )


def start_bot(*, headed: bool, skip_on_error: bool) -> dict[str, Any]:
    """Start automation if not already running."""
    with _lock:
        st = get_status()
        if st.get("running"):
            return {
                "ok": False,
                "started": False,
                "detail": "Automation is already running. Watch for the Chromium window.",
            }

    thread = threading.Thread(
        target=_run_subprocess,
        kwargs={"headed": headed, "skip_on_error": skip_on_error},
        daemon=True,
    )
    thread.start()
    return {
        "ok": True,
        "started": True,
        "message": "Automation started. A Chromium window should open shortly.",
    }
