param(
    [ValidateSet("Debug", "Release")]
    [string]$Configuration = "Debug",
    [switch]$Portable,
    [switch]$RequireSigning
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$venv = Join-Path $root ".venv"
$python = Join-Path $venv "Scripts\python.exe"
$pip = Join-Path $venv "Scripts\pip.exe"
$pyinstaller = Join-Path $venv "Scripts\pyinstaller.exe"
$dist = Join-Path $root "dist"
$build = Join-Path $root "build"
$artifacts = Join-Path $root "artifacts"
$installerDir = Join-Path $root "installer"
$signingScript = Join-Path $root "scripts\sign-artifact.ps1"
$validateScript = Join-Path $root "scripts\validate-release.ps1"
$iconGenerator = Join-Path $root "scripts\generate_icon.py"

New-Item -ItemType Directory -Force -Path $artifacts | Out-Null

if (-not (Test-Path $python)) {
    python -m venv $venv
}

& $pip install --upgrade pip
& $pip install -r (Join-Path $root "requirements.txt")

Remove-Item -Recurse -Force $dist, $build -ErrorAction SilentlyContinue

$null = & $python $iconGenerator

$versionFile = Join-Path $root "resources\version_info.txt"
if (-not (Test-Path $versionFile)) {
    throw "Version file missing: $versionFile"
}

$appName = "TeamsCacheBuster"
$iconPath = Join-Path $root "assets\app.ico"

$baseArgs = @(
    "--noconfirm",
    "--clean",
    "--windowed",
    "--noupx",
    "--onedir",
    "--name", $appName,
    "--icon", $iconPath,
    "--version-file", $versionFile,
    "--paths", (Join-Path $root "src")
)

& $pyinstaller @baseArgs (Join-Path $root "src\teams_cache_buster\__main__.py")

if ($Portable) {
    & $pyinstaller @(
        "--noconfirm",
        "--clean",
        "--windowed",
        "--noupx",
        "--onefile",
        "--name", "$appName-portable",
        "--icon", $iconPath,
        "--version-file", $versionFile,
        "--paths", (Join-Path $root "src"),
        (Join-Path $root "src\teams_cache_buster\__main__.py")
    )
}

if ($Configuration -eq "Release") {
    $msiOut = Join-Path $artifacts "$appName.msi"
    $exePath = Join-Path $dist $appName "$appName.exe"

    if (-not (Test-Path $exePath)) {
        throw "Expected PyInstaller output was not found: $exePath"
    }

    & wix build (Join-Path $installerDir "TeamsCacheBuster.wxs") `
        -o $msiOut `
        -dProductVersion="1.0.0" `
        -dSourceDir=(Join-Path $dist $appName) `
        -dExeName="$appName.exe" `
        -dIconPath=$iconPath `
        -dPublisherName="Teams Cache Buster" `
        -dUpgradeCode="{0E1F6E14-5E48-4D90-A5A2-8F5F2CE5A4D1}"

    & $signingScript -Path @($exePath, $msiOut) -RequireSigning:$RequireSigning

    $checksumFile = Join-Path $artifacts "TeamsCacheBuster.sha256.txt"
    $signatureCheck = $RequireSigning -or $env:SIGNING_CERT_BASE64 -or $env:SIGNING_CERT_THUMBPRINT -or $env:SIGNING_TOOL
    if ($signatureCheck) {
        & $validateScript -Path @($exePath, $msiOut) -ChecksumOutput $checksumFile
    } else {
        & $validateScript -Path @($exePath, $msiOut) -ChecksumOutput $checksumFile -SkipSignatureCheck
    }
    Write-Host "Release artifacts created at $msiOut"
}
