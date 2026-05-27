# Build VTU AIDS desktop app (Windows). Run from repo root:
#   powershell -ExecutionPolicy Bypass -File build\build_windows.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
. (Join-Path $Root "build\SmartAppControl.ps1")
if (Test-SmartAppControlBlocking) {
    Show-SmartAppControlHelp -NonInteractive
    Write-Host "Build continues, but SAC On will block unsigned installer/app on this PC." -ForegroundColor Yellow
}

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Host "Create venv first: python -m venv .venv" -ForegroundColor Red
    exit 1
}

Write-Host "Installing desktop dependencies..." -ForegroundColor Cyan
& $Python -m pip install -q -r requirements-desktop.txt
& $Python -m playwright install chromium

Write-Host "Building app icon (app.ico)..." -ForegroundColor Cyan
& (Join-Path $Root "build\Build-AppIcon.ps1") -InstallRoot $Root

Write-Host "Building VTU AIDS.exe (onedir)..." -ForegroundColor Cyan
& $Python -m PyInstaller build/VTU_AIDS.spec --noconfirm

Write-Host "Finalizing dist (icon, unblock)..." -ForegroundColor Cyan
& (Join-Path $Root "build\Create-SignedEntry.ps1") -InstallRoot $Root

$Dist = Join-Path $Root "dist\VTU AIDS"
$BrowsersDest = Join-Path $Dist "ms-playwright"
$BrowsersSrc = Join-Path $env:LOCALAPPDATA "ms-playwright"

if (Test-Path $BrowsersSrc) {
    Write-Host "Bundling Playwright Chromium (large copy)..." -ForegroundColor Cyan
    if (-not (Test-Path $BrowsersDest)) {
        New-Item -ItemType Directory -Force -Path $BrowsersDest | Out-Null
    }
    Copy-Item "$BrowsersSrc\*" $BrowsersDest -Recurse -Force
}

& (Join-Path $Root "build\Sign-Release.ps1") -InstallRoot $Root -ErrorAction SilentlyContinue

Write-Host "Creating Inno Setup Installer..." -ForegroundColor Cyan
$ISCC = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $ISCC)) {
    $ISCC = "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
}
if (-not (Test-Path $ISCC)) {
    $ISCC = "${env:LOCALAPPDATA}\Programs\Inno Setup 6\ISCC.exe"
}

if (Test-Path $ISCC) {
    $SetupScript = Join-Path $Root "build\setup.iss"
    & $ISCC $SetupScript
    & (Join-Path $Root "build\Finalize-Output.ps1") -InstallRoot $Root
    Write-Host ""
    Write-Host "Done! Installer: build\Output\VTU_AIDS_Setup.exe" -ForegroundColor Green
    Write-Host "If Smart App Control blocks it, run: build\Output\Run-VTU_AIDS_Setup.bat" -ForegroundColor Yellow
    Write-Host "  or: powershell -ExecutionPolicy Bypass -File build\Invoke-Installer.ps1" -ForegroundColor Yellow
} else {
    Write-Host ""
    Write-Host "Done building PyInstaller bundle." -ForegroundColor Green
    Write-Host "To generate the setup .exe, please install Inno Setup 6 and compile build\setup.iss" -ForegroundColor Yellow
}
