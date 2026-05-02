[CmdletBinding()]
param(
    [string]$OutputPath = "build\website-pella.zip",
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$websiteDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if ([System.IO.Path]::IsPathRooted($OutputPath)) {
    $zipPath = $OutputPath
}
else {
    $zipPath = Join-Path $websiteDir $OutputPath
}

$zipPath = [System.IO.Path]::GetFullPath($zipPath)
$zipDir = Split-Path -Parent $zipPath

if (-not (Test-Path -LiteralPath $zipDir)) {
    New-Item -ItemType Directory -Path $zipDir -Force | Out-Null
}

if ((Test-Path -LiteralPath $zipPath) -and -not $Force) {
    throw "Zip file already exists: $zipPath. Re-run with -Force to overwrite it."
}

if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}

$stagingDir = Join-Path ([System.IO.Path]::GetTempPath()) ("80-movie-website-package-" + [System.Guid]::NewGuid().ToString('N'))
$stagingRoot = Join-Path $stagingDir 'package'
New-Item -ItemType Directory -Path $stagingRoot -Force | Out-Null

try {
    $robocopyArgs = @(
        $websiteDir,
        $stagingRoot,
        '/E',
        '/NFL',
        '/NDL',
        '/NJH',
        '/NJS',
        '/NP',
        '/XD',
        (Join-Path $websiteDir 'dist'),
        (Join-Path $websiteDir 'build'),
        (Join-Path $websiteDir '__pycache__'),
        '/XF',
        '.env',
        '*.zip',
        '*.pyc',
        '*.pyo'
    )

    & robocopy @robocopyArgs | Out-Null
    if ($LASTEXITCODE -ge 8) {
        throw "robocopy failed with exit code $LASTEXITCODE"
    }

    Get-ChildItem -Path $stagingRoot -Recurse -Directory -Filter '__pycache__' |
        Remove-Item -Recurse -Force

    Compress-Archive -Path (Join-Path $stagingRoot '*') -DestinationPath $zipPath -CompressionLevel Optimal

    $zipItem = Get-Item -LiteralPath $zipPath
    Write-Host "Created Pella upload zip: $($zipItem.FullName)"
    Write-Host "Size: $([Math]::Round($zipItem.Length / 1MB, 2)) MB"
}
finally {
    if (Test-Path -LiteralPath $stagingDir) {
        Remove-Item -LiteralPath $stagingDir -Recurse -Force
    }
}