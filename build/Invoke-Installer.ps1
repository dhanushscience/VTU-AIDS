# Run VTU_AIDS_Setup.exe (copied to %TEMP% to avoid OneDrive Mark-of-the-Web).
# Requires Smart App Control Off, or a signed build (VTU_AIDS_SIGN_PFX).
param(
    [string]$InstallRoot = (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)),
    [switch]$OpenSettings,
    [switch]$NonInteractive,
    [switch]$SkipSacCheck
)

$ErrorActionPreference = "Stop"
. (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "SmartAppControl.ps1")

if (-not $SkipSacCheck) {
    try {
        Assert-SmartAppControlAllowsUnsigned -OpenSettings:$OpenSettings
    } catch {
        if ($NonInteractive) { exit 2 }
        exit 2
    }
}

$candidates = @(
    (Join-Path $InstallRoot "build\Output\VTU_AIDS_Setup.exe"),
    (Join-Path $InstallRoot "build\VTU_AIDS_Setup.exe")
)
$setup = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $setup) {
    Write-Host "Installer not found. Build first:" -ForegroundColor Red
    Write-Host "  powershell -ExecutionPolicy Bypass -File build\build_windows.ps1" -ForegroundColor Yellow
    exit 1
}

$null = Unblock-PathRecursive -Path (Split-Path -Parent $setup)
Unblock-File -LiteralPath $setup -ErrorAction SilentlyContinue

$sig = Get-AuthenticodeSignature -FilePath $setup
if ($sig.Status -ne "Valid") {
    Write-Host "Installer is unsigned ($($sig.Status))." -ForegroundColor DarkGray
}

$tempDir = Join-Path $env:TEMP "VTU_AIDS_Setup"
New-Item -ItemType Directory -Force -Path $tempDir | Out-Null
$tempSetup = Join-Path $tempDir "VTU_AIDS_Setup.exe"
Copy-Item -LiteralPath $setup -Destination $tempSetup -Force
Unblock-File -LiteralPath $tempSetup -ErrorAction SilentlyContinue

Write-Host "Launching installer from $tempSetup" -ForegroundColor Cyan
try {
    $proc = Start-Process -FilePath $tempSetup -PassThru -Wait
    if ($proc.ExitCode -and $proc.ExitCode -ne 0) { exit $proc.ExitCode }
    exit 0
} catch {
    Write-Host "Could not start installer: $_" -ForegroundColor Red
    Show-SmartAppControlHelp -OpenSettings -NonInteractive:$NonInteractive
    exit 1
}
