# Install the PyInstaller bundle to %LOCALAPPDATA%\VTU AIDS without VTU_AIDS_Setup.exe.
# Use when Smart App Control blocks the Inno installer (turn SAC Off first, or sign releases).
param(
    [string]$InstallRoot = (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)),
    [string]$DestDir = (Join-Path $env:LOCALAPPDATA "VTU AIDS"),
    [switch]$OpenSettings,
    [switch]$SkipSacCheck
)

$ErrorActionPreference = "Stop"
. (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "SmartAppControl.ps1")

if (-not $SkipSacCheck) {
    try {
        Assert-SmartAppControlAllowsUnsigned -OpenSettings:$OpenSettings
    } catch {
        exit 2
    }
}

$src = Join-Path $InstallRoot "dist\VTU AIDS"
if (-not (Test-Path (Join-Path $src "VTU AIDS.exe"))) {
    Write-Host "dist\VTU AIDS not found. Build first:" -ForegroundColor Red
    Write-Host "  powershell -ExecutionPolicy Bypass -File build\build_windows.ps1" -ForegroundColor Yellow
    exit 1
}

Write-Host "Copying app to $DestDir ..." -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $DestDir | Out-Null
& robocopy $src $DestDir /MIR /NFL /NDL /NJH /NJS /NC /NS /NP | Out-Null
if ($LASTEXITCODE -ge 8) {
    throw "robocopy failed with exit code $LASTEXITCODE"
}

$unblocked = Unblock-PathRecursive -Path $DestDir
Write-Host "Unblocked $unblocked file(s)." -ForegroundColor DarkGray

$exe = Join-Path $DestDir "VTU AIDS.exe"
$sig = Get-AuthenticodeSignature -FilePath $exe
if ($sig.Status -ne "Valid") {
    Write-Host "App is unsigned." -ForegroundColor DarkGray
}

Write-Host "Starting VTU AIDS from $exe" -ForegroundColor Green
Start-Process -FilePath $exe -WorkingDirectory $DestDir
