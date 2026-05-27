"""Kill orphan bot/Chromium processes and reset stale state after force-close."""

from __future__ import annotations

import atexit
import json
import logging
import signal
import subprocess
import sys
import threading
from typing import Any

LOGGER = logging.getLogger(__name__)

_shutdown_lock = threading.Lock()
_shutdown_done = False
_handlers_installed = False


def cleanup_playwright_chromium() -> None:
    """Stop headed Chromium from Playwright (ms-playwright paths only)."""
    if sys.platform != "win32":
        return
    ps = (
        "Get-CimInstance Win32_Process -Filter \"name='chrome.exe'\" -ErrorAction SilentlyContinue | "
        "Where-Object { $_.ExecutablePath -like '*ms-playwright*' } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True,
            timeout=12,
            check=False,
        )
        LOGGER.info("Playwright Chromium cleanup finished.")
    except Exception as e:
        LOGGER.debug("Playwright Chromium cleanup skipped: %s", e)


def is_process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        handle = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid
        )
        if not handle:
            return False
        try:
            code = wintypes.DWORD()
            if not ctypes.windll.kernel32.GetExitCodeProcess(
                handle, ctypes.byref(code)
            ):
                return False
            return int(code.value) == STILL_ACTIVE
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    try:
        import os

        os.kill(pid, 0)
        return True
    except OSError:
        return False


def terminate_process_tree(pid: int) -> None:
    """Force-stop a process and its children (Windows: taskkill /T)."""
    if pid <= 0:
        return
    if sys.platform == "win32":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                timeout=20,
                check=False,
            )
            return
        except Exception as e:
            LOGGER.debug("taskkill failed for pid %s: %s", pid, e)
    try:
        import os

        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass


def _read_bot_status_file() -> dict[str, Any]:
    from app.paths import writable_root

    path = writable_root() / "bot_status.json"
    if not path.is_file():
        return {}
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _write_bot_status_cleared(st: dict[str, Any], *, reason: str) -> None:
    from datetime import datetime, timezone

    from app.paths import writable_root

    path = writable_root() / "bot_status.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    finished = datetime.now(timezone.utc).isoformat()
    data = {
        **st,
        "running": False,
        "finished_at": finished,
        "ok": False,
        "exit_code": st.get("exit_code") if st.get("exit_code") is not None else -1,
        "error": reason,
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def reconcile_stale_automation() -> bool:
    """
    If bot_status says running but the bot process is gone, reset status and clean Chromium.
    Returns True if stale state was cleared.
    """
    st = _read_bot_status_file()
    if not st.get("running"):
        return False

    pid = st.get("bot_pid")
    if isinstance(pid, str) and pid.isdigit():
        pid = int(pid)
    if not isinstance(pid, int):
        pid = None

    if pid and is_process_alive(pid):
        return False

    LOGGER.info("Stale automation state detected — cleaning up (bot_pid=%s).", pid)
    if pid:
        terminate_process_tree(pid)
    cleanup_playwright_chromium()
    _write_bot_status_cleared(
        st,
        reason="Automation was interrupted (app closed or process ended).",
    )
    return True


def terminate_active_bot_subprocess() -> None:
    """Stop the in-process bot child started by bot_runner, if any."""
    try:
        from app import bot_runner

        bot_runner.terminate_running_bot()
    except Exception as e:
        LOGGER.debug("terminate_running_bot: %s", e)

    st = _read_bot_status_file()
    pid = st.get("bot_pid")
    if isinstance(pid, str) and pid.isdigit():
        pid = int(pid)
    if isinstance(pid, int) and pid > 0:
        terminate_process_tree(pid)


def shutdown_all() -> None:
    """Idempotent cleanup: stop bot subprocess, Chromium, clear stale running flag."""
    global _shutdown_done
    with _shutdown_lock:
        if _shutdown_done:
            return
        _shutdown_done = True

    LOGGER.info("VTU AIDS shutdown cleanup starting.")
    terminate_active_bot_subprocess()
    cleanup_playwright_chromium()
    st = _read_bot_status_file()
    if st.get("running"):
        _write_bot_status_cleared(
            st,
            reason="Application closed.",
        )


def _signal_handler(signum: int, _frame: object) -> None:
    shutdown_all()
    raise SystemExit(0)


def _install_win_console_handler() -> None:
    import ctypes
    from ctypes import wintypes

    HandlerRoutine = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)

    @HandlerRoutine
    def _handler(ctrl_type: int) -> bool:
        # CTRL_CLOSE, logoff, shutdown — user closed console or ended task gently
        if ctrl_type in (0, 1, 2, 5, 6):
            shutdown_all()
        return False

    ctypes.windll.kernel32.SetConsoleCtrlHandler(_handler, True)


def install_shutdown_handlers() -> None:
    """Register cleanup on normal exit, Ctrl+C, and console close (once only)."""
    global _handlers_installed
    with _shutdown_lock:
        if _handlers_installed:
            return
        _handlers_installed = True

    atexit.register(shutdown_all)
    if sys.platform == "win32":
        try:
            _install_win_console_handler()
        except Exception as e:
            LOGGER.debug("Console ctrl handler not installed: %s", e)
    for sig in (getattr(signal, "SIGTERM", None), getattr(signal, "SIGINT", None)):
        if sig is None:
            continue
        try:
            signal.signal(sig, _signal_handler)
        except Exception:
            pass
