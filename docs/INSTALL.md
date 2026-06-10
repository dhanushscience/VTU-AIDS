# Install VTU AIDS (Windows)

This is a practical, beginner-friendly setup guide for release **v2.1.0**.

> Use only if allowed by your institution policy.  
> VTU AIDS is not affiliated with VTU or Internyet.

## Before you begin

- PC: Windows 10 or Windows 11
- Internet connection
- VTU Internyet login credentials
- Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)

## Option A: Installer (recommended for students)

No Python setup is required.

### 1) Download installer

Download: [VTU_AIDS_Setup.exe](https://github.com/dhanushscience/VTU-AIDS/releases/download/v2.1.0/VTU_AIDS_Setup.exe)  
File size: **~485 MB** (large because Chromium is bundled for automation).

What you should see:

- Browser download item named `VTU_AIDS_Setup.exe`
- Size around 485 MB

### 2) Run installer

1. Double-click `VTU_AIDS_Setup.exe`.
2. Allow Windows prompt if shown.
3. Select install folder and continue.
4. Complete installation.

What you should see:

- Setup wizard pages with app name `VTU AIDS`
- Finish message with successful install

If Windows blocks the installer, go to [windows.md](windows.md) and follow the Smart App Control section.

### 3) Open the app first time

Launch from Start menu: **VTU AIDS**

What you should see:

- App opens in desktop window
- First-run setup wizard appears (if credentials are missing)

### 4) Complete first-run setup wizard

The wizard has 3 simple screens:

1. **Welcome**
2. **Portal Login** (Internyet username/password)
3. **Gemini API** (API key + model + optional default internship label)

Click **Finish**.

What you should see:

- Main app screen becomes fully usable
- Settings are saved for next launch

### 5) Use daily workflow (Step 1 → Step 2 → Step 3)

![Main app overview - use steps in order](images/01-app-overview.png)

What you should see:

- Three panels/steps in order
- Generate and automation buttons in the expected flow

#### Step 1: Pick dates

- Choose calendar dates or use Date range mode
- Skip non-working weekdays if needed

![Date range mode for faster selection](images/02-step1-date-range.png)

What you should see:

- From/Till fields in Date range mode
- Weekday skip options

#### Step 2: Enter your work prompt

- Enter internship label exactly as portal uses it
- Write one clear summary of work done
- Optionally attach files
- Click **Generate with AI**

What you should see:

- AI generation completes and creates rows for selected dates

#### Step 3: Review and upload

- Read every generated row
- Edit any row if needed
- Click **Run automation**

What you should see:

- Upload progress/status updates
- Completion indication when done

### 6) Optional: Visible browser mode during upload

- Turn on **Visible browser** before running automation
- Chromium opens so you can watch progress
- Page is view-only for safety (you can close/minimize window, but not type inside)

### 7) Quit and uninstall safely

- Use **Quit** in app for clean shutdown
- Uninstall from Settings > Apps > VTU AIDS

Optional cleanup:

- Delete `%LOCALAPPDATA%\VTU AIDS\` if you want to remove saved settings/logs

### 8) Report a bug (recommended if something fails)

- Open **Settings**
- Click **Export logs** (this creates a zip file in `%LOCALAPPDATA%\VTU AIDS\`)
- Click **Report bug** (opens prefilled GitHub issue)
- Attach the exported zip so issues can be diagnosed faster

---

## Option B: Run from source (developers)

Requires Python 3.11+ and Git.

```powershell
git clone https://github.com/dhanushscience/VTU-AIDS.git
cd VTU-AIDS
python -m venv .venv
.\.venv\Scripts\pip install -r requirements-desktop.txt
.\.venv\Scripts\python -m playwright install chromium
copy student_config.example.json student_config.json
python vtu_aids.py
```

Launch options:

- `python vtu_aids.py` (desktop default)
- `python vtu_aids.py --desktop`
- `python vtu_aids.py --browser` (fallback mode)
- `python vtu_aids.py --dev`

---

## Quick troubleshooting

| Issue | Fix |
|---|---|
| Installer blocked with no "Run anyway" | Use SAC-safe local install: `powershell -ExecutionPolicy Bypass -File build\\Install-From-Dist.ps1` (see [windows.md](windows.md)). |
| App window is black | Run browser fallback: `python vtu_aids.py --browser` |
| App did not open automatically after install | Normal in v2.1.0. Open from Start menu manually. |
| Need logs for debugging | Check `%LOCALAPPDATA%\VTU AIDS\vtu_aids_error.log` and `bot_run.log`. |

## Security reminder

Do not share or commit:

- `student_config.json` (note: passwords and API keys are now securely stored in Windows Credential Manager)
- `.env`
- `generated/entries.json`

See [SECURITY.md](../SECURITY.md).
