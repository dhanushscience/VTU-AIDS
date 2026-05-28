# Windows Help (student-friendly)

Use this page when Windows blocks install/run, or if app behavior looks confusing.

---

## Quick check list first

- Confirm you are installing **v2.0.0**
- Confirm installer file name is `VTU_AIDS_Setup.exe`
- Confirm size is around **~483 MB**
- Prefer running installer from a local folder (for example `C:\Temp`)

If any of these are wrong, redownload from the official release link.

---

## 1) Smart App Control / Application Control block

### What this usually looks like

- Installer does not run
- Dialog may show only buttons like **Okay** or **Get apps from the Store**
- You may not see a **Run anyway** button

This is commonly **Smart App Control** policy behavior.

### What to do

1. Open **Windows Security**
2. Go to **App & browser control**
3. Open **Smart App Control settings**
4. Set to **Off** (restart if prompted)
5. Run installer again

If you want to keep Smart App Control **ON**, use the proven local install path instead of Program Files installer:

- `powershell -ExecutionPolicy Bypass -File build\Install-From-Dist.ps1`
- This installs to `%LOCALAPPDATA%\VTU AIDS` and unblocks copied files before launch.

What you should see after fix:

- Installer wizard opens normally
- You can complete installation

Developer alternatives (if needed):

- `build\Output\Run-VTU_AIDS_Setup.bat`
- `powershell -ExecutionPolicy Bypass -File build\Invoke-Installer.ps1`
- `powershell -ExecutionPolicy Bypass -File build\Install-From-Dist.ps1`

---

## 2) SmartScreen block after install (different from SAC)

### What this looks like

- VTU AIDS is installed
- App launch gets blocked by Windows warning

### What to do

- Run `Fix block and run VTU AIDS.bat` from install folder

What you should see:

- App opens after unblock step

---

## 3) OneDrive-related install problems

### Why this happens

Installing or launching from OneDrive-synced folders can add extra trust warnings or file locks.

### Safer approach

- Move installer to `C:\Temp` and run there, or
- Use `build\Invoke-Installer.ps1` (dev/local builds)

What you should see:

- Fewer Windows block prompts
- More reliable install completion

---

## 4) Black app window on launch

The default launch mode is desktop window. Some systems may show black screen due to local WebView/GPU issues.

### What to do

- Use browser fallback mode:
  - `python vtu_aids.py --browser`
  - or `Run VTU AIDS (Browser).bat` (dev installs)

What you should see:

- App opens in your normal browser at local address
- Full workflow still works

![Main app screen reference](images/01-app-overview.png)

Reference: if this screen appears in browser mode, fallback is working correctly.

---

## 5) Visible browser mode during automation

If you enable **Visible browser**, Chromium opens so you can observe upload.

What to expect:

- You can watch navigation/fill actions
- It is view-only for automation safety
- You can still close/minimize the browser window

If upload freezes, reopen app once and retry.

---

## 6) Logs for support

If something still fails, collect these files:

- `%LOCALAPPDATA%\VTU AIDS\vtu_aids_error.log`
- `%LOCALAPPDATA%\VTU AIDS\bot_run.log`
- `%LOCALAPPDATA%\VTU AIDS\vtu_aids_startup.log`

These logs help identify exact issue quickly.

---

## 7) Uninstall and cleanup

- Uninstall from **Settings > Apps > VTU AIDS**
- Optional: delete `%LOCALAPPDATA%\VTU AIDS\` to remove saved local data

On uninstall, the app can ask whether to remove generated entries and saved credentials.
