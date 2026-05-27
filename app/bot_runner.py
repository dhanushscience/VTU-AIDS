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
from app.process_cleanup import (
    cleanup_playwright_chromium,
    is_process_alive,
    reconcile_stale_automation,
)

_lock = threading.Lock()
_active_bot_proc: subprocess.Popen[str] | None = None
_active_bot_lock = threading.Lock()


def _status_file() -> str:
    return str(writable_root() / "bot_status.json")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_status(data: dict[str, Any]) -> None:
    path = writable_root() / "bot_status.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _read_status() -> dict[str, Any]:
    """Read bot_status.json without side effects."""
    path = writable_root() / "bot_status.json"
    if path.is_file():
        try:
            with path.open(encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "running": False,
        "ok": None,
        "exit_code": None,
        "stdout": "",
        "stderr": "",
        "error": None,
    }


def _bot_pid_from_status(st: dict[str, Any]) -> int | None:
    pid = st.get("bot_pid")
    if isinstance(pid, str) and pid.isdigit():
        pid = int(pid)
    if isinstance(pid, int) and pid > 0:
        return pid
    return None


def _stale_status_view(st: dict[str, Any]) -> dict[str, Any]:
    """Read-only view when disk says running but the bot process is gone."""
    return {
        **st,
        "running": False,
        "stale": True,
        "ok": False,
        "exit_code": st.get("exit_code") if st.get("exit_code") is not None else -1,
        "stdout": "",
        "stderr": "",
        "error": st.get("error") or "Automation was interrupted (app closed or process ended).",
    }


def get_status() -> dict[str, Any]:
    """Return bot status without mutating disk or terminating processes."""
    st = _read_status()
    if not st.get("running"):
        return st

    # Freshly-started run: thread reserved the slot but child process PID not written yet.
    if st.get("starting") and _bot_pid_from_status(st) is None:
        return st

    pid = _bot_pid_from_status(st)
    if pid is not None and is_process_alive(pid):
        return st
    return _stale_status_view(st)


def terminate_running_bot() -> None:
    """Force-stop the automation subprocess if this app started it."""
    global _active_bot_proc
    with _active_bot_lock:
        proc = _active_bot_proc
    if proc is None or proc.poll() is not None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
            proc.wait(timeout=3)
        except Exception:
            pass
    finally:
        with _active_bot_lock:
            if _active_bot_proc is proc:
                _active_bot_proc = None


def _bot_env() -> dict[str, str]:
    configure_playwright_for_frozen()
    env = os.environ.copy()
    install_root = bot_working_directory()
    bundled = install_root / "ms-playwright"
    if bundled.is_dir():
        env["PLAYWRIGHT_BROWSERS_PATH"] = str(bundled)
    return env


def _run_subprocess(headed: bool, skip_on_error: bool) -> None:
    global _active_bot_proc
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
    started = _now()
    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    proc: subprocess.Popen[str] | None = None
    stdout = ""
    stderr = ""
    try:
        with _active_bot_lock:
            proc = subprocess.Popen(
                cmd,
                cwd=str(bot_working_directory()),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=_bot_env(),
                creationflags=creationflags,
            )
            _active_bot_proc = proc

        _write_status(
            {
                "running": True,
                "starting": False,
                "started_at": started,
                "finished_at": None,
                "ok": None,
                "exit_code": None,
                "stdout": "",
                "stderr": "",
                "error": None,
                "cmd": " ".join(cmd),
                "bot_pid": proc.pid,
            }
        )

        with log_path.open("a", encoding="utf-8") as log:
            log.write(f"\n--- {started} ---\n")
            log.write(f"cmd: {' '.join(cmd)}\n")
            log.write(f"bot_pid={proc.pid}\n")
            log.flush()
            stdout, stderr = proc.communicate()
            if stdout:
                log.write(stdout)
            if stderr:
                log.write(stderr)
            log.write(f"\nexit_code={proc.returncode}\n")

        _write_status(
            {
                "running": False,
                "started_at": started,
                "finished_at": _now(),
                "ok": proc.returncode == 0,
                "exit_code": proc.returncode,
                "stdout": (stdout or "")[-8000:],
                "stderr": (stderr or "")[-8000:],
                "error": None,
                "bot_pid": proc.pid,
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
                "started_at": started,
                "finished_at": _now(),
                "ok": False,
                "exit_code": -1,
                "stdout": (stdout or "")[-8000:],
                "stderr": tb[-8000:],
                "error": str(e),
                "bot_pid": proc.pid if proc is not None else None,
            }
        )
    finally:
        with _active_bot_lock:
            if proc is not None and _active_bot_proc is proc:
                _active_bot_proc = None
        # Headed runs can leave ms-playwright Chromium orphans even on exit code 0.
        if headed and proc is not None and proc.poll() is not None:
            cleanup_playwright_chromium()


def start_bot(*, headed: bool, skip_on_error: bool) -> dict[str, Any]:
    """Start automation if not already running."""
    with _lock:
        reconcile_stale_automation()
        st = _read_status()
        if st.get("running"):
            return {
                "ok": False,
                "started": False,
                "detail": "Automation is already running. Watch for the Chromium window.",
            }

        started = _now()
        _write_status(
            {
                "running": True,
                "starting": True,
                "started_at": started,
                "finished_at": None,
                "ok": None,
                "exit_code": None,
                "stdout": "",
                "stderr": "",
                "error": None,
                "cmd": "",
                "bot_pid": None,
            }
        )

        thread = threading.Thread(
            target=_run_subprocess,
            kwargs={"headed": headed, "skip_on_error": skip_on_error},
            daemon=True,
        )
        try:
            thread.start()
        except Exception:
            _write_status(
                {
                    "running": False,
                    "started_at": started,
                    "finished_at": _now(),
                    "ok": False,
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": "",
                    "error": "Failed to start automation thread.",
                    "cmd": "",
                    "bot_pid": None,
                }
            )
            raise

    return {
        "ok": True,
        "started": True,
        "message": "Automation started. A Chromium window will open in front (view only).",
    }
