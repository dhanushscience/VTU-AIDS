# VTU AIDS v1.0.5

**Release date:** May 2026  
**Platform:** Windows 10/11 (64-bit)

## Download

| File | Size (approx.) | Notes |
|------|----------------|-------|
| [VTU_AIDS_Setup.exe](https://github.com/dhanushscience/VTU-AIDS/releases/download/v1.0.5/VTU_AIDS_Setup.exe) | ~277 MB | Recommended - includes Chromium for automation |

If **Smart App Control** blocks the installer, see [docs/windows.md](windows.md) or `SMART_APP_CONTROL.txt` in the install folder.

---

## Highlights

### Calendar submission marking fixes
- Submitted entries now mark green reliably in the Step 1 calendar.
- Date normalization is handled consistently (`date`/`Date`) across preview loading and calendar lookups.
- Submitted-state refresh is triggered after successful automation so users can see status without manual file checks.

### Automation success UX polish
- After a successful run, UI now shows a short completion message instead of full raw logs.
- Added a `Done` button below the status area to refresh once and sync the latest state.

### Script-mode stability fixes
- Fixed additional script-mode import fallbacks in automation archive and cleanup paths.
- Successful automation now archives submitted rows correctly even when run outside package mode.

### BOM-safe JSON loading
- `entries_store` now reads JSON with BOM-safe decoding (`utf-8-sig`) to avoid preview/save crashes on BOM-encoded files.

---

## Install (end users)

1. Download **VTU_AIDS_Setup.exe** from [Releases](https://github.com/dhanushscience/VTU-AIDS/releases/tag/v1.0.5).
2. Run the installer and open **VTU AIDS** from the Start menu.
3. Complete the setup wizard (Internyet login + [Gemini API key](https://aistudio.google.com/apikey)).
4. **Step 1** dates -> **Step 2** work summary -> **Generate with AI** -> **Step 3** **Run automation**.

Full guide: [docs/INSTALL.md](INSTALL.md)

---

## Upgrade from v1.0.4

- Install over the previous version (uninstall first is optional).
- Your config in `%LOCALAPPDATA%\VTU AIDS\` is kept.
- Hard refresh the browser tab once (`Ctrl+Shift+R`) after upgrading.

---

## GitHub release body (copy-paste)

```markdown
## VTU AIDS v1.0.5

Automated Internship Diary System for [VTU Internyet](https://vtu.internyet.in).

### What's new
- **Submitted date marking fixed** - successful automation now updates green calendar state reliably
- **Automation success UX improved** - short status message + `Done` refresh action
- **Script-mode robustness** - additional import fallbacks for archive/cleanup paths
- **BOM-safe JSON loading** - avoids `Unexpected UTF-8 BOM` crashes in preview/save flows

### Download
- **VTU_AIDS_Setup.exe** (~277 MB, Windows 10/11, includes Chromium)

### Quick start
1. Install and open **VTU AIDS**
2. Complete setup wizard
3. Select dates -> describe work -> **Generate with AI** -> **Run automation**

📖 [Installation guide](https://github.com/dhanushscience/VTU-AIDS/blob/main/docs/INSTALL.md) · [Release notes](https://github.com/dhanushscience/VTU-AIDS/blob/main/docs/RELEASE_v1.0.5.md)

> Use only if permitted by your institution. Not affiliated with VTU or Internyet.
```
