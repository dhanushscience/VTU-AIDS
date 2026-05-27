# Windows notes

## Smart App Control (installer blocked)

**Smart App Control** blocks unsigned apps. There is usually **no “Run anyway”** — only **Okay** or **Get apps from the Store**.

`Unblock-File` and copying out of OneDrive fix **SmartScreen / Mark-of-the-Web**, not Smart App Control.

### Fix on your PC (local / dev builds)

1. Open **Windows Security** → **App & browser control** → **Smart App Control settings** → **Off**  
   (A restart may be required.)
2. Run the installer via one of:
   - `build\Output\Run-VTU_AIDS_Setup.bat`
   - `powershell -ExecutionPolicy Bypass -File build\Invoke-Installer.ps1`  
     (copies the setup to `%TEMP%` and starts it — avoids OneDrive sync blocks)
3. If the setup still fails, install without the installer:
   - `powershell -ExecutionPolicy Bypass -File build\Install-From-Dist.ps1`  
     Copies `dist\VTU AIDS` to `%LOCALAPPDATA%\VTU AIDS` and launches the app.

See also `build\Output\SMART_APP_CONTROL.txt` after a full build.

### Fix for public releases

Sign the build with an Authenticode certificate before publishing:

```powershell
$env:VTU_AIDS_SIGN_PFX = "C:\path\to\cert.pfx"
$env:VTU_AIDS_SIGN_PASSWORD = "your-password"
powershell -ExecutionPolicy Bypass -File build\build_windows.ps1
```

Signing covers `dist\VTU AIDS\*.exe` and `build\Output\VTU_AIDS_Setup.exe` when `signtool.exe` is available.

---

## Black window on launch

The embedded desktop window (WebView2) can show a **black screen** on some PCs even when the server is fine.

**Default (recommended):** The app opens the UI in **Chrome/Edge** (`--browser` mode). The desktop shortcut from the installer uses this too.

**If you want the embedded window:** Run the app with the `--desktop` flag.

**If nothing works:**

1. Reinstall via `VTU_AIDS_Setup.exe` or `build\Install-From-Dist.ps1`.
2. Check `%LOCALAPPDATA%\VTU AIDS\vtu_aids_error.log` and `vtu_aids_startup.log`.

---

## OneDrive install folder

Do **not** build or run `VTU_AIDS_Setup.exe` from a synced **OneDrive** folder if you can avoid it. Sync adds a “downloaded from internet” mark and increases blocks.

Prefer:

- `build\Invoke-Installer.ps1`, or  
- Copy the installer to `C:\Temp` before running.

The Inno installer defaults to **Program Files** or **Local App Data**, not OneDrive.

---

## Post-install: SmartScreen only (not SAC)

If the **installed app** is blocked by SmartScreen (not Smart App Control), use **`Fix block and run VTU AIDS.bat`** in the install folder. That runs `Unblock-File` on the installed files.

---

## Control Panel

The installer registers **VTU AIDS** under **Settings → Apps** for uninstallation.

---

## Automation and clean shutdown

### Normal quit

Use **Quit** in the app (top right). This stops the local server, terminates any running automation subprocess, and closes Playwright Chromium windows.

### Force-close (Task Manager)

If you end **VTU AIDS** or the bot process in Task Manager, Windows cannot run cleanup code in that moment. On the **next launch**, VTU AIDS:

- Detects stale `bot_status.json` (`running: true` but bot PID gone)
- Resets automation status
- Closes orphan `ms-playwright` Chromium processes

If a Chromium window remains, close it manually or reopen VTU AIDS once.

### Logs

| Log | Purpose |
|-----|---------|
| `vtu_aids_error.log` | API and generation errors (full traceback) |
| `bot_run.log` | Playwright automation output |
| `vtu_aids_startup.log` | App launch diagnostics |
