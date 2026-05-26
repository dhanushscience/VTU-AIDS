# Generate static/app.ico and refresh dist copy for the installer.
param(
    [string]$InstallRoot = (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))
)

$ErrorActionPreference = "Stop"
$Python = Join-Path $InstallRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Create .venv first: python -m venv .venv"
}

& $Python -m pip install -q pillow
& $Python (Join-Path $InstallRoot "build\make_ico.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$Ico = Join-Path $InstallRoot "static\app.ico"
$Favicon = Join-Path $InstallRoot "static\favicon.png"
$Dist = Join-Path $InstallRoot "dist\VTU AIDS"
if (Test-Path $Dist) {
    if (Test-Path $Ico) {
        Copy-Item -LiteralPath $Ico -Destination (Join-Path $Dist "VTU AIDS.ico") -Force
    }
    $distStatic = Join-Path $Dist "_internal\static"
    if ((Test-Path $Favicon) -and (Test-Path $distStatic)) {
        Copy-Item -LiteralPath $Favicon -Destination (Join-Path $distStatic "favicon.png") -Force
        Copy-Item -LiteralPath (Join-Path $InstallRoot "static\logo.png") -Destination (Join-Path $distStatic "logo.png") -Force -ErrorAction SilentlyContinue
    }
}
