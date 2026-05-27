# Post-Inno steps: unblock setup, optional signing, helper launchers in build\Output.
param(
    [string]$InstallRoot = (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))
)

$ErrorActionPreference = "Stop"
. (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "SmartAppControl.ps1")

$OutputDir = Join-Path $InstallRoot "build\Output"
$setup = Join-Path $OutputDir "VTU_AIDS_Setup.exe"
if (-not (Test-Path $setup)) {
    $setup = Join-Path $InstallRoot "build\VTU_AIDS_Setup.exe"
}
if (-not (Test-Path $setup)) {
    Write-Host "Finalize-Output: no VTU_AIDS_Setup.exe found." -ForegroundColor Yellow
    return
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
if ($setup -notlike "$OutputDir*") {
    Copy-Item -LiteralPath $setup -Destination (Join-Path $OutputDir "VTU_AIDS_Setup.exe") -Force
    $setup = Join-Path $OutputDir "VTU_AIDS_Setup.exe"
}

Unblock-File -LiteralPath $setup -ErrorAction SilentlyContinue
& (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "Sign-Release.ps1") -InstallRoot $InstallRoot -ExtraFiles @($setup)

$runBat = @'
@echo off
title VTU AIDS Setup
cd /d "%~dp0"
echo If Smart App Control blocked the installer, this script copies it to Temp and retries.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\Invoke-Installer.ps1"
if errorlevel 1 (
  echo.
  echo Alternative: install from the built folder without setup.exe:
  echo   powershell -ExecutionPolicy Bypass -File "%~dp0..\Install-From-Dist.ps1"
  pause
)
'@
Set-Content -Path (Join-Path $OutputDir "Run-VTU_AIDS_Setup.bat") -Value $runBat -Encoding ASCII

$help = @'
Smart App Control blocked VTU_AIDS_Setup.exe?
============================================

Windows blocks unsigned local builds. Unblock-File alone does NOT bypass Smart App Control.

Quick fix (your own PC / dev build):
  1. Windows Security -> App & browser control -> Smart App Control -> Off
  2. Double-click Run-VTU_AIDS_Setup.bat in this folder
     OR run from repo root:
       powershell -ExecutionPolicy Bypass -File build\Invoke-Installer.ps1

Install without the setup.exe (after SAC is Off):
  powershell -ExecutionPolicy Bypass -File build\Install-From-Dist.ps1

Release builds: set VTU_AIDS_SIGN_PFX and VTU_AIDS_SIGN_PASSWORD before build\build_windows.ps1

More: docs\windows.md
'@
Set-Content -Path (Join-Path $OutputDir "SMART_APP_CONTROL.txt") -Value $help -Encoding UTF8

Write-Host "Output helpers written to $OutputDir" -ForegroundColor Green
