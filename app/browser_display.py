"""Headed Chromium: bring to front once, view-only for the user (window chrome still works)."""

from __future__ import annotations

import ctypes
import logging
import sys
import time
from ctypes import wintypes

from playwright.sync_api import Browser, BrowserContext, Page

LOGGER = logging.getLogger(__name__)

_DISPLAY_ONLY_INIT = """
(() => {
  if (window.__vtuAidsDisplayOnly) return;
  const state = { installed: false };
  const install = () => {
    if (!document.documentElement) return;
    let root = document.getElementById("vtu-aids-display-only-root");
    if (!root) {
      root = document.createElement("div");
      root.id = "vtu-aids-display-only-root";
      root.setAttribute("aria-hidden", "true");
      Object.assign(root.style, {
        position: "fixed",
        inset: "0",
        zIndex: "2147483646",
        pointerEvents: "auto",
        background: "transparent",
        cursor: "default",
      });
      const banner = document.createElement("div");
      banner.id = "vtu-aids-display-only-banner";
      Object.assign(banner.style, {
        position: "fixed",
        top: "8px",
        left: "50%",
        transform: "translateX(-50%)",
        padding: "6px 14px",
        borderRadius: "8px",
        background: "rgba(15, 23, 42, 0.88)",
        color: "#f8fafc",
        font: "600 12px/1.35 system-ui, Segoe UI, sans-serif",
        letterSpacing: "0.02em",
        boxShadow: "0 4px 16px rgba(0,0,0,0.25)",
        pointerEvents: "none",
        userSelect: "none",
        whiteSpace: "nowrap",
      });
      banner.textContent =
        "VTU AIDS automation — view only (you can minimize, maximize, or close this window)";
      root.appendChild(banner);
      const block = (e) => {
        if (!e.isTrusted) return;
        e.preventDefault();
        e.stopImmediatePropagation();
      };
      for (const type of [
        "click", "dblclick", "mousedown", "mouseup", "pointerdown", "pointerup",
        "contextmenu", "wheel", "keydown", "keyup", "keypress",
      ]) {
        root.addEventListener(type, block, true);
      }
      (document.documentElement || document.body).appendChild(root);
      state.installed = true;
    }
  };
  install();
  new MutationObserver(install).observe(document.documentElement, {
    childList: true,
    subtree: true,
  });
  window.__vtuAidsDisplayOnly = { install, state };
})();
"""

_patched_force_click = False


def _patch_playwright_force_clicks() -> None:
    """Let Playwright click/fill through the view-only overlay (force=True)."""
    global _patched_force_click
    if _patched_force_click:
        return
    from playwright.sync_api import Locator, Page

    def _with_force(orig):
        def wrapper(self, *args, **kwargs):
            if "force" not in kwargs:
                kwargs["force"] = True
            return orig(self, *args, **kwargs)

        return wrapper

    Locator.click = _with_force(Locator.click)  # type: ignore[method-assign]
    Locator.dblclick = _with_force(Locator.dblclick)  # type: ignore[method-assign]
    Page.click = _with_force(Page.click)  # type: ignore[method-assign]
    Page.dblclick = _with_force(Page.dblclick)  # type: ignore[method-assign]
    _patched_force_click = True


def configure_headed_automation_browser(
    browser: Browser,
    context: BrowserContext,
    page: Page,
) -> None:
    """View-only overlay, force clicks for bot, bring Chromium to front once (Windows)."""
    _patch_playwright_force_clicks()
    context.add_init_script(_DISPLAY_ONLY_INIT)
    try:
        page.evaluate(_DISPLAY_ONLY_INIT)
    except Exception as e:
        LOGGER.debug("Display-only overlay install skipped: %s", e)
    try:
        focus_automation_window(browser)
    except Exception as e:
        LOGGER.warning("Could not focus automation browser window: %s", e)


def release_headed_automation_browser(browser: Browser | None) -> None:
    """No-op (kept for callers); window is not kept always-on-top."""
    del browser


def focus_automation_window(
    browser: Browser | None = None,
    *,
    retries: int = 30,
    interval: float = 0.12,
) -> None:
    """Bring the Playwright Chromium window to the front once (not persistent topmost)."""
    if sys.platform != "win32":
        return
    for _attempt in range(retries):
        hwnd = _find_chromium_hwnd(browser)
        if hwnd:
            _bring_hwnd_to_front(hwnd)
            LOGGER.info("Automation browser window focused (hwnd=%s).", hwnd)
            return
        time.sleep(interval)
    LOGGER.warning("Could not find automation Chromium window to focus.")


