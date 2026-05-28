# VTU AIDS v1.0.4

**Release date:** May 2026  
**Platform:** Windows 10/11 (64-bit)

## Download

| File | Size (approx.) | Notes |
|------|----------------|-------|
| [VTU_AIDS_Setup.exe](https://github.com/dhanushscience/VTU-AIDS/releases/download/v1.0.4/VTU_AIDS_Setup.exe) | ~483 MB | Recommended — includes Chromium for automation |

If **Smart App Control** blocks the installer, see [docs/windows.md](windows.md) or `SMART_APP_CONTROL.txt` in the install folder.

---

## Highlights

### First-run setup wizard
Mandatory 3-step wizard on first launch (or when credentials are missing): Welcome → Portal login → Gemini API key. Main UI stays locked until setup is complete.

### Friendly error messages
The UI shows short, plain-language errors (invalid API key, quota, missing dates, etc.). Full stack traces are written to `%LOCALAPPDATA%\VTU AIDS\vtu_aids_error.log` — not shown in the app.

### Automation browser (headed mode)
When **Run automation** opens Chromium:
- Window is brought **to the front once** (not stuck always-on-top)
- Page is **view only** — you can watch but not click form fields; minimize/maximize/close still work
- Playwright continues filling the portal in the background

### Clean shutdown
Quitting the app or stopping automation cleans up bot subprocesses and Playwright Chromium. If the app was force-closed (Task Manager), the next launch detects stale state and resets `bot_status.json`.

### Automation stability patch
Fixed script-mode import failures that could show `ModuleNotFoundError: No module named 'app'` during headed automation cleanup/display setup.

### Smart App Control helpers
Build output includes `Run-VTU_AIDS_Setup.bat`, `Invoke-Installer.ps1`, and `Install-From-Dist.ps1` for dev/local installs when SAC blocks unsigned builds.

---

## Install (end users)

1. Download **VTU_AIDS_Setup.exe** from [Releases](https://github.com/dhanushscience/VTU-AIDS/releases/tag/v1.0.4).
2. Run the installer → open **VTU AIDS** from the Start menu.
3. Complete the setup wizard (Internyet login + [Gemini API key](https://aistudio.google.com/apikey)).
4. **Step 1** dates → **Step 2** work summary → **Generate with AI** → **Step 3** **Run automation**.

Full guide: [docs/INSTALL.md](INSTALL.md)

---

## Upgrade from v1.0.3

- Install over the previous version (Settings → Apps → VTU AIDS → uninstall optional).
- Your config in `%LOCALAPPDATA%\VTU AIDS\` is kept.
- Hard refresh the browser tab once (Ctrl+Shift+R) if the UI looks cached.

---

## Build from source

```powershell
git clone https://github.com/dhanushscience/VTU-AIDS.git
cd VTU-AIDS
python -m venv .venv
.\.venv\Scripts\pip install -r requirements-desktop.txt
.\.venv\Scripts\python -m playwright install chromium
powershell -ExecutionPolicy Bypass -File build\build_windows.ps1
```

Output: `build\Output\VTU_AIDS_Setup.exe`

Optional Authenticode signing before publish:

```powershell
$env:VTU_AIDS_SIGN_PFX = "C:\path\to\cert.pfx"
$env:VTU_AIDS_SIGN_PASSWORD = "your-password"
powershell -ExecutionPolicy Bypass -File build\build_windows.ps1
```

---

## Known limitations

- **Smart App Control On:** unsigned builds are blocked until SAC is Off or the build is signed.
- **Force kill via Task Manager:** cannot run cleanup instantly; reopen VTU AIDS once to clear stale automation state.
- **Mobile/APK:** not supported — Playwright desktop automation does not port to Android as-is.

---

## GitHub release body (copy-paste)

```markdown
## VTU AIDS v1.0.4

Automated Internship Diary System for [VTU Internyet](https://vtu.internyet.in).

### What's new
- **First-run setup wizard** — portal login + Gemini API key before main UI
- **Friendly errors** — readable messages in UI; full details in local log file
- **Automation browser** — Chromium pops to front once; view-only overlay while bot runs
- **Clean shutdown** — stops bot/Chromium on quit; recovers after force-close
- **SAC install helpers** — scripts for Smart App Control / local dev installs

### Download
- **VTU_AIDS_Setup.exe** (~483 MB, Windows 10/11, includes Chromium)

### Quick start
1. Install and open **VTU AIDS**
2. Complete setup wizard
3. Select dates → describe work → **Generate with AI** → **Run automation**

📖 [Installation guide](https://github.com/dhanushscience/VTU-AIDS/blob/main/docs/INSTALL.md) · [Release notes](https://github.com/dhanushscience/VTU-AIDS/blob/main/docs/RELEASE_v1.0.4.md)

> Use only if permitted by your institution. Not affiliated with VTU or Internyet.
```
