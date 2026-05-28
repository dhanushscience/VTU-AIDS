# VTU AIDS v2.0.0

Major release focused on automation reliability, polished UI/UX, stronger document extraction, new update notifications, and refreshed branding.

**Platform:** Windows 10/11 (64-bit)

## Download

- Installer: [VTU_AIDS_Setup.exe](https://github.com/dhanushscience/VTU-AIDS/releases/download/v2.0.0/VTU_AIDS_Setup.exe)
- Releases page: [VTU-AIDS Releases](https://github.com/dhanushscience/VTU-AIDS/releases)

If Windows blocks install, see [windows.md](windows.md).
For Smart App Control environments, use:
`powershell -ExecutionPolicy Bypass -File build\Install-From-Dist.ps1`
to install under `%LOCALAPPDATA%\VTU AIDS`.

---

## Highlights in v2.0.0

### 1) Portal automation is faster and more reliable for existing entries

- Added early existing-entry fast path to avoid unnecessary calendar/navigation steps.
- Reduced lag in React form fill by using native input value setter injection with fallback.
- Improved create/edit flow checks so date selection is verified before skipping Continue.
- Scoped field interactions (skills/hours) to the correct form container to avoid side effects.
- Replaced risky Tab-based blur with safer in-form blur handling to prevent focus jumping.

### 2) Stronger bot process safety and control

- Fixed cross-process lock behavior to avoid false "already running" detection in child process.
- Added clean stop automation flow in backend and frontend (`/api/run-bot/stop`).
- Improved subprocess lifecycle handling and Chromium cleanup on stop.

### 3) Major UI/UX refresh across all three sections

- Unified Run/Stop into one dynamic automation button with clear running-state visuals.
- Added professional confirmation modal (replacing browser-native confirm prompts).
- Applied consistent themed styling for setup, settings, and confirmation dialogs for better readability.
- Improved spacing, alignment, and section density for cleaner daily workflow.
- Reduced oversized date selection highlight effects for better calendar readability.
- Added proper gap and visual rhythm between status toasts and action buttons.
- Fixed hover/readability issues in action buttons and refined running-state animations.

### 4) Internship timeline and progress tracking

- Added internship start date, probable end date, and optional total days in Settings.
- Added circular progress tracker with center count (for example `43/90`).
- Progress now updates based on submitted portal entries (not just generated drafts).
- Allows work beyond target duration (no hard stop at target day count).

### 5) Better calendar behavior and date selection experience

- Defaulted calendar behavior toward latest relevant month after generation/sync.
- Improved Select vs Edit mode visuals (dotted boxes shown only where appropriate).
- Added "Selected dates" heading and improved chips container behavior.
- Fixed stale/unselected date chips appearing after load/sync operations.
- Improved responsive spacing around mode toggle and calendar controls.

### 6) Input validation improvements (frontend + backend)

- Enforced hours range to min `1` and max `24` across UI interactions and API validation.
- Enforced words-per-day range (`20` to `500`) in UI and backend.
- Added safer config/save validation for critical numeric fields.

### 7) Document upload and extraction reliability upgrade

- Increased max upload size from `10 MB` to `25 MB`.
- Added robust PDF fallback extraction path:
  - pypdf text extraction first
  - direct Gemini PDF extraction fallback
  - embedded-image OCR fallback where applicable
- Removed legacy `.doc` handling due to unreliable extraction quality.
- Improved upload error messaging to expose actionable root causes instead of generic failures.
- Added UI hint for max upload size near upload control.

### 8) Scroll and responsive behavior optimized site-wide

- Scrollbars are now conditional and appear only when content truly overflows.
- Improved behavior for smaller window heights with responsive overflow fallback.
- Refined drawer and section scrolling rules to avoid unnecessary scrollbars in normal sizes.

### 9) New in-app update notification flow

- Added GitHub release update check endpoint (`/api/update-check`).
- Added non-blocking in-app update banner with:
  - **Install update** action
  - **Remind me later** action
- Update messaging now recommends staying on latest version to enjoy new features.
- "Remind me later" defers prompts per-version and re-notifies on newer releases.

### 10) Branding and icon refresh

- Added support for new branding assets:
  - `static/AIDS_MAIN.png` (main logo)
  - `static/AIDS_TASKBAR_FAVICON.png` (taskbar/favicon)
- Updated frontend, backend icon routes, desktop launcher icon preference, and build scripts.
- Regenerated `logo.png`, `favicon.png`, and `app.ico` from new assets.
- Improved ICO generation pipeline with transparent-background handling.

---

## Included fixes from this cycle

- Fixed repeated code-1 startup and module-import related run failures.
- Fixed navigation/focus issues causing accidental page movement during entry edit.
- Fixed incorrect selected-date rendering and stale chips after sync/reload.
- Fixed calendar visibility regression in Date range mode.
- Fixed clipping/overflow issues in selected dates and settings sections.
- Fixed upload failures for scanned/image-style PDFs with fallback extraction logic.
- Fixed inconsistent error responses for document extraction failures.

---

## Upgrade notes for users

1. Install `v2.0.0` over previous release (uninstall first is optional).
2. Reopen app and verify Settings once (portal + Gemini key).
3. If Windows shows old icon after update, close app and restart Explorer or unpin/repin shortcut.

Detailed install help: [INSTALL.md](INSTALL.md)

---

## Notes and warnings

- Use only if your institution permits this workflow.
- Not affiliated with VTU or Internyet.
- Keep credentials private and follow institutional policy.
