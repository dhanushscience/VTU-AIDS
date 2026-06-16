# VTU AIDS v2.1.1

Patch release: Google auth API keys (`AQ.…`), marketing site improvements, and version alignment.

**Platform:** Windows 10/11 (64-bit)

## Download

- Installer: [VTU_AIDS_Setup.exe](https://github.com/dhanushscience/VTU-AIDS/releases/download/v2.1.1/VTU_AIDS_Setup.exe)
- Releases page: [VTU-AIDS Releases](https://github.com/dhanushscience/VTU-AIDS/releases)
- Marketing site: [dhanushscience.github.io/VTU-AIDS](https://dhanushscience.github.io/VTU-AIDS/)

If Windows blocks install, see [windows.md](windows.md).
For Smart App Control environments, use:

```powershell
powershell -ExecutionPolicy Bypass -File build\Install-From-Dist.ps1
```

to install under `%LOCALAPPDATA%\VTU AIDS`.

---

## Highlights in v2.1.1

### 1) New Gemini API key format (`AQ.…`)

- Google AI Studio now issues **auth keys** starting with `AQ.` (in addition to legacy `AIza…` keys).
- VTU AIDS accepts both formats in Settings and the setup wizard.
- Fixes “API key format looks wrong” when pasting a valid new AI Studio key.

### 2) Marketing website

- Mobile-friendly layout and intro animations.
- GitHub Pages deploy workflow for [website/](website/).
- Live site: https://dhanushscience.github.io/VTU-AIDS/

### 3) Version alignment

- App version in diagnostics, installer metadata, and in-app update checks now reports **2.1.1** consistently.

---

## Upgrade notes

1. Install `v2.1.1` over `v2.1.0` or earlier (uninstall first is optional).
2. If you use a new `AQ.…` API key, open **Settings**, paste the full key, and click **Save**.
3. Credentials in Windows Credential Manager are preserved across upgrades.

Detailed install help: [INSTALL.md](INSTALL.md)

---

## Notes and warnings

- Use only if your institution permits this workflow.
- Not affiliated with VTU or Internyet.
- Never share API keys or portal passwords publicly.
