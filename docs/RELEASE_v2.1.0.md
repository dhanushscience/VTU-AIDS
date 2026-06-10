# VTU AIDS v2.1.0

Security and performance release focused on safeguarding user credentials and improving app reliability.

**Platform:** Windows 10/11 (64-bit)

## Download

- Installer: [VTU_AIDS_Setup.exe](https://github.com/dhanushscience/VTU-AIDS/releases/download/v2.1.0/VTU_AIDS_Setup.exe)
- Releases page: [VTU-AIDS Releases](https://github.com/dhanushscience/VTU-AIDS/releases)

If Windows blocks install, see [windows.md](windows.md).
For Smart App Control environments, use:
`powershell -ExecutionPolicy Bypass -File build\Install-From-Dist.ps1`
to install under `%LOCALAPPDATA%\VTU AIDS`.

---

## Highlights in v2.1.0

### 1) Major Security Upgrade: Windows Credential Manager Integration

- **Secure Storage**: Passwords and Gemini API keys are no longer stored in plain text inside `student_config.json`.
- **System-Level Security**: Credentials are now securely saved to the Windows Credential Manager via the `keyring` library under the `VTU_AIDS` namespace.
- **Automatic Migration**: When upgrading from an older version, any existing plain-text credentials in your configuration file are automatically migrated to the secure keychain and permanently removed from the file.

### 2) Bug Fixes and Reliability

- Addressed potential security vulnerabilities regarding credential storage in the local application data directory.
- Refactored configuration handling to seamlessly support keychain integration across the desktop application, background automation, and CLI tools without disrupting the user experience.

---

## Upgrade notes for users

1. Install `v2.1.0` over previous release (uninstall first is optional).
2. Existing passwords will automatically be migrated to the Windows Credential Manager upon first opening the app.

Detailed install help: [INSTALL.md](INSTALL.md)

---

## Notes and warnings

- Use only if your institution permits this workflow.
- Not affiliated with VTU or Internyet.
- Keep credentials private and follow institutional policy.
