# PyInstaller spec — build from repo root:
#   pyinstaller build/VTU_AIDS.spec

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

block_cipher = None
# SPEC = absolute path to this .spec file (PyInstaller built-in)
ROOT = Path(SPEC).resolve().parent.parent
VERSION_FILE = ROOT / "build" / "version_info.txt"

datas = [
    (str(ROOT / "static"), "static"),
    (str(ROOT / "app"), "app"),
    (str(ROOT / "VTU_skills.txt"), "."),
    (str(ROOT / "student_config.example.json"), "."),
    (str(ROOT / ".env.example"), "."),
    (str(ROOT / "generated" / "entries.sample.json"), "generated"),
    (str(ROOT / "generated" / "entries.schema.json"), "generated"),
]

_genai_datas, _genai_binaries, _genai_hidden = collect_all("google.genai")

from PyInstaller.utils.hooks import collect_data_files as _collect_data

import certifi
certifi_cacert = certifi.where()

# collect_data_files is more reliable than a single (src, dest) tuple —
# it picks up all data files certifi ships, preventing empty-folder builds.
_certifi_datas = _collect_data("certifi")

hiddenimports = [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "webview",
    "google",
    "google.genai",
    "google.genai.errors",
    "google.genai.types",
    "google.auth",
    "pypdf",
    "docx",
    "pptx",
    "multipart",
    "playwright",
    "playwright.sync_api",
    "pandas",
    "openpyxl",
    *_genai_hidden,
]

datas = [
    *datas,
    *_genai_datas,
    *_certifi_datas,
    (certifi_cacert, "certifi"),
]

a = Analysis(
    [str(ROOT / "app" / "cli.py"), str(ROOT / "app" / "run_diary_bot.py")],
    pathex=[str(ROOT)],
    binaries=[*_genai_binaries],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VTU AIDS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(
        ROOT / "static" / "app.ico"
        if (ROOT / "static" / "app.ico").is_file()
        else ROOT / "static" / "favicon.png"
    )
    if (ROOT / "static" / "app.ico").is_file() or (ROOT / "static" / "favicon.png").is_file()
    else None,
    version=str(VERSION_FILE) if VERSION_FILE.is_file() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="VTU AIDS",
)
