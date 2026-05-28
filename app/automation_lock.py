"""Cross-process lock so only one Playwright automation run controls the portal at a time."""

from __future__ import annotations

import logging
import os
from pathlib import Path

try:
    from app.paths import writable_root
    from app.process_cleanup import is_process_alive
except ModuleNotFoundError:
    from paths import writable_root
    from process_cleanup import is_process_alive

LOGGER = logging.getLogger(__name__)


def automation_lock_path() -> Path:
    return writable_root() / "automation.lock"


def _read_lock_pid(path: Path) -> int | None:
    try:
        raw = path.read_text(encoding="utf-8").strip()
        pid = int(raw.split()[0])
        return pid if pid > 0 else None
    except (OSError, ValueError):
        return None


def _status_says_running() -> tuple[bool, str]:
    """Check bot_status.json from the desktop app subprocess launcher."""
    status_path = writable_root() / "bot_status.json"
    if not status_path.is_file():
        return False, ""
    try:
        import json

        with status_path.open(encoding="utf-8") as f:
            st = json.load(f)
    except (OSError, json.JSONDecodeError):
        return False, ""
    if not st.get("running"):
        return False, ""
    pid = st.get("bot_pid")
    if isinstance(pid, str) and pid.isdigit():
        pid = int(pid)
    me = os.getpid()
    if isinstance(pid, int) and pid > 0 and pid != me and is_process_alive(pid):
        return True, f"UI automation already running (pid={pid})."
    return False, ""


def acquire_automation_lock() -> None:
    """Raise RuntimeError if another automation process is already active."""
    running, detail = _status_says_running()
    if running:
        raise RuntimeError(
            f"{detail} Wait for it to finish or stop it from Settings before starting another run."
        )

    path = automation_lock_path()
    holder = _read_lock_pid(path)
    if holder is not None and holder != os.getpid() and is_process_alive(holder):
        raise RuntimeError(
            f"Another automation process is already running (pid={holder}). "
            "Close the other Chromium window or wait for it to finish."
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{os.getpid()}\n", encoding="utf-8")
    LOGGER.debug("Acquired automation lock (pid=%s).", os.getpid())


def release_automation_lock() -> None:
    path = automation_lock_path()
    holder = _read_lock_pid(path)
    if holder is not None and holder != os.getpid():
        return
    try:
        path.unlink(missing_ok=True)
        LOGGER.debug("Released automation lock.")
    except OSError as e:
        LOGGER.debug("Could not remove automation lock: %s", e)
