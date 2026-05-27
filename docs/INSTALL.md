# Installation guide

Step-by-step setup for **Windows** users and developers.

**Current release:** [v1.0.4](https://github.com/dhanushscience/VTU-AIDS/releases/tag/v1.0.4)

---

## Option A — Installer (recommended)

No Python required on your PC.

### 1. Download

Get **`VTU_AIDS_Setup.exe`** from [Releases](https://github.com/dhanushscience/VTU-AIDS/releases/download/v1.0.4/VTU_AIDS_Setup.exe) (≈280 MB — includes Chromium for automation).

### 2. Run the installer

![App overview after install](images/01-app-overview.png)

1. Double-click **`VTU_AIDS_Setup.exe`** (or, for local builds, `build\Output\Run-VTU_AIDS_Setup.bat`).
2. If **Smart App Control** blocks it (no Run anyway): turn **Smart App Control** **Off** under Windows Security → App & browser control, then retry. See **[docs/windows.md](windows.md)**. For dev builds without the installer: `build\Install-From-Dist.ps1`.
3. If only **SmartScreen** blocks the installed app, use **`Fix block and run VTU AIDS.bat`** in the install folder.
4. Choose an install location (e.g. `C:\Program Files\VTU AIDS` or `F:\VTU AIDS`).
5. Finish the wizard and launch **VTU AIDS** from the Start menu or desktop shortcut.

### 3. First launch — Setup wizard

On first run (or if credentials are missing), a **3-step setup wizard** opens automatically and the main UI stays blurred until you finish:

1. **Welcome** — overview and install help if Windows blocked the installer  
2. **Portal login** — VTU Internyet username and password  
3. **Gemini API** — API key from [Google AI Studio](https://aistudio.google.com/apikey), model, optional default internship  

Click **Finish** to save. Change these anytime via **Settings** (top right).

Settings are stored at:

`%LOCALAPPDATA%\VTU AIDS\student_config.json`

### 4. Generate and upload entries

![App overview](images/01-app-overview.png)

| Step | What to do |
|------|------------|
| **01 — Dates** | Pick days on the calendar, or switch to **Date range** and set From/Till + weekday skip. |
| **02 — Your entry** | Internship label, work summary, optional documents → **Generate with AI**. |
| **03 — AI entries** | Review the table, edit if needed → **Run automation**. |

![Date range mode](images/02-step1-date-range.png)

**Tips**

- Use **Date range** for a week or month at once; the calendar hides to save space.
- Enable **Visible browser** to watch Playwright fill the portal (view-only overlay — you cannot click the page, but can minimize/maximize/close the window).
- **Download Excel** exports your entries locally.
- If an error appears in the app, check `%LOCALAPPDATA%\VTU AIDS\vtu_aids_error.log` for full details.

### 5. Quit and uninstall

Use **Quit** in the app header to stop the server and any running automation cleanly.

**Settings → Apps → VTU AIDS**, or run the uninstaller from the Start menu. Optionally delete `%LOCALAPPDATA%\VTU AIDS\` to remove saved config and entries.

If you force-closed the app (Task Manager), reopen VTU AIDS once — it clears stale automation state and orphan Chromium windows.

---

## Option B — Run from source (developers)

Requires **Python 3.11+** and **Git**.

```powershell
git clone https://github.com/dhanushscience/VTU-AIDS.git
cd VTU-AIDS
python -m venv .venv
.\.venv\Scripts\pip install -r requirements-desktop.txt
.\.venv\Scripts\python -m playwright install chromium
copy student_config.example.json student_config.json
```

Edit `student_config.json` or use the in-app setup wizard / Settings after launch.

### Launch modes

| Command | Description |
|---------|-------------|
| `python vtu_aids.py` | Default — opens UI in your system browser |
| `python vtu_aids.py --browser` | Same as default |
| `python vtu_aids.py --desktop` | Embedded window (WebView2; may show black on some GPUs) |
| `python vtu_aids.py --dev` | Dev server with hot reload at http://127.0.0.1:8765/ |

Alternative entry point:

```powershell
.\.venv\Scripts\python -m app.cli --browser
```

### Build your own installer

1. Install [Inno Setup 6](https://jrsoftware.org/isinfo.php).
2. Run:

```powershell
powershell -ExecutionPolicy Bypass -File build\build_windows.ps1
```

Output: **`build\Output\VTU_AIDS_Setup.exe`**

See [docs/windows.md](windows.md) for Smart App Control, OneDrive, and troubleshooting.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| App won't start / tiny exe (~300 KB) | Reinstall from a fresh build; never patch the exe with rcedit. Valid size ≈ **19 MB**. |
| Black desktop window | Use browser mode: `python vtu_aids.py --browser` |
| UI scripts failed | Ctrl+Shift+R hard refresh, or reinstall |
| Smart App Control block | Turn SAC **Off** in Windows Security; dev: `build\Invoke-Installer.ps1` or `build\Install-From-Dist.ps1` — [windows.md](windows.md) |
| Automation says already running | Close orphan Chromium or reopen VTU AIDS to reset stale state |
| Logs | `%LOCALAPPDATA%\VTU AIDS\vtu_aids_error.log`, `bot_run.log` |

---

## Security reminder

Never commit or share `student_config.json`, `.env`, or `generated/entries.json`. See [SECURITY.md](../SECURITY.md).
