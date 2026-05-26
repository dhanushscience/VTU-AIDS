"""Resolve bundle and writable paths (dev tree vs PyInstaller desktop .exe)."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

_APP_DATA_DIR = "VTU AIDS"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def project_root() -> Path:
    """Source / install folder (may be on OneDrive)."""
    return Path(__file__).resolve().parent.parent


def bundle_root() -> Path:
    """Read-only packaged assets (static, VTU_skills.txt, samples)."""
    if is_frozen():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        internal = Path(sys.executable).resolve().parent / "_internal"
        if internal.is_dir():
            return internal
    return project_root()


def _app_data_root() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / _APP_DATA_DIR
    base.mkdir(parents=True, exist_ok=True)
    return base


def _migrate_legacy_writable(legacy: Path, target: Path) -> None:
    """One-time copy of config/data from project folder to fast local AppData."""
    marker = target / ".migrated_from_project"
    if marker.is_file():
        return

    pairs: list[tuple[Path, Path]] = [
        (legacy / "student_config.json", target / "student_config.json"),
        (legacy / ".env", target / ".env"),
        (legacy / "generated" / "entries.json", target / "generated" / "entries.json"),
        (legacy / "generated" / "entries.xlsx", target / "generated" / "entries.xlsx"),
    ]
    for src, dst in pairs:
        if src.is_file() and not dst.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    marker.write_text(str(legacy.resolve()), encoding="utf-8")


def writable_root() -> Path:
    """Config, generated JSON, logs — always under LOCALAPPDATA (fast; avoids OneDrive locks)."""
    base = _app_data_root()
    if not is_frozen():
        _migrate_legacy_writable(project_root(), base)
    return base


def static_dir() -> Path:
    return bundle_root() / "static"


def skills_path() -> Path:
    return bundle_root() / "VTU_skills.txt"


def config_path() -> Path:
    return writable_root() / "student_config.json"


def generated_dir() -> Path:
    d = writable_root() / "generated"
    d.mkdir(parents=True, exist_ok=True)
    return d


def entries_json_path() -> Path:
    return generated_dir() / "entries.json"


def submitted_entries_json_path() -> Path:
    return generated_dir() / "submitted_entries.json"


def entries_excel_path() -> Path:
    return generated_dir() / "entries.xlsx"


def env_file_path() -> Path:
    return writable_root() / ".env"


def bot_script_path() -> Path:
    if is_frozen():
        return Path(sys.executable)
    return project_root() / "app" / "run_diary_bot.py"


def bot_working_directory() -> Path:
    """Folder the Playwright bot should use as cwd (install dir, not AppData)."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return project_root()


def bot_python_executable() -> str:
    """Use python.exe for subprocesses (pythonw hides errors and can block headed runs)."""
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe":
        py = exe.with_name("python.exe")
        if py.is_file():
            return str(py)
    return str(exe)


def bot_command(extra_args: list[str]) -> list[str]:
    """Argv to spawn the Playwright bot (same .exe when packaged)."""
    if is_frozen():
        return [str(Path(sys.executable)), "--run-bot", *extra_args]
    return [bot_python_executable(), str(bot_script_path()), *extra_args]


def ensure_first_run_layout() -> None:
    """Create writable folders and default config on first desktop launch."""
    ensure_ssl_certificates()
    generated_dir()
    cfg = config_path()
    if not cfg.is_file():
        legacy = project_root() / "student_config.json"
        if legacy.is_file():
            shutil.copy2(legacy, cfg)
        else:
            example = bundle_root() / "student_config.example.json"
            if example.is_file():
                shutil.copy2(example, cfg)
            else:
                cfg.write_text(
                    '{\n  "username": "",\n  "password": "",\n  "gemini_api_key": ""\n}\n',
                    encoding="utf-8",
                )
    env_example = bundle_root() / ".env.example"
    env_dst = env_file_path()
    if env_example.is_file() and not env_dst.is_file():
        shutil.copy2(env_example, env_dst)


def ensure_ssl_certificates() -> None:
    """Fix [Errno 2] from Gemini/httpx when SSL_CERT_FILE points at a missing CA bundle."""
    for var in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
        val = os.environ.get(var, "").strip().strip('"').strip("'")
        if val and not Path(val).is_file():
            os.environ.pop(var, None)

    ca_path = None
    if is_frozen():
        # PyInstaller may place certifi data in _MEIPASS/certifi/ or next to
        # the exe under _internal/certifi/ — check all plausible locations.
        meipass = Path(getattr(sys, "_MEIPASS"))
        exe_dir = Path(sys.executable).resolve().parent
        candidates = [
            meipass / "certifi" / "cacert.pem",
            exe_dir / "_internal" / "certifi" / "cacert.pem",
            exe_dir / "certifi" / "cacert.pem",
        ]
        for candidate in candidates:
            if candidate.is_file():
                ca_path = str(candidate)
                break

    if not ca_path:
        try:
            import certifi
            ca_path = certifi.where()
        except ImportError:
            pass

    if ca_path and Path(ca_path).is_file():
        os.environ["SSL_CERT_FILE"] = ca_path
        os.environ["REQUESTS_CA_BUNDLE"] = ca_path


def load_dotenv() -> None:
    env = env_file_path()
    if not env.is_file():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def configure_playwright_for_frozen() -> None:
    if not is_frozen():
        return
    exe_dir = Path(sys.executable).resolve().parent
    for candidate in (exe_dir / "ms-playwright", bundle_root() / "ms-playwright"):
        if candidate.is_dir():
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(candidate)
            return
