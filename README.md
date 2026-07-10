# Teams Cache Buster

Teams Cache Buster is a Windows desktop utility that clears Microsoft Teams cache folders and safely handles Outlook and Teams process shutdown/relaunch behavior.

## What it does

- Detects whether Microsoft Teams Classic, New Teams, and Outlook are running.
- Warns the user before closing apps.
- Forcefully stops the running apps with a short delay to release file hooks.
- Clears:
  - `%appdata%\Microsoft\Teams`
  - `%localappdata%\Packages\MSTeams_8wekyb3d8bbwe\LocalCache\Microsoft\MSTeams`
- Relaunches only the apps that were detected before cleanup.

## Project layout

- `src/teams_cache_buster/` main application code
- `tests/` unit tests with mocks
- `scripts/` build and packaging scripts
- `installer/` WiX installer source
- `requirements.txt` pinned Python dependencies
- `pytest.ini` configures `src` on the Python path for tests

## Development build

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m pytest
python -m teams_cache_buster
```

## Production build

Primary release format: signed MSI built from the `onedir` PyInstaller output.

Build prerequisites:

- Windows
- Python 3.12 or compatible
- WiX Toolset v4 installed as a `dotnet` tool
- Windows SDK `signtool.exe` if you are using certificate-based Authenticode signing locally

```powershell
# Unsigned local build
pwsh ./scripts/build.ps1 -Configuration Release

# Signed production build
pwsh ./scripts/build.ps1 -Configuration Release -RequireSigning

# Optional portable onefile build
pwsh ./scripts/build.ps1 -Configuration Debug -Portable
```

The build script expects the following environment variables for signing in production:

- `SIGNING_CERT_BASE64`
- `SIGNING_CERT_PASSWORD`
- `SIGNING_TIMESTAMP_URL`
- `SIGNING_CERT_THUMBPRINT` or a certificate in the imported store
- `SIGNING_TOOL` and `SIGNING_TOOL_ARGS_JSON` for an Azure signing client or other trusted external signer

## GitHub Actions

The repository uses GitHub-hosted Windows runners (`windows-latest`) for CI and release builds.

- Pushes run tests and produce build artifacts.
- Pushes also smoke-test the Windows `.exe` by launching it with `--smoke-test`.
- Published GitHub releases build signed artifacts when signing secrets are present.
- Release assets include the MSI installer and SHA-256 checksum.
- The onedir build is uploaded as a downloadable artifact for manual inspection.

### Unsigned development builds

If signing variables are not present, the build script can produce unsigned development artifacts for internal testing. This is useful for local verification and UI testing, but it does not replace production signing.

### Signed production builds

For production releases, the build pipeline:

- Generates the `onedir` PyInstaller payload.
- Builds an MSI installer with a stable product name, publisher, and upgrade code.
- Signs the executable and installer with SHA-256 Authenticode.
- Uses RFC 3161 timestamping.
- Verifies the signature.
- Runs a Microsoft Defender scan.
- Writes a SHA-256 checksum.

## Testing the exe

Because this is a Windows executable, you cannot run it directly on macOS. The intended validation path is:

1. Push changes to GitHub.
2. Let GitHub Actions build the app on `windows-latest`.
3. Download the `TeamsCacheBuster-ondir` artifact or the release MSI.
4. Confirm the workflow's `--smoke-test` step passed.

For a local Windows machine, you can also run:

```powershell
TeamsCacheBuster.exe --smoke-test
```

## Signing commands

The build pipeline calls `scripts/sign-artifact.ps1` for the executable and MSI. It reads signing settings from environment variables and does not store keys or passwords in the repository.

Example certificate-based signing input:

```powershell
$env:SIGNING_CERT_BASE64 = "<base64 pfx>"
$env:SIGNING_CERT_PASSWORD = "<pfx password>"
$env:SIGNING_TIMESTAMP_URL = "https://timestamp.digicert.com"
```

Example pluggable signing client input:

```powershell
$env:SIGNING_TOOL = "TrustedSigningClient.exe"
$env:SIGNING_TOOL_ARGS_JSON = '["sign","--profile","<profile>"]'
```

## Validation

The build pipeline calls `scripts/validate-release.ps1` to:

- Verify Authenticode signatures for signed production builds.
- Run a Microsoft Defender scan where available.
- Emit SHA-256 checksums in `artifacts/TeamsCacheBuster.sha256.txt`.

## Notes on distribution

This project follows standard Windows software-distribution practices to reduce false-positive risk. No packaging flow can guarantee that antivirus software or SmartScreen will never warn on a new build.
