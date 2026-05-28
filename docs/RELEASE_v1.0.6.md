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

### 6) Internship selection reliability improved

- Added bounded retries and fallback selection methods for slow/intermittent internship dropdown behavior
- Added stronger post-selection verification before moving to Step 2
- Failure messages now include clearer observed picker state for faster debugging

### 7) Full diagnostics mode enabled for this release

- Verbose DEBUG logging is enabled across launcher, API, and automation flows
- Logs include a run/session correlation ID to connect events across files
- New diagnostics log file: `%LOCALAPPDATA%\VTU AIDS\vtu_aids_debug.log`

### 8) New Settings bug-report workflow

- Added **Export logs** button in Settings (creates zip bundle with core logs)
- Added **Report bug** button in Settings (opens prefilled GitHub issue)
- Report template includes environment + run ID and asks user to attach exported logs

---

## Quick student flow

1. Install `VTU_AIDS_Setup.exe` (~483 MB)
2. Open VTU AIDS from Start menu
3. Complete setup wizard (Internyet + Gemini API key)
4. Daily use: Step 1 dates -> Step 2 prompt -> Step 3 review/upload

Detailed install help: [INSTALL.md](INSTALL.md)

---

## Portal flow (Internyet, 2026)

Automation follows the live two-step diary create flow:

1. **List:** `/dashboard/student/diary-entries` — click **Create** (link).
2. **Step 1:** `/dashboard/student/student-diary` — internship + diary date, then **Continue**.
3. **Step 2:** `/dashboard/student/create-diary-entry` (or `edit-diary-entry/{id}`) — fill fields, then **Save** (exact button label; not “Save Diary Entry”).

Field `name` attributes used by the bot: `description`, `hours`, `learnings`, `links`, `blockers`, `skill_ids` (react-select).

**Automation tips:** Run only one bot at a time (do not start CLI `--run-bot` while the app is already automating). Avoid pressing Escape in the entry form; the bot uses Tab to blur fields. If a run fails, check `%LOCALAPPDATA%\VTU AIDS\vtu_aids_debug.log`.

---

## Notes and warnings

- Use only if your institution permits this workflow
- Not affiliated with VTU or Internyet
- Keep credentials private and follow your institution policy
