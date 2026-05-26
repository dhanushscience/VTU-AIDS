# Windows notes

## Black window on launch

The embedded desktop window (WebView2) can show a **black screen** on some PCs even when the server is fine.

**Default (recommended):** The app opens the UI in **Chrome/Edge** (`--browser` mode). The desktop shortcut from the installer uses this too.

**If you want the embedded window:** You can run the app with the `--desktop` flag.

**If nothing works:**

1. Try reinstalling the application via the `VTU_AIDS_Setup.exe` installer.
2. Check `%LOCALAPPDATA%\VTU AIDS\vtu_aids_error.log` and `vtu_aids_startup.log`.

## OneDrive install folder

Do **not** install the developer repository into a synced OneDrive folder. `pip` often fails with **Access is denied** while files are syncing.

The `VTU_AIDS_Setup.exe` installer will automatically default to installing in `Local App Data` or `Program Files`, which avoids these OneDrive conflicts safely.

## Smart App Control

If your `VTU_AIDS_Setup.exe` installer or the application is blocked by Smart App Control, you may need to add an exception or trust the publisher. To sign releases, developers can set `VTU_AIDS_SIGN_PFX` and `VTU_AIDS_SIGN_PASSWORD`, then rebuild the app.

## Control Panel

The installer registers **VTU AIDS** under **Settings → Apps** for uninstallation. You can easily remove the application from your PC there.
