#!/usr/bin/env python3
"""
VTU AIDS — single entry point.

  Double-click / Run VTU AIDS.bat     → opens in your browser (most reliable)
  python vtu_aids.py                  → desktop window (pywebview)
  python vtu_aids.py --dev            → dev server + hot reload
  python vtu_aids.py --run-bot …      → Playwright automation
"""

from __future__ import annotations

import argparse
import os
import socket
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
import webbrowser

HOST = "127.0.0.1"
PORT = 8765
URL = f"http://{HOST}:{PORT}/"

# Reduces black-window issues with some GPU / WebView2 drivers on Windows.
os.environ.setdefault(
    "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS",
    "--disable-gpu --disable-gpu-compositing",
)

# Before any HTTPS (Gemini); avoids FileNotFoundError [Errno 2] from bad SSL_CERT_FILE.
try:
    from app.paths import ensure_ssl_certificates

    ensure_ssl_certificates()
except Exception:
    pass

def _ensure_stdio() -> None:
    """pythonw.exe sets stdout/stderr to None; uvicorn logging crashes without this."""
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")


def _has_tty() -> bool:
    try:
        return sys.stdout is not None and sys.stdout.isatty()
    except Exception:
        return False


def _show_error_box(message: str) -> None:
    _log("error: " + message.replace("\n", " ")[:400])
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, message[:2000], "VTU AIDS", 0x10)
    except Exception:
        pass


_SPLASH_HTML = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<style>
  html,body{margin:0;height:100%;background:#f4f4f5;color:#18181b;
    font-family:"Segoe UI",system-ui,sans-serif;display:flex;align-items:center;
    justify-content:center;flex-direction:column;gap:12px}
  .spin{width:36px;height:36px;border:3px solid #e4e4e7;border-top-color:#2563eb;
    border-radius:50%;animation:r .8s linear infinite}
  @keyframes r{to{transform:rotate(360deg)}}
</style></head><body>
<div class="spin"></div><p>Loading VTU AIDS…</p>
</body></html>"""


def _log(msg: str) -> None:
    try:
        from app.paths import writable_root

        path = writable_root() / "vtu_aids_startup.log"
        line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n"
        with path.open("a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def _error_html(message: str) -> str:
    safe = (
        message.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br>")
    )
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<style>
  body{{margin:0;padding:24px;font-family:"Segoe UI",system-ui,sans-serif;
    background:#f4f4f5;color:#18181b;line-height:1.5}}
  .box{{max-width:560px;margin:40px auto;padding:20px;background:#fff;
    border:1px solid #e4e4e7;border-radius:12px}}
</style></head><body><div class="box">
<h1>VTU AIDS could not start</h1><p>{safe}</p>
<p>Try <b>Run VTU AIDS (Browser).bat</b> or reinstall with Install VTU AIDS.bat.</p>
</div></body></html>"""


def _pick_port() -> int:
    """Use 8765, or next free port if something else is stuck on 8765."""
    global PORT, URL
    for candidate in (8765, 8766, 8767, 8768):
        try:
            with socket.create_connection((HOST, candidate), timeout=0.3):
                # Port in use — try HTTP to see if it is our app
                try:
                    test_url = f"http://{HOST}:{candidate}/"
                    with urllib.request.urlopen(test_url, timeout=1) as resp:
                        if resp.status == 200:
                            body = resp.read(256).decode("utf-8", errors="ignore").lower()
                            if "vtu aids" in body or "<html" in body:
                                PORT = candidate
                                URL = test_url
                                return candidate
                except Exception:
                    pass
                continue
        except OSError:
            PORT = candidate
            URL = f"http://{HOST}:{candidate}/"
            return candidate
    PORT = 8765
    URL = f"http://{HOST}:{PORT}/"
    return PORT


