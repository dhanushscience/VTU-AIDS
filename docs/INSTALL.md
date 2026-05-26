# Installation guide

Step-by-step setup for **Windows** users and developers.

---

## Option A — Installer (recommended)

No Python required on your PC.

### 1. Download

Get **`VTU_AIDS_Setup.exe`** from the [Releases](https://github.com/YOUR_USERNAME/vtu-aids/releases) page (≈280 MB — includes Chromium for automation).

### 2. Run the installer

![App overview after install](images/01-app-overview.png)

1. Double-click **`VTU_AIDS_Setup.exe`**.
2. If **Smart App Control** blocks it, click **More info → Run anyway**, or use the post-install **`Fix block and run VTU AIDS.bat`** in the install folder.
3. Choose an install location (e.g. `C:\Program Files\VTU AIDS` or `F:\VTU AIDS`).
4. Finish the wizard and launch **VTU AIDS** from the Start menu or desktop shortcut.

### 3. First launch — Settings

![Settings drawer](images/03-settings.png)

1. Click **Settings** (top right).
2. Enter your **VTU Internyet username** and **password**.
3. Paste your **Gemini API key** from [Google AI Studio](https://aistudio.google.com/apikey) (starts with `AIza`).
4. Set **default internship** text exactly as it appears in the portal dropdown.
5. Click **Save settings**.

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
- Enable **Visible browser** to watch Playwright fill the portal.
- **Download Excel** exports your entries locally.

### 5. Uninstall

**Settings → Apps → VTU AIDS**, or run the uninstaller from the Start menu. Optionally delete `%LOCALAPPDATA%\VTU AIDS\` to remove saved config and entries.

---

## Option B — Run from source (developers)

Requires **Python 3.11+** and **Git**.

```powershell
git clone https://github.com/YOUR_USERNAME/vtu-aids.git
cd vtu-aids
python -m venv .venv
.\.venv\Scripts\pip install -r requirements-desktop.txt
.\.venv\Scripts\python -m playwright install chromium
copy student_config.example.json student_config.json
```

Edit `student_config.json` or use in-app Settings after launch.

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
| Smart App Control block | Unblock install folder or use `Fix block and run VTU AIDS.bat` |
| Logs | `%LOCALAPPDATA%\VTU AIDS\vtu_aids_error.log` |

---

## Security reminder

Never commit or share `student_config.json`, `.env`, or `generated/entries.json`. See [SECURITY.md](../SECURITY.md).
