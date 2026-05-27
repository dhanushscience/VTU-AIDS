# VTU AIDS v1.0.6

**Release date:** May 2026  
**Platform:** Windows 10/11 (64-bit)

## Download

| File | Size (approx.) | Notes |
|------|----------------|-------|
| [VTU_AIDS_Setup.exe](https://github.com/dhanushscience/VTU-AIDS/releases/download/v1.0.6/VTU_AIDS_Setup.exe) | ~277 MB | Recommended — includes Chromium for automation |

If **Smart App Control** blocks the installer, see [docs/windows.md](windows.md) or `SMART_APP_CONTROL.txt` in the install folder.

---

## Highlights

### Desktop mode is now the default
- `python vtu_aids.py` and **VTU AIDS.exe** (no flags) open the embedded desktop window.
- Installer Start menu and optional desktop shortcut launch desktop mode automatically.
- Dev launchers (`Run VTU AIDS.bat`) use `--desktop`; **Run VTU AIDS (Browser).bat** remains for fallback.

### Documentation updates
- README, INSTALL, and Windows guides reflect desktop-first launch and browser fallback.

### Carried forward from v1.0.5
- Submitted date green marking, automation success UX (`Done` button), script-mode import fixes, BOM-safe JSON loading, and all v1.0.4 setup/error/automation improvements.

---

## Install (end users)

1. Download **VTU_AIDS_Setup.exe** from [Releases](https://github.com/dhanushscience/VTU-AIDS/releases/tag/v1.0.6).
2. Run the installer and open **VTU AIDS** from the Start menu (desktop window).
3. Complete the setup wizard (Internyet login + [Gemini API key](https://aistudio.google.com/apikey)).
4. **Step 1** dates → **Step 2** work summary → **Generate with AI** → **Step 3** **Run automation**.

Full guide: [docs/INSTALL.md](INSTALL.md)

---

## Upgrade from v1.0.5

- Install over the previous version (uninstall first is optional).
- Your config in `%LOCALAPPDATA%\VTU AIDS\` is kept.
- If the UI looks cached after upgrade, hard refresh once (`Ctrl+Shift+R`) when using browser fallback mode.

---

## GitHub release body (copy-paste)

```markdown
## VTU AIDS v1.0.6

Automated Internship Diary System for [VTU Internyet](https://vtu.internyet.in).

### What's new
- **Desktop mode default** — installer and `VTU AIDS.exe` open the embedded app window (no browser tab required)
- **Launchers updated** — dev `.bat` files and docs match desktop-first; browser mode kept as fallback
- **Includes v1.0.5 fixes** — green submitted dates, success UX, script-mode stability, BOM-safe JSON

### Download
- **VTU_AIDS_Setup.exe** (~277 MB, Windows 10/11, includes Chromium)

### Quick start
1. Install and open **VTU AIDS** from the Start menu
2. Complete setup wizard
3. Select dates → describe work → **Generate with AI** → **Run automation**

📖 [Installation guide](https://github.com/dhanushscience/VTU-AIDS/blob/main/docs/INSTALL.md) · [Release notes](https://github.com/dhanushscience/VTU-AIDS/blob/main/docs/RELEASE_v1.0.6.md)

> Use only if permitted by your institution. Not affiliated with VTU or Internyet.
```