def _wait_for_server(timeout: float = 60.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            req = urllib.request.Request(URL, method="GET")
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    body = resp.read(800).decode("utf-8", errors="ignore").lower()
                    if "<html" in body or "vtu aids" in body:
                        return True
        except (urllib.error.URLError, OSError, TimeoutError):
            pass
        time.sleep(0.25)
    return False


def _run_uvicorn(*, reload: bool) -> None:
    from pathlib import Path

    from app.paths import is_frozen, static_dir, writable_root

    _ensure_stdio()
    try:
        if is_frozen() and not (static_dir() / "index.html").is_file():
            log = writable_root() / "vtu_aids_error.log"
            log.write_text(f"Missing static files at {static_dir()}\n", encoding="utf-8")

        if reload:
            repo = Path(__file__).resolve().parent.parent
            import uvicorn

            uvicorn.run(
                "app.main:app",
                host=HOST,
                port=PORT,
                reload=True,
                reload_dirs=[str(repo / "app"), str(repo / "static")],
                log_level="info",
                access_log=True,
            )
            return

        import uvicorn
        from app.main import app

        uvicorn.run(app, host=HOST, port=PORT, log_level="warning", access_log=False)
    except Exception:
        log = writable_root() / "vtu_aids_error.log"
        log.write_text(traceback.format_exc(), encoding="utf-8")
        raise


def _start_server_thread() -> None:
    t = threading.Thread(target=_run_uvicorn, kwargs={"reload": False}, daemon=True)
    t.start()


def run_browser() -> None:
    """Open the UI in the default system browser (recommended — avoids black WebView)."""
    from app.paths import configure_playwright_for_frozen, ensure_first_run_layout, load_dotenv
    from app.process_cleanup import reconcile_stale_automation

    _log("run_browser start")
    ensure_first_run_layout()
    reconcile_stale_automation()
    load_dotenv()
    configure_playwright_for_frozen()
    _pick_port()
    _start_server_thread()

    if not _wait_for_server():
        log_hint = ""
        try:
            from app.paths import writable_root

            p = writable_root() / "vtu_aids_error.log"
            if p.is_file():
                log_hint = f"\n\nSee: {p}"
        except Exception:
            pass
        raise SystemExit(
            "VTU AIDS server failed to start. Packages may be missing.\n"
            "Run Install VTU AIDS.bat and install to a folder outside OneDrive."
            + log_hint
        )

    launch_url = f"{URL}?v={int(time.time())}"
    webbrowser.open(launch_url)
    _log(f"browser opened {launch_url}")

    if _has_tty():
        print("VTU AIDS is running.")
        print(f"  {URL}")
        print("Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            from app.process_cleanup import shutdown_all

            shutdown_all()
        return

    # pythonw: keep server alive in background
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(
            0,
            f"VTU AIDS is open in your browser.\n\n{URL}\n\nClick OK to close the app.",
            "VTU AIDS",
            0x40,
        )
    except Exception:
        while True:
            time.sleep(3600)


def run_desktop() -> None:
    from app.paths import configure_playwright_for_frozen, ensure_first_run_layout, load_dotenv, writable_root
    from app.process_cleanup import reconcile_stale_automation

    _log("run_desktop start")
    ensure_first_run_layout()
    reconcile_stale_automation()
    load_dotenv()
    configure_playwright_for_frozen()
    _pick_port()
    _start_server_thread()

    if not _wait_for_server(timeout=60):
        log_path = writable_root() / "vtu_aids_error.log"
        msg = "Server failed to start."
        if log_path.is_file():
            msg += f"\n\n{log_path.read_text(encoding='utf-8')[-1500:]}"
        _log("server timeout: " + msg)
        raise SystemExit(
            msg + "\n\nUse Run VTU AIDS (Browser).bat instead, or run Install VTU AIDS.bat."
        )

    try:
        import webview
    except ImportError as e:
        raise SystemExit("Install pywebview: pip install pywebview") from e

    icon_path: str | None = None
    try:
        from app.paths import bundle_root

        for name in ("app.ico", "logo.png", "favicon.png"):
            candidate = bundle_root() / "static" / name
            if candidate.is_file():
                icon_path = str(candidate)
                break
    except Exception:
        pass

    window = webview.create_window(
        "VTU AIDS — Automated Internship Diary System",
        url=URL,
        width=1440,
        height=920,
        min_size=(1024, 680),
        text_select=True,
        background_color="#f4f4f5",
        icon=icon_path,
    )

    # Do NOT force edgechromium first — it often shows a black window without error.
    for gui in (None, "edgechromium"):
        try:
            label = gui or "default"
            _log(f"webview.start gui={label}")
            if gui:
                webview.start(gui=gui, debug=False)
            else:
                webview.start(debug=False)
            return
        except Exception as e:
            _log(f"webview failed gui={gui}: {e}")
            continue

    _log("webview failed, falling back to browser")
    webbrowser.open(URL)
    raise SystemExit(
        f"Desktop window could not start. Opened {URL} in your browser instead."
    )


def run_dev() -> None:
    from app.paths import load_dotenv

    load_dotenv()
    _pick_port()
    print("VTU AIDS — dev server")
    print(f"Web UI: {URL}")
    print("Press Ctrl+C to stop.")
    threading.Thread(
        target=lambda: (time.sleep(1.0), webbrowser.open(URL)),
        daemon=True,
    ).start()
    _run_uvicorn(reload=True)


def run_bot_cli(argv: list[str]) -> int:
    from app.paths import configure_playwright_for_frozen, load_dotenv, writable_root

    load_dotenv()
    configure_playwright_for_frozen()
    os.chdir(writable_root())
    sys.argv = ["app/run_diary_bot.py", *argv]
    from app.run_diary_bot import main as bot_main

    return int(bot_main())


def install_browser() -> int:
    print("Installing Playwright Chromium (may take a few minutes)…")
    try:
        from playwright.__main__ import main as playwright_main
    except ImportError:
        print("Playwright is not installed.")
        return 1
    sys.argv = ["playwright", "install", "chromium"]
    try:
        playwright_main()
        print("Done.")
        return 0
    except SystemExit as e:
        return int(e.code) if e.code is not None else 1


def main() -> int:
    _ensure_stdio()

    if len(sys.argv) > 1 and sys.argv[1] == "--run-bot":
        return run_bot_cli(sys.argv[2:])

    if len(sys.argv) > 1 and sys.argv[1] == "--install-browser":
        return install_browser()

    parser = argparse.ArgumentParser(description="VTU AIDS")
    parser.add_argument("--dev", action="store_true", help="Dev server + browser tab")
    parser.add_argument(
        "--browser",
        action="store_true",
        help="Open in system browser (recommended)",
    )
    parser.add_argument(
        "--desktop",
        action="store_true",
        help="Embedded desktop window (may show black on some PCs)",
    )
    args = parser.parse_args()

    try:
        if args.dev:
            run_dev()
            return 0
        if args.browser:
            run_browser()
            return 0
        if args.desktop:
            run_desktop()
            return 0
        run_browser()
        return 0
    except SystemExit as e:
        if e.code in (0, None):
            return 0
        msg = e.code if isinstance(e.code, str) else str(e.code)
        if not _has_tty():
            _show_error_box(msg)
        else:
            print(msg, file=sys.stderr)
        return 1
    except Exception:
        msg = traceback.format_exc()
        try:
            from app.paths import writable_root

            (writable_root() / "vtu_aids_error.log").write_text(msg, encoding="utf-8")
        except Exception:
            pass
        if not _has_tty():
            _show_error_box("VTU AIDS failed to start.\n\nSee vtu_aids_error.log in Local App Data\\VTU AIDS")
        else:
            print(msg, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
