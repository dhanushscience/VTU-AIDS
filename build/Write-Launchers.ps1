# Creates launchers for an install folder.
param(
    [Parameter(Mandatory = $true)]
    [string]$InstallRoot
)

$ErrorActionPreference = "Stop"
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$DistDir = Join-Path $InstallRoot "dist\VTU AIDS"
$Pythonw = Join-Path $InstallRoot ".venv\Scripts\pythonw.exe"
$Python = Join-Path $InstallRoot ".venv\Scripts\python.exe"

$browserBat = @"
@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run Install VTU AIDS.bat first.
    pause
    exit /b 1
)
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0vtu_aids.py" --browser
exit /b 0
"@

$desktopBat = @"
@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run Install VTU AIDS.bat first.
    pause
    exit /b 1
)
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0vtu_aids.py" --desktop
exit /b 0
"@

Set-Content -Path (Join-Path $InstallRoot "Run VTU AIDS.bat") -Value $desktopBat -Encoding ASCII
Set-Content -Path (Join-Path $InstallRoot "Run VTU AIDS (Desktop).bat") -Value $desktopBat -Encoding ASCII
Set-Content -Path (Join-Path $InstallRoot "Run VTU AIDS (Browser).bat") -Value $browserBat -Encoding ASCII

$distBat = @"
@echo off
set "INSTALL=%~dp0..\.."
if exist "%INSTALL%\.venv\Scripts\pythonw.exe" (
    cd /d "%INSTALL%"
    start "" "%INSTALL%\.venv\Scripts\pythonw.exe" "%INSTALL%\vtu_aids.py" --desktop
    exit /b 0
)
echo Run Install VTU AIDS.bat from the main VTU AIDS folder.
pause
"@

if (Test-Path $DistDir) {
    Set-Content -Path (Join-Path $DistDir "Launch VTU AIDS.bat") -Value $distBat -Encoding ASCII
}

if (Test-Path $DistDir) {
    Get-ChildItem -Path $DistDir -Recurse -File -ErrorAction SilentlyContinue |
        ForEach-Object { Unblock-File -LiteralPath $_.FullName -ErrorAction SilentlyContinue }
}

Write-Host "Launchers written under $InstallRoot"
