<p align="center">
  <img src="static/logo.png" alt="VTU AIDS logo" width="96" />
</p>

<h1 align="center">VTU AIDS</h1>

<p align="center">
  Automated Internship Diary System for students using
  <a href="https://vtu.internyet.in">VTU Internyet</a>
</p>

<p align="center">
  <a href="https://github.com/dhanushscience/VTU-AIDS/releases/download/v2.0.0/VTU_AIDS_Setup.exe">
    <img src="https://img.shields.io/badge/Download-VTU_AIDS_Setup.exe%20(v2.0.0)-2563eb?style=for-the-badge&logo=windows&logoColor=white" alt="Download VTU AIDS for Windows" />
  </a>
</p>

<p align="center">
  <sub>Windows 10/11 · installer size ~483 MB · includes Chromium</sub>
</p>

<p align="center">
  <a href="docs/INSTALL.md">Installation guide</a> ·
  <a href="docs/windows.md">Windows troubleshooting</a> ·
  <a href="docs/RELEASE_v2.0.0.md">v2.0.0 release notes</a> ·
  <a href="SECURITY.md">Security</a>
</p>

---

> **Disclaimer:** Use only if allowed by your institution and portal terms.  
> **Not affiliated with VTU or Internyet.**  
> **Never share your credentials or API key.**

## What this app does

VTU AIDS helps students create internship diary entries faster.  
You pick dates, write one clear summary of your work, and the app prepares day-wise entries using Gemini AI. You can review/edit everything before upload.

## Who should use this

- Students who already use the VTU Internyet diary portal
- Students who want to save time writing repetitive day-wise entries
- Students who are comfortable reviewing AI-generated text before submission

### Prerequisites

- Windows 10 or Windows 11
- VTU Internyet account (username/password)
- Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)
- Permission from your institution to use automation tools

---

## Fastest start (recommended)

1. Download [**VTU_AIDS_Setup.exe (v2.0.0)**](https://github.com/dhanushscience/VTU-AIDS/releases/download/v2.0.0/VTU_AIDS_Setup.exe) (**~483 MB**).
2. Run the installer.
3. Open **VTU AIDS** from Start menu.
4. Complete first-run setup wizard.
5. Use the 3-step workflow daily.

Full beginner walkthrough: [docs/INSTALL.md](docs/INSTALL.md)

---

## Screenshots (what each screen means)

All screenshots in docs should use sample/demo values only (no personal credentials, emails, or internship-specific private details).

| Screenshot | What you should understand |
|---|---|
| ![App overview](docs/images/01-app-overview.png) | Main screen after setup: you will use Step 1, Step 2, then Step 3 in order. |
| ![Date range mode](docs/images/02-step1-date-range.png) | Faster date selection: choose From/Till dates and skip weekdays like Sunday. |
| ![Settings screen](docs/images/03-settings.png) | Safe place to update Internyet login, Gemini key, model, and default internship label. |

---

## First run setup wizard (step by step)

When you open the app first time, the setup wizard appears automatically.

1. **Welcome**
   - What you should see: intro message and **Next** button.
2. **Portal login**
   - Enter your VTU Internyet username and password.
   - What you should see: fields accepted and move to next step.
3. **Gemini API details**
   - Paste API key, choose model, set optional default internship label.
   - Click **Finish**.
   - What you should see: main app becomes usable.
4. **Version update notice (when applicable)**
   - On app load, VTU AIDS checks latest GitHub release in the background.
   - If a newer version exists, an update banner appears with:
     - **Install update** (opens latest release/installer)
     - **Remind me later** (hides current version reminder and shows again for a newer version)

You can reopen these settings anytime from **Settings**.

---

## Daily usage flow (student routine)

### Step 1: Select dates

- Pick individual days in the calendar, or switch to **Date range**
- Optionally skip non-working weekdays
- Optional: enable **Edit** mode if you want to edit rows later

### Step 2: Write your prompt

- Enter internship label exactly as shown on portal
- Write your work summary in simple language
- Optional: attach reference files
- Click **Generate with AI**

### Step 3: Review and upload

- Read generated entries
- Fix anything incorrect
- Click **Run automation** to upload to Internyet
- Optional: click **Download Excel** for local copy

---

## Visible browser option (important)

- If **Visible browser** is ON, you can see Chromium while upload runs.
- This view is for monitoring only (you cannot type/click inside automation page).
- Use this when you want confidence about what is being uploaded.
- If desktop window appears black, run browser mode fallback:
  - `python vtu_aids.py --browser`
  - or `Run VTU AIDS (Browser).bat` (developer installs)

---

## Data and privacy

Local storage path:

`%LOCALAPPDATA%\VTU AIDS\`

Saved here:

- `student_config.json` (portal login + Gemini settings)
- Generated entries and temporary automation files
- Logs such as `vtu_aids_error.log`, `bot_run.log`, `vtu_aids_startup.log`, `vtu_aids_debug.log`

Notes:

- Data is local to your Windows user profile
- Default storage is outside OneDrive sync location
- Do not upload/share config files publicly

---

## Common errors and exact fixes

| Problem you see | Simple fix |
|---|---|
| Installer blocked with only `Okay` / `Get apps from the Store` | This is usually Smart App Control. Use SAC-safe local install: `powershell -ExecutionPolicy Bypass -File build\\Install-From-Dist.ps1` (details in [docs/windows.md](docs/windows.md)). |
| Black app window | Use browser fallback (`--browser`). |
| Setup installed but app did not auto-open | This is expected in v2.0.0. Launch from Start menu manually. |
| Generate or page looks stuck | Press `Ctrl+Shift+R` for hard refresh. |
| Automation fails and asks for missing browser executable | Run `python vtu_aids.py --install-browser` (source/dev setups). |
| Force-closed app and automation says already running | Open VTU AIDS again once; stale status is cleaned automatically. |
| Need to report a bug | Open **Settings** → **Export logs** → **Report bug** and attach the generated zip file. |

---

## FAQ for students

**Is this officially from VTU?**  
No. It is not affiliated with VTU or Internyet.

**Do I still need to check my content?**  
Yes. Always review AI text before upload.

**Can I use it without a Gemini key?**  
No. Generation requires a valid Gemini API key.

**Will it submit without showing browser?**  
Yes. You can run hidden or visible mode.

**Where can I edit credentials later?**  
Open **Settings** in the app.

**Will uninstall remove my saved data?**  
Installer can ask whether to remove `%LOCALAPPDATA%\VTU AIDS\` data.

---

## Additional docs

- [docs/INSTALL.md](docs/INSTALL.md) - full beginner installation walkthrough
- [docs/windows.md](docs/windows.md) - Windows block/fix reference
- [docs/RELEASE_v2.0.0.md](docs/RELEASE_v2.0.0.md) - release changes

## Security reminder

Never commit/share:

- `student_config.json`
- `.env`
- `generated/entries.json`
