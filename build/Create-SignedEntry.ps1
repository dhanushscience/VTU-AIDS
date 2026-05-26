# Post-build steps for dist\VTU AIDS (icon, unblock, cleanup).
# Uses the PyInstaller bootloader as VTU AIDS.exe — do not swap in pythonw.exe
# (that layout cannot see the stdlib and fails with "No module named encodings").
param(
    [string]$InstallRoot = (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))
)

$ErrorActionPreference = "Stop"
$Dist = Join-Path $InstallRoot "dist\VTU AIDS"
$Exe = Join-Path $Dist "VTU AIDS.exe"
$BootBackup = Join-Path $Dist "_bootloader\VTU AIDS (PyInstaller bootloader).exe"
$Internal = Join-Path $Dist "_internal"

if (-not (Test-Path $Exe)) {
    throw "Build output not found: $Exe"
}

# Restore PyInstaller exe if a previous build replaced it with pythonw.exe (~100 KB).
$exeLen = (Get-Item -LiteralPath $Exe).Length
if ($exeLen -lt 1MB -and (Test-Path $BootBackup)) {
    Copy-Item -LiteralPath $BootBackup -Destination $Exe -Force
    Write-Host "Restored PyInstaller launcher -> VTU AIDS.exe" -ForegroundColor Yellow
}

# python314._pth + copied DLLs next to the exe break the PyInstaller bootloader.
foreach ($name in @("python314._pth", "python313._pth", "python312._pth", "python.exe", "python3.dll", "python314.dll", "python313.dll", "VCRUNTIME140.dll", "VCRUNTIME140_1.dll")) {
    $p = Join-Path $Dist $name
    if (Test-Path $p) { Remove-Item -LiteralPath $p -Force }
}

$siteCustomize = Join-Path $Internal "sitecustomize.py"
if (Test-Path $siteCustomize) {
    Remove-Item -LiteralPath $siteCustomize -Force
}

$AppIco = Join-Path $InstallRoot "static\app.ico"
if (Test-Path $AppIco) {
    $distIco = Join-Path $Dist "VTU AIDS.ico"
    Copy-Item -LiteralPath $AppIco -Destination $distIco -Force
    $lnkPath = Join-Path $Dist "VTU AIDS.lnk"
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($lnkPath)
    $shortcut.TargetPath = $Exe
    $shortcut.WorkingDirectory = $Dist
    $shortcut.IconLocation = "$distIco,0"
    $shortcut.Description = "VTU AIDS"
    $shortcut.Save()
}

$fixBat = @'
@echo off
cd /d "%~dp0"
echo Removing Windows download blocks from this folder...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-ChildItem -LiteralPath '%~dp0' -Recurse -File | Unblock-File -ErrorAction SilentlyContinue"
echo Starting VTU AIDS...
start "" "%~dp0VTU AIDS.exe"
exit /b 0
'@
Set-Content -Path (Join-Path $Dist "Fix block and run VTU AIDS.bat") -Value $fixBat -Encoding ASCII

# Icon is embedded by PyInstaller (build/VTU_AIDS.spec). Do NOT run rcedit on the
# exe afterward — it corrupts PyInstaller's PKG and breaks startup.

& (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "Unblock-Dist.ps1") -DistDir $Dist

Write-Host "Post-build dist ready: $Dist" -ForegroundColor Green
