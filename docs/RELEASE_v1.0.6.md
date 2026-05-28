# VTU AIDS v1.0.6

Release for easier installation, first-run setup, and reliable daily use.

**Platform:** Windows 10/11 (64-bit)

## Download

- Installer: [VTU_AIDS_Setup.exe](https://github.com/dhanushscience/VTU-AIDS/releases/download/v1.0.6/VTU_AIDS_Setup.exe)
- Size: **~483 MB** (includes Chromium for automation)

If Windows blocks install, see [windows.md](windows.md).

---

## Major improvements in v1.0.6

### 1) Desktop launch is default

- `VTU AIDS.exe` and `python vtu_aids.py` open desktop mode by default
- Start menu launch is aligned with desktop-first behavior

### 2) Browser fallback remains available

- If desktop window is black, run:
  - `python vtu_aids.py --browser`
  - `Run VTU AIDS (Browser).bat` (developer installs)

### 3) Installer flow is safer for restricted Windows PCs

- Setup no longer auto-runs app at finish
- Reduces confusion on policy-restricted systems where auto-run can be blocked

### 4) Student documentation is now comprehensive

- README rewritten with beginner flow, screenshots, privacy notes, FAQ
- INSTALL guide now has numbered practical walkthrough + "what you should see" cues
- Windows guide rewritten as simple troubleshooting reference

### 5) Prior fixes included

- v1.0.5 and v1.0.4 fixes are included in this release line

---

## Quick student flow

1. Install `VTU_AIDS_Setup.exe` (~483 MB)
2. Open VTU AIDS from Start menu
3. Complete setup wizard (Internyet + Gemini API key)
4. Daily use: Step 1 dates -> Step 2 prompt -> Step 3 review/upload

Detailed install help: [INSTALL.md](INSTALL.md)

---

## Notes and warnings

- Use only if your institution permits this workflow
- Not affiliated with VTU or Internyet
- Keep credentials private and follow your institution policy
