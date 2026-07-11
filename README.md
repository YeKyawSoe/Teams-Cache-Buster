# Teams Cache Buster

Teams Cache Buster is a Windows desktop utility that clears Microsoft Teams cache files and safely handles the related Teams and Outlook processes.

## Features

- Detects running Teams and Outlook processes
- Warns the user before closing apps
- Clears the classic and new Teams cache locations
- Restarts only the apps that were running before cleanup
- Ships as a Windows GUI app built with `tkinter`

## What it clears

- `%appdata%\Microsoft\Teams`
- `%localappdata%\Packages\MSTeams_8wekyb3d8bbwe\LocalCache\Microsoft\MSTeams`

## Run locally

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m teams_cache_buster
```

## Run tests

```powershell
python -m pytest -q
```

## Build

Primary release format:

- Signed MSI installer built from the PyInstaller `onedir` output

Optional build:

- Portable `onefile` executable

Build script:

```powershell
pwsh ./scripts/build.ps1 -Configuration Release
```

Optional portable build:

```powershell
pwsh ./scripts/build.ps1 -Configuration Debug -Portable
```

## CI and release flow

- GitHub Actions workflow: `.github/workflows/build.yml`
- Runs on `windows-latest`
- Pushes and pull requests run tests, build the app, and smoke-test the executable
- Workflow dispatch lets you run the job manually from the Actions tab
- Releases can sign the EXE and MSI, verify signatures, run Microsoft Defender, and publish SHA-256 checksums

## Signing and release inputs

Provide these through CI secrets or environment variables:

- `SIGNING_CERT_BASE64`
- `SIGNING_CERT_PASSWORD`
- `SIGNING_TIMESTAMP_URL`
- `SIGNING_CERT_THUMBPRINT`
- `SIGNING_TOOL`
- `SIGNING_TOOL_ARGS_JSON`

## Notes

- The app is intended for Windows only
- Antivirus and SmartScreen warnings cannot be eliminated entirely, but the build follows standard Windows distribution practices to reduce false positives