# --- Windows helpers -----------------------------------------------------------------


def _win_user32():
    return ctypes.WinDLL("user32", use_last_error=True)


def _win_kernel32():
    return ctypes.WinDLL("kernel32", use_last_error=True)


def _browser_pids(browser: Browser | None) -> set[int]:
    """Collect browser PIDs when Playwright exposes them (optional on some builds)."""
    pids: set[int] = set()
    if browser is None:
        return pids
    proc = getattr(browser, "process", None)
    if proc is None:
        impl = getattr(browser, "_impl_obj", None)
        if impl is not None:
            proc = getattr(impl, "_browser_process", None)
            if proc is None:
                connection = getattr(impl, "_connection", None)
                if connection is not None:
                    proc = getattr(connection, "_browser_process", None)
    pid = getattr(proc, "pid", None) if proc is not None else None
    if pid:
        root = int(pid)
        pids.add(root)
        if sys.platform == "win32":
            pids.update(_child_pids_win(root))
    return pids


def _child_pids_win(parent_pid: int) -> set[int]:
    """Direct child process IDs (Chromium GPU/renderer processes)."""
    children: set[int] = set()
    try:
        TH32CS_SNAPPROCESS = 0x00000002
        kernel32 = _win_kernel32()
        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", wintypes.LONG),
                ("dwFlags", wintypes.DWORD),
                ("szExeFile", wintypes.WCHAR * 260),
            ]

        snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if snap == ctypes.c_void_p(-1).value:
            return children
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        if not kernel32.Process32FirstW(snap, ctypes.byref(entry)):
            kernel32.CloseHandle(snap)
            return children
        while True:
            if int(entry.th32ParentProcessID) == parent_pid:
                children.add(int(entry.th32ProcessID))
            if not kernel32.Process32NextW(snap, ctypes.byref(entry)):
                break
        kernel32.CloseHandle(snap)
    except Exception as e:
        LOGGER.debug("Child PID enumeration failed: %s", e)
    return children


def _process_image_path(pid: int) -> str:
    if sys.platform != "win32":
        return ""
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    kernel32 = _win_kernel32()
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(32768)
        size = wintypes.DWORD(len(buf))
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return buf.value
    finally:
        kernel32.CloseHandle(handle)
    return ""


def _is_playwright_chromium_exe(exe: str) -> bool:
    lower = exe.lower()
    return "ms-playwright" in lower or ("playwright" in lower and "chrome" in lower)


def _find_chromium_hwnd(browser: Browser | None = None) -> int | None:
    if sys.platform != "win32":
        return None

    pids = _browser_pids(browser)
    user32 = _win_user32()
    best_hwnd: int | None = None
    best_area = 0

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _lparam):
        nonlocal best_hwnd, best_area
        if not user32.IsWindowVisible(hwnd):
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        exe = _process_image_path(pid.value).lower()
        if pid.value not in pids and not _is_playwright_chromium_exe(exe):
            return True

        class_buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_buf, 256)
        if class_buf.value != "Chrome_WidgetWin_1":
            return True

        owner = user32.GetWindow(hwnd, 4)  # GW_OWNER
        if owner:
            return True

        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        area = max(0, rect.right - rect.left) * max(0, rect.bottom - rect.top)
        if area > best_area:
            best_area = area
            best_hwnd = int(hwnd)
        return True

    user32.EnumWindows(callback, 0)
    return best_hwnd


def _bring_hwnd_to_front(hwnd: int) -> None:
    """Flash topmost briefly so the window comes forward once, then drop topmost."""
    user32 = _win_user32()
    SW_RESTORE = 9
    HWND_TOPMOST = -1
    HWND_NOTOPMOST = -2
    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001
    SWP_SHOWWINDOW = 0x0040

    try:
        user32.AllowSetForegroundWindow(0xFFFFFFFF)
    except Exception:
        pass

    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetWindowPos(
        hwnd,
        HWND_TOPMOST,
        0,
        0,
        0,
        0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
    )
    user32.SetWindowPos(
        hwnd,
        HWND_NOTOPMOST,
        0,
        0,
        0,
        0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
    )
    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)
