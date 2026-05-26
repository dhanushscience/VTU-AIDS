"""Build static/app.ico and static/favicon.png from the current logo."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
ICO_OUT = STATIC / "app.ico"
FAVICON_OUT = STATIC / "favicon.png"


def _source_image() -> Path:
    for name in ("logo.png", "AIDS.png", "favicon.png"):
        path = STATIC / name
        if path.is_file():
            return path
    raise FileNotFoundError(f"No logo PNG found under {STATIC}")


def main() -> int:
    try:
        from PIL import Image
    except ImportError:
        print("Install Pillow: pip install pillow", file=sys.stderr)
        return 1

    src = _source_image()
    img = Image.open(src).convert("RGBA")
    img.save(
        ICO_OUT,
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    favicon = img.resize((32, 32), Image.Resampling.LANCZOS)
    favicon.save(FAVICON_OUT, format="PNG", optimize=True)
    print(f"Wrote {ICO_OUT} and {FAVICON_OUT} from {src.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
