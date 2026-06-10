# Security

## Never commit secrets

These files are **gitignored** and must stay local:

| File | Contains |
|------|----------|
| `student_config.json` | Portal username. (Passwords and API keys are securely stored in the Windows Credential Manager and no longer exist in this file in plain text) |
| `.env` | Optional `GEMINI_API_KEY` (Not recommended, use UI instead) |
| `generated/entries.json` | Your diary content |

Use `student_config.example.json` as a template only.

## Where data is stored (installed app)

| Data | Location |
|------|----------|
| Settings | `%LOCALAPPDATA%\VTU AIDS\student_config.json` |
| Passwords & API Keys | Securely stored in the Windows Credential Manager |
| Generated entries | `%LOCALAPPDATA%\VTU AIDS\generated\` |
| Logs | `%LOCALAPPDATA%\VTU AIDS\vtu_aids_*.log`, `bot_run.log`, `bot_status.json` |

## API keys

- Get a Gemini key from [Google AI Studio](https://aistudio.google.com/apikey).
- Keys start with `AIza`. They are masked in the UI after saving.
- If a key was ever committed to git, **revoke it** in AI Studio and create a new one.

## Reporting issues

Open a GitHub issue for bugs. **Do not** paste passwords, API keys, or portal credentials in issues.
