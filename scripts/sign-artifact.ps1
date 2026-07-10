param(
    [Parameter(Mandatory = $true)]
    [string[]]$Path,
    [switch]$RequireSigning
)

$ErrorActionPreference = "Stop"

function Invoke-CmdSigned {
    param(
        [string[]]$Arguments
    )

    $signtoolPath = $null

    $signtool = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($signtool) {
        $signtoolPath = $signtool.Source
    }

    if (-not $signtoolPath) {
        $signtool = Get-ChildItem -Path "$env:ProgramFiles(x86)\Windows Kits\10\bin\*\x64\signtool.exe" -ErrorAction SilentlyContinue |
            Sort-Object FullName -Descending |
            Select-Object -First 1
        if ($signtool) {
            $signtoolPath = $signtool.FullName
        }
    }

    if (-not $signtoolPath) {
        throw "signtool.exe was not found on PATH."
    }

    & $signtoolPath @Arguments
}

function ConvertTo-SecureTempPfx {
    param([string]$Base64Content)

    $bytes = [Convert]::FromBase64String($Base64Content)
    $tempPath = Join-Path $env:TEMP ("teams-cache-buster-" + [guid]::NewGuid().ToString("N") + ".pfx")
    [System.IO.File]::WriteAllBytes($tempPath, $bytes)
    return $tempPath
}

$timestampUrl = $env:SIGNING_TIMESTAMP_URL
$signingTool = $env:SIGNING_TOOL

if (-not $timestampUrl -and -not $signingTool) {
    if ($RequireSigning) {
        throw "Signing is required, but no signing configuration was provided."
    }
    Write-Host "Signing skipped because no signing configuration was supplied."
    return
}

foreach ($target in $Path) {
    if (-not (Test-Path $target)) {
        throw "Signing target does not exist: $target"
    }
}

if ($signingTool) {
    $toolArgs = @()
    if ($env:SIGNING_TOOL_ARGS_JSON) {
        $toolArgs = $env:SIGNING_TOOL_ARGS_JSON | ConvertFrom-Json
    }
    foreach ($target in $Path) {
        & $signingTool @toolArgs $target
        if ($LASTEXITCODE -ne 0) {
            throw "Custom signing tool failed for $target"
        }
    }
    return
}

if (-not $timestampUrl) {
    if ($RequireSigning) {
        throw "SIGNING_TIMESTAMP_URL is required for certificate-based signing."
    }
    Write-Host "Signing skipped because no timestamp server was supplied."
    return
}

$fd = "sha256"
$td = "sha256"
$commonArgs = @("/fd", $fd, "/tr", $timestampUrl, "/td", $td, "/v")

if ($env:SIGNING_CERT_BASE64) {
    if (-not $env:SIGNING_CERT_PASSWORD) {
        throw "SIGNING_CERT_PASSWORD is required when SIGNING_CERT_BASE64 is supplied."
    }

    $pfxPath = ConvertTo-SecureTempPfx -Base64Content $env:SIGNING_CERT_BASE64
    try {
        foreach ($target in $Path) {
            Invoke-CmdSigned -Arguments @("sign", "/f", $pfxPath, "/p", $env:SIGNING_CERT_PASSWORD) + $commonArgs + @($target)
        }
    } finally {
        Remove-Item $pfxPath -Force -ErrorAction SilentlyContinue
    }
    return
}

if ($env:SIGNING_CERT_THUMBPRINT) {
    foreach ($target in $Path) {
        Invoke-CmdSigned -Arguments @("sign", "/sha1", $env:SIGNING_CERT_THUMBPRINT) + $commonArgs + @($target)
    }
    return
}

if ($RequireSigning) {
    throw "Signing is required, but no certificate or signing tool configuration was provided."
}

Write-Host "Signing skipped because the release secrets were not supplied."
