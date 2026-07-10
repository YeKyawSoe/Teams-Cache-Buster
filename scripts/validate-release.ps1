param(
    [Parameter(Mandatory = $true)]
    [string[]]$Path,
    [string]$ChecksumOutput = "",
    [switch]$SkipSignatureCheck
)

$ErrorActionPreference = "Stop"

function Get-DefenderScanner {
    $startMpScan = Get-Command Start-MpScan -ErrorAction SilentlyContinue
    if ($startMpScan) {
        return @{ Mode = "Cmdlet"; Command = $startMpScan.Source }
    }

    $candidate = Join-Path $env:ProgramFiles "Windows Defender\MpCmdRun.exe"
    if (Test-Path $candidate) {
        return @{ Mode = "Exe"; Command = $candidate }
    }

    $candidate = Join-Path ${env:ProgramFiles(x86)} "Windows Defender\MpCmdRun.exe"
    if (Test-Path $candidate) {
        return @{ Mode = "Exe"; Command = $candidate }
    }

    return $null
}

$hashLines = New-Object System.Collections.Generic.List[string]

foreach ($target in $Path) {
    if (-not (Test-Path $target)) {
        throw "Validation target does not exist: $target"
    }

    if (-not $SkipSignatureCheck) {
        $signature = Get-AuthenticodeSignature -FilePath $target
        if ($signature.Status -ne "Valid") {
            throw "Authenticode signature validation failed for $target. Status: $($signature.Status)"
        }
    }

    $hash = Get-FileHash -Algorithm SHA256 -Path $target
    $hashLines.Add("{0}  {1}" -f $hash.Hash, $target)
}

$scanner = Get-DefenderScanner
if ($scanner) {
    foreach ($target in $Path) {
        if ($scanner.Mode -eq "Cmdlet") {
            Start-MpScan -ScanType QuickScan -ScanPath $target
        } else {
            & $scanner.Command -Scan -ScanType 3 -File $target
            if ($LASTEXITCODE -ne 0) {
                throw "Microsoft Defender scan failed for $target"
            }
        }
    }
}

if ($ChecksumOutput) {
    $hashLines | Set-Content -Path $ChecksumOutput -Encoding ascii
}

Write-Host "Validation completed successfully."
